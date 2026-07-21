"""Read-only normalization of the existing fungi/dbCAN Aim2 evaluation."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from ..config import ProjectConfig
from ..errors import ValidationError
from ..provenance import RunContext
from ..tableio import ArtifactTableWriter, json_dump_new, read_tsv
from .fasta import iter_fasta, sequence_hashes
from .identifiers import (
    canonical_id,
    cazy_class,
    family_base,
    genome_from_filename,
    parse_jgi_header,
    resolve_genome_alias,
)


FAMILY_METRIC_REQUIRED = {
    "family",
    "n_true",
    "recall_default",
    "precision_default",
    "health",
    "auprc",
    "verdict",
    "rec_bit_cutoff",
    "heldout_F1_gain",
    "generalizes",
}
COMPARISON_REQUIRED = {
    "protein_id",
    "genome",
    "cazy_annotation",
    "dbcan_annotation",
    "result",
}
HMM_RESULT_REQUIRED = {
    "HMM Name",
    "HMM Length",
    "Target Name",
    "Target Length",
    "i-Evalue",
    "Target From",
    "Target To",
    "Coverage",
}


def valid_1based_inclusive(start: int, end: int, sequence_length: int) -> bool:
    return start >= 1 and end >= start and end <= sequence_length


def _require_columns(path: Path, observed: Iterable[str], required: set[str]) -> None:
    missing = required - {value.strip() for value in observed}
    if missing:
        raise ValidationError(f"{path} is missing required columns: {sorted(missing)}")


def _record_table(run: RunContext, artifact_id: str, writer: ArtifactTableWriter) -> None:
    columns = writer.fieldnames
    run.record_output(f"{artifact_id}_tsv", writer.tsv_path, writer.count, columns)
    if writer.parquet_path.exists():
        run.record_output(f"{artifact_id}_parquet", writer.parquet_path, writer.count, columns)
    run.record_output(f"{artifact_id}_metadata", writer.metadata_path, 1, ["rows", "columns"])


def import_family_metrics(config: ProjectConfig, run: RunContext) -> dict[str, Any]:
    path = config.source_path("aim2_family_evaluation")
    run.record_input("aim2_family_evaluation", path, schema="aim2_family_evaluation")
    rows = read_tsv(path)
    try:
        first = next(rows)
    except StopIteration as exc:
        raise ValidationError(f"Empty family evaluation table: {path}") from exc
    _require_columns(path, first.keys(), FAMILY_METRIC_REQUIRED)
    source_fields = list(first.keys())
    fields = [*source_fields, "family_base", "cazy_class", "source_release", "dbcan_release"]
    numeric_float = {
        "recall_default",
        "recall_hi",
        "precision_default",
        "precision_hi",
        "health",
        "auprc",
        "priority",
        "rec_bit_cutoff",
        "rec_cov_cutoff",
        "heldout_recall_default",
        "heldout_precision_default",
        "heldout_F1_default",
        "heldout_recall_tuned",
        "heldout_precision_tuned",
        "heldout_F1_tuned",
        "heldout_F1_gain",
    }
    numeric_int = {"n_true", "hmm_len"}
    types = {name: "float64" for name in numeric_float if name in fields}
    types.update({name: "int64" for name in numeric_int if name in fields})
    writer = ArtifactTableWriter(run.result_dir / "family_metrics", fields, types)
    counts = defaultdict(int)

    def emit(row: dict[str, str]) -> None:
        normalized: dict[str, Any] = dict(row)
        for name in numeric_float:
            if name in normalized:
                normalized[name] = _float_or_none(normalized[name])
        for name in numeric_int:
            if name in normalized:
                normalized[name] = _int_or_none(normalized[name])
        base = family_base(row.get("family", ""))
        normalized.update(
            {
                "family_base": base,
                "cazy_class": cazy_class(base),
                "source_release": "2026-07-19",
                "dbcan_release": config.phase0.get("versions", {}).get("dbcan_release", "unknown"),
            }
        )
        writer.write(normalized)
        verdict = row.get("verdict", "NA").split(" [", 1)[0] or "NA"
        counts[verdict] += 1

    emit(first)
    for row in rows:
        emit(row)
    writer.close()
    _record_table(run, "family_metrics", writer)
    return {"rows": writer.count, "verdict_counts": dict(sorted(counts.items()))}


def _float_or_none(value: str | None) -> float | None:
    if value is None or value.strip() in {"", "NA", "-"}:
        return None
    return float(value)


def _int_or_none(value: str | None) -> int | None:
    if value is None or value.strip() in {"", "NA", "-"}:
        return None
    return int(float(value))


def validate_mycocosm_genomes(config: ProjectConfig, run: RunContext) -> dict[str, Any]:
    metadata_path = config.source_path("mycocosm_metadata")
    support_path = config.source_path("aim2_genome_support")
    run.record_input("mycocosm_metadata", metadata_path, schema="mycocosm_metadata")
    run.record_input("aim2_genome_support", support_path, schema="aim2_genome_support")

    metadata: dict[str, dict[str, str]] = {}
    with metadata_path.open("r", encoding="latin-1", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "portal" not in reader.fieldnames:
            raise ValidationError("MycoCosm metadata is missing the portal column")
        for row in reader:
            metadata[row["portal"]] = row
    genomes = set()
    for row in read_tsv(support_path):
        if row.get("genome"):
            genomes.add(row["genome"])

    fields = [
        "genome_id",
        "name",
        "ncbi_taxon",
        "is_public",
        "is_published",
        "is_restricted",
        "publication",
        "validation_status",
    ]
    writer = ArtifactTableWriter(run.result_dir / "mycocosm_genomes", fields)
    missing: list[str] = []
    unpublished: list[str] = []
    restricted: list[str] = []
    for genome in sorted(genomes):
        row = metadata.get(genome)
        if row is None:
            missing.append(genome)
            writer.write({"genome_id": genome, "validation_status": "missing_metadata"})
            continue
        if row.get("is published") != "Y":
            unpublished.append(genome)
        if row.get("is restricted") != "N":
            restricted.append(genome)
        writer.write(
            {
                "genome_id": genome,
                "name": row.get("name"),
                "ncbi_taxon": row.get("NCBI Taxon"),
                "is_public": row.get("is public"),
                "is_published": row.get("is published"),
                "is_restricted": row.get("is restricted"),
                "publication": row.get("publication(s)"),
                "validation_status": "ok",
            }
        )
    writer.close()
    _record_table(run, "mycocosm_genomes", writer)
    if missing or unpublished or restricted:
        raise ValidationError(
            "MycoCosm policy validation failed: "
            f"missing={len(missing)}, unpublished={len(unpublished)}, restricted={len(restricted)}"
        )
    return {
        "evaluated_genomes": len(genomes),
        "metadata_matched": len(genomes) - len(missing),
        "published": len(genomes) - len(unpublished),
        "non_restricted": len(genomes) - len(restricted),
    }


def _wanted_comparison_ids(path: Path) -> dict[str, set[str]]:
    wanted: dict[str, set[str]] = defaultdict(set)
    rows = read_tsv(path)
    try:
        first = next(rows)
    except StopIteration as exc:
        raise ValidationError(f"Empty protein comparison: {path}") from exc
    _require_columns(path, first.keys(), COMPARISON_REQUIRED)
    if not _is_malformed_comparison_row(first):
        wanted[first["genome"]].add(first["protein_id"])
    for row in rows:
        if not _is_malformed_comparison_row(row):
            wanted[row["genome"]].add(row["protein_id"])
    return wanted


def _is_malformed_comparison_row(row: dict[str, str]) -> bool:
    return row.get("protein_id") == "protein_id" and row.get("genome") == "genome"


def import_protein_aliases(config: ProjectConfig, run: RunContext) -> dict[str, Any]:
    comparison_path = config.source_path("aim2_protein_comparison")
    proteome_dir = config.source_path("aim2_proteomes")
    run.record_input("aim2_protein_comparison", comparison_path, schema="aim2_protein_comparison")
    run.record_input("aim2_proteomes", proteome_dir, schema="protein_fasta_directory", digest="directory")
    wanted = _wanted_comparison_ids(comparison_path)
    total_wanted = sum(len(values) for values in wanted.values())
    fields = [
        "canonical_id",
        "genome_id",
        "original_id",
        "dbcan_gene_id",
        "source_database",
        "sequence_sha256",
        "legacy_seq_md5",
        "sequence_length",
        "join_method",
        "join_confidence",
    ]
    types = {"sequence_length": "int64"}
    writer = ArtifactTableWriter(run.result_dir / "protein_aliases", fields, types)
    found: dict[str, set[str]] = defaultdict(set)
    conflict_fields = [
        "canonical_id",
        "kept_observed_genome_id",
        "kept_dbcan_gene_id",
        "kept_sequence_sha256",
        "conflicting_observed_genome_id",
        "conflicting_dbcan_gene_id",
        "conflicting_sequence_sha256",
        "sequences_equal",
    ]
    conflict_writer = ArtifactTableWriter(
        run.result_dir / "protein_alias_conflicts",
        conflict_fields,
        {"sequences_equal": "bool"},
    )
    known_genomes = set(wanted)
    resolved_files: list[tuple[int, Path, str, str]] = []
    for path in (candidate for candidate in proteome_dir.iterdir() if candidate.is_file()):
        observed = genome_from_filename(path.name)
        logical, method = resolve_genome_alias(observed, known_genomes)
        if logical is not None:
            priority = 0 if method == "exact_genome_id" else 1
            resolved_files.append((priority, path, logical, method))
    resolved_files.sort(key=lambda item: (item[0], item[1].name))
    logical_file_counts = Counter(item[2] for item in resolved_files)
    collision_candidates = {
        genome for genome, count in logical_file_counts.items() if count > 1
    }
    first_details: dict[tuple[str, str], tuple[str, str, str]] = {}
    for index, (_, path, logical_genome, genome_join_method) in enumerate(resolved_files, 1):
        fallback_genome = genome_from_filename(path.name)
        target_ids = wanted.get(logical_genome)
        if not target_ids:
            continue
        if index % 100 == 0:
            print(f"[import-aim2] aliases: {index}/{len(resolved_files)} proteomes")
        for header, sequence in iter_fasta(path):
            parsed = parse_jgi_header(header, fallback_genome)
            if parsed.original_id not in target_ids:
                continue
            sha256, md5 = sequence_hashes(sequence)
            dbcan_id = "jgi-" + parsed.raw_id.removeprefix("jgi|").replace("|", "-")
            cid = canonical_id(logical_genome, parsed.original_id)
            detail_key = (logical_genome, parsed.original_id)
            if parsed.original_id in found[logical_genome]:
                kept = first_details[detail_key]
                conflict_writer.write(
                    {
                        "canonical_id": cid,
                        "kept_observed_genome_id": kept[0],
                        "kept_dbcan_gene_id": kept[1],
                        "kept_sequence_sha256": kept[2],
                        "conflicting_observed_genome_id": parsed.genome_id,
                        "conflicting_dbcan_gene_id": dbcan_id,
                        "conflicting_sequence_sha256": sha256,
                        "sequences_equal": kept[2] == sha256,
                    }
                )
                continue
            writer.write(
                {
                    "canonical_id": cid,
                    "genome_id": logical_genome,
                    "original_id": parsed.original_id,
                    "dbcan_gene_id": dbcan_id,
                    "source_database": "JGI_MycoCosm",
                    "sequence_sha256": sha256,
                    "legacy_seq_md5": md5,
                    "sequence_length": len(sequence),
                    "join_method": f"{genome_join_method}+exact_original_id",
                    "join_confidence": (
                        "exact" if genome_join_method == "exact_genome_id" else "high"
                    ),
                }
            )
            found[logical_genome].add(parsed.original_id)
            if logical_genome in collision_candidates:
                first_details[detail_key] = (parsed.genome_id, dbcan_id, sha256)
    writer.close()
    conflict_writer.close()
    _record_table(run, "protein_aliases", writer)
    _record_table(run, "protein_alias_conflicts", conflict_writer)

    missing_rows = []
    for genome, ids in wanted.items():
        for original_id in sorted(ids - found.get(genome, set())):
            missing_rows.append((genome, original_id))
    missing_path = run.result_dir / "protein_aliases_unmatched.tsv"
    with missing_path.open("x", encoding="utf-8", newline="") as handle:
        output = csv.writer(handle, delimiter="\t", lineterminator="\n")
        output.writerow(["genome_id", "original_id"])
        output.writerows(missing_rows)
    run.record_output(
        "protein_aliases_unmatched",
        missing_path,
        len(missing_rows),
        ["genome_id", "original_id"],
    )
    if missing_rows or conflict_writer.count:
        raise ValidationError(
            "Protein alias validation failed: "
            f"missing={len(missing_rows)} of {total_wanted}, "
            f"duplicate_conflicts={conflict_writer.count}"
        )
    return {
        "wanted": total_wanted,
        "matched": writer.count,
        "unmatched": 0,
        "duplicate_conflicts": 0,
    }


def import_weak_domains(config: ProjectConfig, run: RunContext) -> dict[str, Any]:
    root = config.source_path("aim2_dbcan_results")
    spec = config.source("aim2_dbcan_results")
    paths = sorted(path for path in root.glob(spec.get("include", "*/dbCAN_hmm_results.tsv")) if path.is_file())
    expected_files = spec.get("expected_files")
    if expected_files is not None and len(paths) != int(expected_files):
        raise ValidationError(f"Expected {expected_files} HMM result files, found {len(paths)}")
    run.record_input("aim2_dbcan_results", root, schema="dbcan_hmm_results", digest="directory")
    fields = [
        "canonical_id",
        "domain_index",
        "start_1based",
        "end_1based_inclusive",
        "family_raw",
        "family_base",
        "cazy_class",
        "i_evalue",
        "bitscore",
        "hmm_coverage",
        "boundary_source",
        "evidence_type",
        "dbcan_version",
    ]
    types = {
        "domain_index": "int64",
        "start_1based": "int64",
        "end_1based_inclusive": "int64",
        "i_evalue": "float64",
        "bitscore": "float64",
        "hmm_coverage": "float64",
    }
    writer = ArtifactTableWriter(run.result_dir / "domains_weak", fields, types)
    invalid_coordinates = 0
    for file_index, path in enumerate(paths, 1):
        if file_index % 100 == 0:
            print(f"[import-aim2] weak domains: {file_index}/{len(paths)} files")
        fallback_genome = genome_from_filename(path.parent.name.removesuffix(".dbcan"))
        counters: dict[str, int] = defaultdict(int)
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t", quoting=csv.QUOTE_NONE)
            _require_columns(path, reader.fieldnames or [], HMM_RESULT_REQUIRED)
            for row in reader:
                parsed = parse_jgi_header(row["Target Name"], fallback_genome)
                start = int(row["Target From"])
                end = int(row["Target To"])
                target_length = int(row["Target Length"])
                if not valid_1based_inclusive(start, end, target_length):
                    invalid_coordinates += 1
                    continue
                cid = canonical_id(parsed.genome_id, parsed.original_id)
                counters[cid] += 1
                raw_family = row["HMM Name"].removesuffix(".hmm")
                base = family_base(raw_family)
                writer.write(
                    {
                        "canonical_id": cid,
                        "domain_index": counters[cid],
                        "start_1based": start,
                        "end_1based_inclusive": end,
                        "family_raw": raw_family,
                        "family_base": base,
                        "cazy_class": cazy_class(base),
                        "i_evalue": float(row["i-Evalue"]),
                        "bitscore": None,
                        "hmm_coverage": float(row["Coverage"]),
                        "boundary_source": "dbcan_hmm_envelope",
                        "evidence_type": "weak_supervision",
                        "dbcan_version": config.phase0.get("versions", {}).get(
                            "dbcan_release", "unknown"
                        ),
                    }
                )
    writer.close()
    _record_table(run, "domains_weak", writer)
    if invalid_coordinates:
        raise ValidationError(f"Found {invalid_coordinates} invalid HMM envelope coordinates")
    return {"files": len(paths), "domains": writer.count, "invalid_coordinates": 0}


def import_aim2(
    config: ProjectConfig,
    run: RunContext,
    include_aliases: bool = True,
    include_domains: bool = True,
) -> dict[str, Any]:
    """Normalize all selected Aim2 artifacts into the immutable run directory."""

    summary: dict[str, Any] = {
        "family_metrics": import_family_metrics(config, run),
        "mycocosm": validate_mycocosm_genomes(config, run),
    }
    if include_aliases:
        summary["protein_aliases"] = import_protein_aliases(config, run)
    else:
        summary["protein_aliases"] = {"status": "skipped"}
    if include_domains:
        summary["domains_weak"] = import_weak_domains(config, run)
    else:
        summary["domains_weak"] = {"status": "skipped"}
    summary_path = json_dump_new(run.result_dir / "aim2_import_summary.json", summary)
    run.record_output("aim2_import_summary", summary_path, 1, list(summary))
    for key, value in summary.items():
        run.add_metric(f"aim2_{key}", value)
    return summary
