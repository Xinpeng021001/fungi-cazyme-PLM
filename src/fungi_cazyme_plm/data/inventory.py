"""Immutable data-source inventory and validation."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import ProjectConfig
from ..errors import ValidationError
from ..provenance import RunContext
from ..tableio import deterministic_gzip_text, sha256_file


SNAPSHOT_FIELDS = [
    "source_id",
    "kind",
    "resolved_path",
    "exists",
    "file_count",
    "size_bytes",
    "mtime_utc",
    "sha256",
    "record_count",
    "columns",
    "validation_status",
    "validation_message",
]


@dataclass
class InventoryRow:
    source_id: str
    kind: str
    resolved_path: str
    exists: bool
    file_count: int
    size_bytes: int
    mtime_utc: str
    sha256: str
    record_count: int | None
    columns: list[str]
    validation_status: str
    validation_message: str

    def flat(self) -> dict[str, Any]:
        value = asdict(self)
        value["exists"] = "true" if self.exists else "false"
        value["columns"] = json.dumps(self.columns, ensure_ascii=False)
        value["record_count"] = "" if self.record_count is None else self.record_count
        return value


def _mtime_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


def _count_records(path: Path, spec: dict[str, Any]) -> int | None:
    prefix = spec.get("record_prefix")
    encoding = spec.get("encoding", "utf-8")
    suffix = path.suffix.lower()
    if prefix is not None:
        with path.open("r", encoding=encoding, errors="strict") as handle:
            return sum(1 for line in handle if line.startswith(str(prefix)))
    if suffix in {".tsv", ".txt", ".csv"}:
        if spec.get("unique_records", False):
            delimiter = "," if suffix == ".csv" else "\t"
            with path.open("r", encoding=encoding, errors="strict", newline="") as handle:
                reader = csv.reader(handle, delimiter=delimiter, quoting=csv.QUOTE_NONE)
                if spec.get("has_header", True):
                    next(reader, None)
                return len(
                    {
                        tuple(value.strip() for value in row)
                        for row in reader
                        if any(value.strip() for value in row)
                    }
                )
        with path.open("r", encoding=encoding, errors="strict", newline="") as handle:
            line_count = sum(1 for line in handle if line.strip())
        return line_count - (1 if spec.get("has_header", True) and line_count else 0)
    return None


def _read_columns(path: Path, spec: dict[str, Any]) -> list[str]:
    if not spec.get("has_header", True):
        return []
    suffix = path.suffix.lower()
    if suffix not in {".tsv", ".txt", ".csv"}:
        return []
    delimiter = "," if suffix == ".csv" else "\t"
    encoding = spec.get("encoding", "utf-8")
    try:
        with path.open("r", encoding=encoding, errors="strict", newline="") as handle:
            return [
                value.strip()
                for value in next(
                    csv.reader(handle, delimiter=delimiter, quoting=csv.QUOTE_NONE), []
                )
            ]
    except (UnicodeError, csv.Error):
        return []


def _quick_digest(path: Path) -> str:
    stat = path.stat()
    payload = f"{path.resolve()}\0{stat.st_size}\0{stat.st_mtime_ns}".encode()
    return hashlib.sha256(payload).hexdigest()


def inspect_file(source_id: str, path: Path, spec: dict[str, Any], quick: bool) -> InventoryRow:
    if not path.is_file():
        return InventoryRow(
            source_id, "file", str(path), False, 0, 0, "", "", None, [], "error", "missing file"
        )
    stat = path.stat()
    record_count = _count_records(path, spec)
    columns = _read_columns(path, spec)
    digest = _quick_digest(path) if quick else sha256_file(path)
    messages: list[str] = []
    status = "warning" if quick else "ok"
    if quick:
        messages.append("quick metadata digest; full content hash not computed")
    expected = spec.get("expected_records")
    if expected is not None and record_count != int(expected):
        status = "error"
        messages.append(f"expected {expected} records, observed {record_count}")
    return InventoryRow(
        source_id=source_id,
        kind="file",
        resolved_path=str(path),
        exists=True,
        file_count=1,
        size_bytes=stat.st_size,
        mtime_utc=_mtime_utc(stat.st_mtime),
        sha256=digest,
        record_count=record_count,
        columns=columns,
        validation_status=status,
        validation_message="; ".join(messages),
    )


def inspect_directory(
    source_id: str,
    path: Path,
    spec: dict[str, Any],
    quick: bool,
) -> tuple[InventoryRow, list[dict[str, Any]]]:
    if not path.is_dir():
        row = InventoryRow(
            source_id,
            "directory",
            str(path),
            False,
            0,
            0,
            "",
            "",
            None,
            [],
            "error",
            "missing directory",
        )
        return row, []
    include = spec.get("include", "**/*")
    files = sorted(candidate for candidate in path.glob(include) if candidate.is_file())
    detail: list[dict[str, Any]] = []
    root_digest = hashlib.sha256()
    size = 0
    newest_mtime = path.stat().st_mtime
    for candidate in files:
        stat = candidate.stat()
        digest = _quick_digest(candidate) if quick else sha256_file(candidate)
        relative = candidate.relative_to(path).as_posix()
        root_digest.update(relative.encode())
        root_digest.update(b"\0")
        root_digest.update(digest.encode())
        root_digest.update(b"\0")
        root_digest.update(str(stat.st_size).encode())
        root_digest.update(b"\n")
        size += stat.st_size
        newest_mtime = max(newest_mtime, stat.st_mtime)
        detail.append(
            {
                "source_id": source_id,
                "relative_path": relative,
                "size_bytes": stat.st_size,
                "mtime_utc": _mtime_utc(stat.st_mtime),
                "sha256": digest,
            }
        )
    messages: list[str] = []
    status = "warning" if quick else "ok"
    if quick:
        messages.append("quick metadata digest; full child hashes not computed")
    expected = spec.get("expected_files")
    if expected is not None and len(files) != int(expected):
        status = "error"
        messages.append(f"expected {expected} files, observed {len(files)}")
    row = InventoryRow(
        source_id=source_id,
        kind="directory",
        resolved_path=str(path),
        exists=True,
        file_count=len(files),
        size_bytes=size,
        mtime_utc=_mtime_utc(newest_mtime),
        sha256=root_digest.hexdigest(),
        record_count=None,
        columns=[],
        validation_status=status,
        validation_message="; ".join(messages),
    )
    return row, detail


def inventory_sources(
    config: ProjectConfig,
    run: RunContext,
    quick: bool = False,
) -> tuple[Path, list[InventoryRow]]:
    """Inspect all configured sources, write a snapshot, and fail on mismatches."""

    rows: list[InventoryRow] = []
    details: list[dict[str, Any]] = []
    for source_id, spec in config.sources.items():
        path = Path(spec["path"])
        print(f"[inventory] {source_id}: {path}")
        if spec.get("kind") == "directory":
            row, child_rows = inspect_directory(source_id, path, spec, quick)
            details.extend(child_rows)
        else:
            row = inspect_file(source_id, path, spec, quick)
        rows.append(row)
        if path.exists():
            run.record_input(
                source_id,
                path,
                record_count=row.record_count,
                schema="source_inventory",
                digest=row.sha256,
            )
        run.event(
            "source_inspected",
            source_id=source_id,
            status=row.validation_status,
            records=row.record_count,
            files=row.file_count,
        )

    combined = hashlib.sha256()
    for row in sorted(rows, key=lambda item: item.source_id):
        combined.update(f"{row.source_id}\0{row.sha256}\n".encode())
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    snapshot_stem = f"source_snapshot_{timestamp}_{combined.hexdigest()[:12]}"
    snapshot_dir = config.outputs["snapshots_dir"]
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / f"{snapshot_stem}.tsv"
    detail_path = snapshot_dir / f"{snapshot_stem}.files.tsv.gz"
    with snapshot_path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=SNAPSHOT_FIELDS,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(row.flat() for row in rows)
    with deterministic_gzip_text(detail_path) as handle:
        fields = ["source_id", "relative_path", "size_bytes", "mtime_utc", "sha256"]
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(details)

    run.record_output("source_snapshot", snapshot_path, len(rows), SNAPSHOT_FIELDS)
    run.record_output(
        "source_snapshot_files",
        detail_path,
        len(details),
        ["source_id", "relative_path", "size_bytes", "mtime_utc", "sha256"],
    )
    run.add_metric("source_snapshot", str(snapshot_path))
    run.add_metric("source_count", len(rows))
    run.add_metric("source_error_count", sum(row.validation_status == "error" for row in rows))
    run.add_metric("quick_inventory", quick)

    errors = [row for row in rows if row.validation_status == "error"]
    if errors:
        message = "; ".join(f"{row.source_id}: {row.validation_message}" for row in errors)
        raise ValidationError(f"Source inventory failed: {message}")
    return snapshot_path, rows


def validate_snapshot(config: ProjectConfig, snapshot_path: str | Path) -> None:
    """Fail if a configured source differs from a prior full snapshot."""

    previous: dict[str, str] = {}
    with Path(snapshot_path).open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            previous[row["source_id"]] = row["sha256"]
    drift: list[str] = []
    for source_id in sorted(set(config.sources) - set(previous)):
        drift.append(f"{source_id}: new source absent from pinned snapshot")
    for source_id, expected_digest in previous.items():
        if source_id not in config.sources:
            drift.append(f"{source_id}: missing from current config")
            continue
        spec = config.sources[source_id]
        path = Path(spec["path"])
        if spec.get("kind") == "directory":
            current, _ = inspect_directory(source_id, path, spec, quick=False)
        else:
            current = inspect_file(source_id, path, spec, quick=False)
        if current.sha256 != expected_digest:
            drift.append(f"{source_id}: {expected_digest[:12]} -> {current.sha256[:12]}")
    if drift:
        raise ValidationError("Input drift detected: " + "; ".join(drift))
