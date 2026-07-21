"""Audit family-substrate mappings without treating inherited labels as gold."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..config import ProjectConfig
from ..data.fasta import iter_fasta
from ..data.identifiers import cazy_class, family_base, parse_cazy_header
from ..errors import ValidationError
from ..provenance import RunContext
from ..tableio import ArtifactTableWriter, json_dump_new


NORMALIZED_FIELDS = [
    "family_raw",
    "family_base",
    "cazy_class",
    "substrate_high_level",
    "substrate_curated",
    "activity_name",
    "ec_number",
    "substrate_label_level",
    "evidence_type",
    "source_release",
]

FAMILY_AUDIT_FIELDS = [
    "family_base",
    "cazy_class",
    "mapping_rows",
    "high_level_substrate_count",
    "high_level_substrates",
    "curated_substrate_count",
    "curated_substrates",
    "ec_count",
    "ec_numbers",
    "polyspecific_high_level",
    "present_in_fungal_2025",
    "protein_level_hard_label_count",
    "hard_evaluation_eligible",
]


def _clean(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().strip('"').strip()


def _fungal_families(path: Path) -> set[str]:
    families = set()
    for header, _ in iter_fasta(path):
        parsed = parse_cazy_header(header)
        families.update(family_base(value) for value in parsed.families_raw)
    return families


def audit_function_labels(config: ProjectConfig, run: RunContext) -> dict[str, Any]:
    mapping_path = config.source_path("family_substrate_current")
    fungal_path = config.source_path("cazy_fungi_2025")
    run.record_input("family_substrate_current", mapping_path, schema="family_substrate")
    run.record_input("cazy_fungi_2025", fungal_path, schema="cazy_fasta")

    fungal_families = _fungal_families(fungal_path)
    normalized_writer = ArtifactTableWriter(
        run.result_dir / "function_labels_normalized", NORMALIZED_FIELDS
    )
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"rows": 0, "high": set(), "curated": set(), "ec": set()}
    )
    with mapping_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t", quoting=csv.QUOTE_NONE)
        header = [_clean(value) for value in next(reader, [])]
        canonical_header = {
            "Substrate_high_level": "substrate_high_level",
            "Substrate_curated": "substrate_curated",
            "Family": "family_raw",
            "Name": "activity_name",
            "EC_Number": "ec_number",
        }
        missing = set(canonical_header) - set(header)
        if missing:
            raise ValidationError(
                f"Function mapping is missing normalized columns: {sorted(missing)}"
            )
        index = {canonical_header[name]: header.index(name) for name in canonical_header}
        input_rows = 0
        physical_rows = 0
        duplicate_rows = 0
        seen_rows: set[tuple[str, ...]] = set()
        for values in reader:
            if not any(_clean(value) for value in values):
                continue
            physical_rows += 1
            normalized_key = tuple(_clean(value) for value in values)
            if normalized_key in seen_rows:
                duplicate_rows += 1
                continue
            seen_rows.add(normalized_key)
            input_rows += 1
            if len(values) < len(header):
                values.extend([""] * (len(header) - len(values)))
            raw_family = _clean(values[index["family_raw"]])
            if not raw_family:
                continue
            base = family_base(raw_family)
            high = _clean(values[index["substrate_high_level"]])
            curated = _clean(values[index["substrate_curated"]])
            ec_number = _clean(values[index["ec_number"]])
            activity = _clean(values[index["activity_name"]])
            normalized_writer.write(
                {
                    "family_raw": raw_family,
                    "family_base": base,
                    "cazy_class": cazy_class(base),
                    "substrate_high_level": high,
                    "substrate_curated": curated,
                    "activity_name": activity,
                    "ec_number": ec_number,
                    "substrate_label_level": "family",
                    "evidence_type": "family_inherited_weak_label",
                    "source_release": "current_local_dbcan",
                }
            )
            group = grouped[base]
            group["rows"] += 1
            if high:
                group["high"].add(high)
            if curated:
                group["curated"].add(curated)
            if ec_number:
                group["ec"].add(ec_number)
    normalized_writer.close()
    run.record_output(
        "function_labels_normalized_tsv",
        normalized_writer.tsv_path,
        normalized_writer.count,
        NORMALIZED_FIELDS,
    )
    if normalized_writer.parquet_path.exists():
        run.record_output(
            "function_labels_normalized_parquet",
            normalized_writer.parquet_path,
            normalized_writer.count,
            NORMALIZED_FIELDS,
        )

    audit_writer = ArtifactTableWriter(
        run.result_dir / "function_family_audit",
        FAMILY_AUDIT_FIELDS,
        {
            "mapping_rows": "int64",
            "high_level_substrate_count": "int64",
            "curated_substrate_count": "int64",
            "ec_count": "int64",
            "polyspecific_high_level": "bool",
            "present_in_fungal_2025": "bool",
            "protein_level_hard_label_count": "int64",
            "hard_evaluation_eligible": "bool",
        },
    )
    polyspecific = 0
    for family in sorted(grouped):
        group = grouped[family]
        multi = len(group["high"]) > 1
        polyspecific += int(multi)
        audit_writer.write(
            {
                "family_base": family,
                "cazy_class": cazy_class(family),
                "mapping_rows": group["rows"],
                "high_level_substrate_count": len(group["high"]),
                "high_level_substrates": ";".join(sorted(group["high"])),
                "curated_substrate_count": len(group["curated"]),
                "curated_substrates": ";".join(sorted(group["curated"])),
                "ec_count": len(group["ec"]),
                "ec_numbers": ";".join(sorted(group["ec"])),
                "polyspecific_high_level": multi,
                "present_in_fungal_2025": family in fungal_families,
                "protein_level_hard_label_count": 0,
                "hard_evaluation_eligible": False,
            }
        )
    audit_writer.close()
    run.record_output(
        "function_family_audit_tsv",
        audit_writer.tsv_path,
        audit_writer.count,
        FAMILY_AUDIT_FIELDS,
    )
    if audit_writer.parquet_path.exists():
        run.record_output(
            "function_family_audit_parquet",
            audit_writer.parquet_path,
            audit_writer.count,
            FAMILY_AUDIT_FIELDS,
        )

    expected_rows = config.source("family_substrate_current").get("expected_records")
    if expected_rows is not None and input_rows != int(expected_rows):
        raise ValidationError(
            f"Function mapping row drift: expected {expected_rows}, observed {input_rows}"
        )
    if int(expected_rows or 0) == 1023 and (len(grouped) != 390 or polyspecific != 88):
        raise ValidationError(
            "Function mapping derived-count drift: "
            f"families={len(grouped)} (expected 390), polyspecific={polyspecific} (expected 88)"
        )

    mapped_fungal = len(set(grouped) & fungal_families)
    summary = {
        "mapping_rows": input_rows,
        "mapping_physical_rows": physical_rows,
        "exact_duplicate_rows_removed": duplicate_rows,
        "normalized_rows": normalized_writer.count,
        "unique_families": len(grouped),
        "high_level_polyspecific_families": polyspecific,
        "fungal_2025_unique_families": len(fungal_families),
        "mapped_fungal_2025_families": mapped_fungal,
        "fungal_family_mapping_coverage": (
            mapped_fungal / len(fungal_families) if fungal_families else 0.0
        ),
        "protein_level_characterized_label_count": 0,
        "hard_function_evaluation_ready": False,
        "blocking_reason": "protein-level characterized substrate/EC table not found",
    }
    summary_path = json_dump_new(run.result_dir / "function_label_audit.json", summary)
    run.record_output("function_label_audit", summary_path, 1, list(summary))
    for key, value in summary.items():
        run.add_metric(f"function_{key}", value)
    return summary
