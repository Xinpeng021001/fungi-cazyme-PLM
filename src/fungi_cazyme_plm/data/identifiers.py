"""Identifier, family, and FASTA-header normalization."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


FAMILY_RE = re.compile(r"^([A-Za-z]+\d+)")
CLASS_RE = re.compile(r"^([A-Za-z]+)")


def family_base(value: str) -> str:
    """Return base CAZy family while preserving fam-0 as a real open-set tag."""

    cleaned = value.strip().strip("'\"").removesuffix(".hmm").strip("'\"")
    match = FAMILY_RE.match(cleaned)
    return match.group(1).upper() if match else cleaned


def cazy_class(value: str) -> str:
    match = CLASS_RE.match(family_base(value))
    return match.group(1).upper() if match else ""


def is_fam0(value: str) -> bool:
    base = family_base(value)
    match = re.match(r"^[A-Z]+(\d+)$", base)
    return bool(match and int(match.group(1)) == 0)


def split_annotation(value: str, base_only: bool = True) -> Counter[str]:
    """Parse a `+` annotation as a multiset, preserving repeated domains."""

    if value is None:
        return Counter()
    cleaned = value.strip()
    if not cleaned or cleaned == "-":
        return Counter()
    ignored = {"cazyme_annotation", "dbcan_hmm", "dbcan_annotation", "gene id", "ec#"}
    items = []
    for token in cleaned.split("+"):
        token = token.strip()
        if not token or token.lower() in ignored:
            continue
        items.append(family_base(token) if base_only else token)
    return Counter(items)


def format_annotation(counter: Counter[str]) -> str:
    values: list[str] = []
    for family in sorted(counter):
        values.extend([family] * counter[family])
    return "+".join(values) if values else "-"


def genome_from_filename(value: str) -> str:
    """Extract a JGI portal/genome identifier from a source filename."""

    name = Path(value).name
    for marker in (
        "_GeneCatalog",
        "_filtered",
        "_Filtered",
        ".aa.fasta",
        ".fasta",
        ".faa",
    ):
        if marker in name:
            name = name.split(marker, 1)[0]
    return name


def resolve_genome_alias(observed: str, known_genomes: set[str]) -> tuple[str | None, str]:
    """Resolve versioned JGI portal names without guessing across multiple candidates."""

    if observed in known_genomes:
        return observed, "exact_genome_id"
    candidate = observed
    while match := re.fullmatch(r"(.+)_\d+", candidate):
        candidate = match.group(1)
        if candidate in known_genomes:
            return candidate, "stripped_numeric_version_suffix"
    pgt = re.fullmatch(r"Pgt_201_([AB]\d+)", observed)
    if pgt and f"Pgt_{pgt.group(1)}" in known_genomes:
        return f"Pgt_{pgt.group(1)}", "aim2_pgt_201_alias"
    return None, "unresolved_genome_id"


@dataclass(frozen=True)
class CazyHeader:
    original_id: str
    genome_id: str
    families_raw: tuple[str, ...]
    identifier_type: str


def parse_cazy_header(header: str) -> CazyHeader:
    """Parse both observed 2024 and 2025 fungal CAZy header layouts."""

    text = header.strip().lstrip(">").split()[0]
    parts = text.split("|")
    numeric_index = next((index for index, part in enumerate(parts) if part.isdigit()), None)
    if numeric_index is None:
        accession = parts[0]
        families = tuple(
            token
            for token in parts[1:]
            if cazy_class(token) in {"AA", "CBM", "CE", "GH", "GT", "PL"}
            and FAMILY_RE.match(token)
        )
        if not accession or not families:
            raise ValueError(f"Unsupported accession-style CAZy header: {header!r}")
        return CazyHeader(accession, "unresolved_genome", families, "accession")
    original_id = parts[numeric_index]
    if numeric_index + 1 >= len(parts):
        raise ValueError(f"CAZy header has no genome field: {header!r}")
    genome_id = genome_from_filename(parts[numeric_index + 1])
    if numeric_index == 0:
        families = parts[numeric_index + 2 :]
    else:
        families = parts[:numeric_index]
    families = tuple(token for token in families if token)
    if not families:
        raise ValueError(f"CAZy header has no family token: {header!r}")
    return CazyHeader(original_id, genome_id, families, "jgi_numeric")


@dataclass(frozen=True)
class JGIHeader:
    genome_id: str
    original_id: str
    raw_id: str


def parse_jgi_header(header: str, fallback_genome: str | None = None) -> JGIHeader:
    """Parse pipe-delimited raw JGI or hyphenated run_dbCAN identifiers."""

    raw = header.strip().lstrip(">").split()[0]
    if raw.startswith("jgi|"):
        parts = raw.split("|", 3)
        if len(parts) < 3:
            raise ValueError(f"Malformed JGI header: {header!r}")
        return JGIHeader(parts[1], parts[2], raw)
    if raw.startswith("jgi-"):
        parts = raw.split("-", 3)
        if len(parts) < 3:
            raise ValueError(f"Malformed run_dbCAN JGI ID: {header!r}")
        return JGIHeader(parts[1], parts[2], raw)
    if raw.isdigit() and fallback_genome:
        return JGIHeader(fallback_genome, raw, raw)
    if fallback_genome:
        match = re.search(r"(?:^|[-|])([0-9]+)(?:[-|]|$)", raw)
        if match:
            return JGIHeader(fallback_genome, match.group(1), raw)
    raise ValueError(f"Unrecognized JGI header: {header!r}")


def canonical_id(genome_id: str, original_id: str, source: str = "aim2") -> str:
    return f"{source}:{genome_id}:{original_id}"
