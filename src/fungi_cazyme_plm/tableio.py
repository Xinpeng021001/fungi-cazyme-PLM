"""Streaming TSV/Parquet output helpers."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence, TextIO


try:  # Keep audit commands useful in an existing light-weight environment.
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:  # pragma: no cover - exercised in dependency-light hosts
    pa = None
    pq = None


TYPE_MAP = {
    "string": lambda: pa.string() if pa else None,
    "int64": lambda: pa.int64() if pa else None,
    "float64": lambda: pa.float64() if pa else None,
    "bool": lambda: pa.bool_() if pa else None,
}


def sha256_file(path: str | Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def count_lines(path: str | Path, encoding: str = "utf-8") -> int:
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding=encoding, errors="strict", newline="") as handle:
        return sum(1 for _ in handle)


@contextmanager
def deterministic_gzip_text(path: str | Path) -> Iterator[TextIO]:
    """Create a gzip text file with a fixed header timestamp for stable checksums."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    raw_handle = output.open("xb")
    gzip_handle = gzip.GzipFile(filename="", mode="wb", fileobj=raw_handle, mtime=0)
    text_handle = io.TextIOWrapper(gzip_handle, encoding="utf-8", newline="")
    try:
        yield text_handle
    finally:
        text_handle.close()
        raw_handle.close()


def read_tsv(path: str | Path, encoding: str = "utf-8") -> Iterator[dict[str, str]]:
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding=encoding, newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t", quoting=csv.QUOTE_NONE)
        if reader.fieldnames is None:
            return
        for row in reader:
            yield {str(key).strip(): value for key, value in row.items() if key is not None}


def write_tsv(
    path: str | Path,
    rows: Iterable[Mapping[str, Any]],
    fieldnames: Sequence[str],
) -> int:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {output}")
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        count = 0
        for row in rows:
            writer.writerow({key: _tsv_value(row.get(key)) for key in fieldnames})
            count += 1
    return count


def _tsv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        return ";".join(str(item) for item in value)
    return str(value)


class ArtifactTableWriter:
    """Write a typed Parquet table and a portable gzipped TSV in one pass."""

    def __init__(
        self,
        base_path: str | Path,
        fieldnames: Sequence[str],
        types: Mapping[str, str] | None = None,
        batch_size: int = 50_000,
        require_parquet: bool = False,
    ) -> None:
        self.base_path = Path(base_path)
        self.base_path.parent.mkdir(parents=True, exist_ok=True)
        self.tsv_path = self.base_path.with_suffix(".tsv.gz")
        self.parquet_path = self.base_path.with_suffix(".parquet")
        self.metadata_path = self.base_path.with_suffix(".metadata.json")
        for path in (self.tsv_path, self.parquet_path, self.metadata_path):
            if path.exists():
                raise FileExistsError(f"Refusing to overwrite existing output: {path}")
        if require_parquet and pa is None:
            raise RuntimeError("pyarrow is required for this command but is not installed")

        self.fieldnames = list(fieldnames)
        self.types = dict(types or {})
        self.batch_size = batch_size
        self.count = 0
        self._batch: list[dict[str, Any]] = []
        self._tsv_context = deterministic_gzip_text(self.tsv_path)
        self._tsv_handle = self._tsv_context.__enter__()
        self._tsv_writer = csv.DictWriter(
            self._tsv_handle,
            fieldnames=self.fieldnames,
            delimiter="\t",
            lineterminator="\n",
            extrasaction="ignore",
        )
        self._tsv_writer.writeheader()
        self._parquet_writer = None
        self._schema = self._make_schema() if pa is not None else None

    def _make_schema(self):
        fields = []
        for name in self.fieldnames:
            type_name = self.types.get(name, "string")
            if type_name not in TYPE_MAP:
                raise ValueError(f"Unsupported table type {type_name!r} for {name}")
            fields.append(pa.field(name, TYPE_MAP[type_name](), nullable=True))
        return pa.schema(fields)

    def write(self, row: Mapping[str, Any]) -> None:
        normalized = {name: row.get(name) for name in self.fieldnames}
        self._tsv_writer.writerow(
            {name: _tsv_value(normalized.get(name)) for name in self.fieldnames}
        )
        self._batch.append(normalized)
        self.count += 1
        if len(self._batch) >= self.batch_size:
            self._flush_parquet_batch()

    def _flush_parquet_batch(self) -> None:
        if not self._batch:
            return
        if pa is not None:
            table = pa.Table.from_pylist(self._batch, schema=self._schema)
            if self._parquet_writer is None:
                self._parquet_writer = pq.ParquetWriter(
                    self.parquet_path,
                    self._schema,
                    compression="zstd",
                )
            self._parquet_writer.write_table(table)
        self._batch.clear()

    def close(self) -> dict[str, Any]:
        self._flush_parquet_batch()
        if self._parquet_writer is not None:
            self._parquet_writer.close()
        elif pa is not None:
            empty = pa.Table.from_pylist([], schema=self._schema)
            pq.write_table(empty, self.parquet_path, compression="zstd")
        self._tsv_context.__exit__(None, None, None)
        metadata = {
            "rows": self.count,
            "columns": self.fieldnames,
            "tsv_gz": str(self.tsv_path),
            "parquet": str(self.parquet_path) if self.parquet_path.exists() else None,
            "parquet_written": self.parquet_path.exists(),
        }
        with self.metadata_path.open("x", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2, sort_keys=True)
            handle.write("\n")
        return metadata

    def __enter__(self) -> "ArtifactTableWriter":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if exc_type is None:
            self.close()
        else:
            self._tsv_context.__exit__(exc_type, exc, traceback)
            if self._parquet_writer is not None:
                self._parquet_writer.close()


def json_dump_new(path: str | Path, payload: Any) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return output


def json_load(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)
