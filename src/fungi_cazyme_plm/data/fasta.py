"""Dependency-free streaming FASTA helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterator


def iter_fasta(path: str | Path) -> Iterator[tuple[str, str]]:
    header: str | None = None
    chunks: list[str] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header is not None:
                    yield header, normalize_sequence("".join(chunks))
                header = line[1:]
                chunks = []
            elif header is None:
                raise ValueError(f"Sequence before first FASTA header at {path}:{line_number}")
            else:
                chunks.append(line)
    if header is not None:
        yield header, normalize_sequence("".join(chunks))


def normalize_sequence(sequence: str) -> str:
    return sequence.replace(" ", "").replace("*", "").upper()


def sequence_hashes(sequence: str) -> tuple[str, str]:
    encoded = normalize_sequence(sequence).encode("ascii", errors="strict")
    return hashlib.sha256(encoded).hexdigest(), hashlib.md5(encoded).hexdigest()

