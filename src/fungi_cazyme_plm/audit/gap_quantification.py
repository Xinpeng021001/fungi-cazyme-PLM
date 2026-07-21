"""Fungal CAZy versus dbCAN HMM gap classification."""

from __future__ import annotations

import csv
import json
import math
import shutil
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Any, Iterable

from ..config import ProjectConfig
from ..errors import ValidationError
from ..provenance import RunContext
from ..tableio import ArtifactTableWriter, json_dump_new, read_tsv
from ..data.identifiers import (
    canonical_id,
    cazy_class,
    family_base,
    format_annotation,
    genome_from_filename,
    is_fam0,
    parse_jgi_header,
    split_annotation,
)


GAP_FIELDS = [
    "canonical_id",
    "genome_id",
    "expected_families",
    "predicted_families",
    "primary_error",
    "family_error",
    "error_flags",
    "family_base",
    "cazy_class",
    "family_size_bin",
    "hmm_present",
    "best_i_evalue",
    "best_coverage",
    "best_bitscore",
    "nearest_seed_identity",
    "seed_query_coverage",
    "seed_target_coverage",
    "seed_reference_release",
    "taxonomy_order",
    "sequence_quality",
    "boundary_assessment",
    "source_release",
    "dbcan_release",
]

GAP_TYPES = {
    "hmm_present": "bool",
    "best_i_evalue": "float64",
    "best_coverage": "float64",
    "best_bitscore": "float64",
    "nearest_seed_identity": "float64",
    "seed_query_coverage": "float64",
    "seed_target_coverage": "float64",
}


@dataclass(frozen=True)
class RawHit:
    i_evalue: float
    coverage: float
    bitscore: float


def _require_columns(path: Path, observed: Iterable[str], required: set[str]) -> None:
    missing = required - {value.strip() for value in observed}
    if missing:
        raise ValidationError(f"{path} is missing required columns: {sorted(missing)}")


def load_hmm_families(path: Path) -> set[str]:
    families = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("NAME"):
                parts = line.split()
                if len(parts) >= 2:
                    families.add(family_base(parts[1]))
    if not families:
        raise ValidationError(f"No HMM NAME records found in {path}")
    return families


def count_hmm_models(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("NAME") and len(line.split()) >= 2:
                count += 1
    if count == 0:
        raise ValidationError(f"No HMM NAME records found in {path}")
    return count


def load_family_support(path: Path) -> dict[str, int]:
    support: dict[str, int] = {}
    for row in read_tsv(path):
        family = family_base(row.get("family", ""))
        raw = row.get("n_true", "")
        if family and raw not in {"", "NA", "-"}:
            support[family] = int(float(raw))
    return support


def load_raw_hits(path: Path) -> dict[tuple[str, str, str], RawHit]:
    required = {"family", "protein_id", "genome", "i_evalue", "coverage", "bitscore"}
    best: dict[tuple[str, str, str], RawHit] = {}
    rows = read_tsv(path)
    try:
        first = next(rows)
    except StopIteration as exc:
        raise ValidationError(f"Empty raw hit table: {path}") from exc
    _require_columns(path, first.keys(), required)

    def consume(row: dict[str, str]) -> None:
        key = (row["genome"], row["protein_id"], family_base(row["family"]))
        hit = RawHit(float(row["i_evalue"]), float(row["coverage"]), float(row["bitscore"]))
        previous = best.get(key)
        if previous is None or hit.bitscore > previous.bitscore:
            best[key] = hit

    consume(first)
    for row in rows:
        consume(row)
    return best


def load_post_overlap_calls(config: ProjectConfig) -> set[tuple[str, str, str]]:
    root = config.source_path("aim2_dbcan_results")
    pattern = config.source("aim2_dbcan_results").get("include", "*/dbCAN_hmm_results.tsv")
    calls: set[tuple[str, str, str]] = set()
    required = {"HMM Name", "Target Name"}
    for path in sorted(root.glob(pattern)):
        if not path.is_file():
            continue
        fallback_genome = genome_from_filename(path.parent.name.removesuffix(".dbcan"))
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t", quoting=csv.QUOTE_NONE)
            _require_columns(path, reader.fieldnames or [], required)
            for row in reader:
                parsed = parse_jgi_header(row["Target Name"], fallback_genome)
                calls.add(
                    (parsed.genome_id, parsed.original_id, family_base(row["HMM Name"]))
                )
    return calls


def _family_size_bin(family: str, support: dict[str, int], config: ProjectConfig) -> str:
    size = support.get(family, 0)
    for item in config.phase0.get("family_size_bins", []):
        minimum = int(item.get("min", 0))
        maximum = item.get("max")
        if size >= minimum and (maximum is None or size <= int(maximum)):
            return str(item["label"])
    return "unknown"


def classify_primary(expected: Counter[str], predicted: Counter[str], hmm_models: set[str]) -> str:
    if expected and any(family not in hmm_models or is_fam0(family) for family in expected):
        return "hmm_model_absent"
    if expected and not predicted:
        return "missed_entirely"
    if expected and predicted and not (set(expected) & set(predicted)):
        return "wrong_family"
    if expected and predicted and expected != predicted:
        return "incomplete_domain_set"
    if not expected and predicted:
        return "overcall_only"
    return "concordant"


def _family_error(family: str, expected: Counter[str], predicted: Counter[str]) -> str:
    exp = expected.get(family, 0)
    pred = predicted.get(family, 0)
    matched = min(exp, pred)
    if exp and pred and exp == pred:
        return "matched"
    if exp and pred and matched:
        return "partial"
    if exp and not pred:
        return "false_negative"
    if pred and not exp:
        return "false_positive"
    return "absent"


def borderline_flags(
    hit: RawHit,
    default_evalue: float = 1e-15,
    default_coverage: float = 0.35,
    borderline_evalue_max: float = 1e-13,
    borderline_coverage_min: float = 0.25,
) -> set[str]:
    """Apply the pre-registered inclusive/exclusive threshold boundaries."""

    flags: set[str] = set()
    if default_evalue < hit.i_evalue <= borderline_evalue_max and hit.coverage >= default_coverage:
        flags.add("borderline_evalue")
    if hit.i_evalue <= default_evalue and borderline_coverage_min <= hit.coverage < default_coverage:
        flags.add("borderline_coverage")
    return flags


def wilson_interval(successes: int, total: int, confidence: float = 0.95) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 0.0)
    alpha = 1.0 - confidence
    z = NormalDist().inv_cdf(1.0 - alpha / 2.0)
    proportion = successes / total
    denominator = 1.0 + (z * z / total)
    centre = proportion + (z * z / (2.0 * total))
    spread = z * math.sqrt(
        proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total)
    )
    return ((centre - spread) / denominator, (centre + spread) / denominator)


def _load_seed_identity(path: Path | None) -> dict[tuple[str, str, str], dict[str, float]]:
    if path is None or not path.is_file():
        return {}
    result = {}
    for row in read_tsv(path):
        key = (row["genome_id"], row["original_id"], family_base(row["family_base"]))
        result[key] = {
            "identity": float(row["identity"]),
            "query_coverage": float(row["query_coverage"]),
            "target_coverage": float(row["target_coverage"]),
        }
    return result


def _load_taxonomy_orders(config: ProjectConfig) -> dict[str, str]:
    metadata_path = config.source_path("mycocosm_metadata")
    genome_taxids: dict[str, str] = {}
    with metadata_path.open("r", encoding="latin-1", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("portal") and row.get("NCBI Taxon"):
                genome_taxids[row["portal"]] = row["NCBI Taxon"]
    tool = config.raw.get("tools", {}).get("taxonkit") if isinstance(config.raw.get("tools"), dict) else None
    executable = tool or shutil.which("taxonkit")
    if not executable:
        return {}
    unique_taxids = sorted(set(genome_taxids.values()))
    proc = subprocess.run(
        [str(executable), "reformat", "-I", "1", "-f", "{o}"],
        input="\n".join(unique_taxids) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return {}
    taxid_order: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            taxid_order[parts[0]] = parts[-1] if parts[-1] != "" else "unresolved"
    return {genome: taxid_order.get(taxid, "unresolved") for genome, taxid in genome_taxids.items()}


def quantify_gap(
    config: ProjectConfig,
    run: RunContext,
    seed_identity_path: Path | None = None,
    reconstruct_overlap: bool = True,
) -> dict[str, Any]:
    comparison_path = config.source_path("aim2_protein_comparison")
    hits_path = config.source_path("aim2_hits")
    family_eval_path = config.source_path("aim2_family_evaluation")
    hmm_path = config.source_path("dbcan_hmm_current")
    for source_id, path, schema in (
        ("aim2_protein_comparison", comparison_path, "aim2_protein_comparison"),
        ("aim2_hits", hits_path, "aim2_hits"),
        ("aim2_family_evaluation", family_eval_path, "aim2_family_evaluation"),
        ("dbcan_hmm_current", hmm_path, "hmmer3"),
    ):
        run.record_input(source_id, path, schema=schema)

    print("[gap] loading HMM families and per-family support")
    hmm_models = load_hmm_families(hmm_path)
    family_support = load_family_support(family_eval_path)
    print("[gap] loading 1.63M raw HMM score rows")
    raw_hits = load_raw_hits(hits_path)
    print(f"[gap] loaded {len(raw_hits):,} best protein-family raw hits")
    post_overlap = load_post_overlap_calls(config) if reconstruct_overlap else set()
    seed_identity = _load_seed_identity(seed_identity_path)
    taxonomy_orders = _load_taxonomy_orders(config)

    thresholds = config.phase0.get("thresholds", {})
    default_evalue = float(thresholds.get("default_i_evalue", 1e-15))
    default_coverage = float(thresholds.get("default_hmm_coverage", 0.35))
    borderline_evalue_max = float(thresholds.get("borderline_i_evalue_max", 1e-13))
    borderline_coverage_min = float(thresholds.get("borderline_coverage_min", 0.25))
    versions = config.phase0.get("versions", {})

    writer = ArtifactTableWriter(run.result_dir / "gap_cases", GAP_FIELDS, GAP_TYPES)
    protein_primary = Counter()
    family_stats: dict[str, Counter[str]] = defaultdict(Counter)
    class_stats: dict[str, Counter[str]] = defaultdict(Counter)
    size_stats: dict[str, Counter[str]] = defaultdict(Counter)
    order_stats: dict[str, Counter[str]] = defaultdict(Counter)
    truth_instances = 0
    matched_instances = 0
    unmatched_instances = 0
    addressable_instances = 0
    comparison_rows = 0
    source_rows = 0
    malformed_rows = 0
    comparison_genomes: set[str] = set()

    rows = read_tsv(comparison_path)
    try:
        first = next(rows)
    except StopIteration as exc:
        raise ValidationError(f"Empty protein comparison table: {comparison_path}") from exc
    required = {"protein_id", "genome", "cazy_annotation", "dbcan_annotation", "result"}
    _require_columns(comparison_path, first.keys(), required)

    def consume(row: dict[str, str]) -> None:
        nonlocal truth_instances, matched_instances, unmatched_instances, addressable_instances
        nonlocal comparison_rows, source_rows, malformed_rows
        source_rows += 1
        if row.get("protein_id") == "protein_id" and row.get("genome") == "genome":
            malformed_rows += 1
            return
        comparison_rows += 1
        if comparison_rows % 250_000 == 0:
            print(f"[gap] classified {comparison_rows:,} protein rows")
        genome = row["genome"]
        comparison_genomes.add(genome)
        original_id = row["protein_id"]
        expected = split_annotation(row["cazy_annotation"], base_only=True)
        predicted = split_annotation(row["dbcan_annotation"], base_only=True)
        primary = classify_primary(expected, predicted, hmm_models)
        protein_primary[primary] += 1
        truth_instances += sum(expected.values())
        for family, expected_count in expected.items():
            matched = min(expected_count, predicted.get(family, 0))
            unmatched = expected_count - matched
            matched_instances += matched
            unmatched_instances += unmatched
            eligible = family in hmm_models and not is_fam0(family)
            if eligible:
                addressable_instances += unmatched
            family_stats[family]["truth"] += expected_count
            family_stats[family]["matched"] += matched
            family_stats[family]["unmatched"] += unmatched
            family_stats[family]["addressable"] += unmatched if eligible else 0
            klass = cazy_class(family)
            size_bin = _family_size_bin(family, family_support, config)
            order = taxonomy_orders.get(genome, "unresolved")
            for stats, group in (
                (class_stats, klass),
                (size_stats, size_bin),
                (order_stats, order),
            ):
                stats[group]["truth"] += expected_count
                stats[group]["matched"] += matched
                stats[group]["unmatched"] += unmatched
                stats[group]["addressable"] += unmatched if eligible else 0

        families = sorted(set(expected) | set(predicted))
        for family in families:
            raw = raw_hits.get((genome, original_id, family))
            hmm_present = family in hmm_models and not is_fam0(family)
            flags = {"boundary_not_evaluable"}
            family_error = _family_error(family, expected, predicted)
            if family_error in {"false_negative", "partial"} and raw is not None:
                flags.update(
                    borderline_flags(
                        raw,
                        default_evalue,
                        default_coverage,
                        borderline_evalue_max,
                        borderline_coverage_min,
                    )
                )
                if (
                    reconstruct_overlap
                    and raw.i_evalue <= default_evalue
                    and raw.coverage >= default_coverage
                    and (genome, original_id, family) not in post_overlap
                ):
                    flags.add("overlap_filter_loss")
            if sum(expected.values()) >= 2 and expected != predicted:
                flags.add("multi_domain_incomplete")
            if is_fam0(family):
                flags.add("fam0_open_set")
            seed = seed_identity.get((genome, original_id, family), {})
            writer.write(
                {
                    "canonical_id": canonical_id(genome, original_id),
                    "genome_id": genome,
                    "expected_families": format_annotation(expected),
                    "predicted_families": format_annotation(predicted),
                    "primary_error": primary,
                    "family_error": family_error,
                    "error_flags": ";".join(sorted(flags)),
                    "family_base": family,
                    "cazy_class": cazy_class(family),
                    "family_size_bin": _family_size_bin(family, family_support, config),
                    "hmm_present": hmm_present,
                    "best_i_evalue": raw.i_evalue if raw else None,
                    "best_coverage": raw.coverage if raw else None,
                    "best_bitscore": raw.bitscore if raw else None,
                    "nearest_seed_identity": seed.get("identity"),
                    "seed_query_coverage": seed.get("query_coverage"),
                    "seed_target_coverage": seed.get("target_coverage"),
                    "seed_reference_release": versions.get("seed_reference_release")
                    if seed
                    else None,
                    "taxonomy_order": taxonomy_orders.get(genome),
                    "sequence_quality": "not_audited",
                    "boundary_assessment": "not_evaluable_no_independent_gold",
                    "source_release": versions.get("cazy_truth_release", "unknown"),
                    "dbcan_release": versions.get("dbcan_release", "unknown"),
                }
            )

    consume(first)
    for row in rows:
        consume(row)
    writer.close()
    run.record_output("gap_cases_tsv", writer.tsv_path, writer.count, GAP_FIELDS)
    if writer.parquet_path.exists():
        run.record_output("gap_cases_parquet", writer.parquet_path, writer.count, GAP_FIELDS)
    run.record_output("gap_cases_metadata", writer.metadata_path, 1, ["rows", "columns"])

    expected_records = config.source("aim2_protein_comparison").get("expected_records")
    if expected_records is not None and source_rows != int(expected_records):
        raise ValidationError(
            f"Protein comparison source-row drift: expected {expected_records}, observed {source_rows}"
        )
    expected_malformed = int(
        config.source("aim2_protein_comparison").get("known_malformed_rows", 0)
    )
    if malformed_rows != expected_malformed:
        raise ValidationError(
            f"Protein comparison malformed-row drift: expected {expected_malformed}, "
            f"observed {malformed_rows}"
        )

    confidence = float(config.phase0.get("go_no_go", {}).get("confidence_level", 0.95))
    rate = addressable_instances / truth_instances if truth_instances else 0.0
    lower, upper = wilson_interval(addressable_instances, truth_instances, confidence)
    threshold = float(
        config.phase0.get("go_no_go", {}).get("addressable_error_threshold", 0.05)
    )
    if upper < threshold:
        gate = "pivot_to_function_decoder"
    elif lower > threshold:
        gate = "continue_family_structure_claims"
    else:
        gate = "manual_review_required"

    summary_fields = [
        "dimension",
        "group",
        "protein_cases",
        "truth_instances",
        "matched_instances",
        "unmatched_instances",
        "addressable_instances",
        "addressable_error_rate",
    ]
    summary_path = run.result_dir / "gap_summary.tsv"
    with summary_path.open("x", encoding="utf-8", newline="") as handle:
        output = csv.DictWriter(
            handle, fieldnames=summary_fields, delimiter="\t", lineterminator="\n"
        )
        output.writeheader()
        output.writerow(
            {
                "dimension": "overall",
                "group": "all",
                "protein_cases": comparison_rows,
                "truth_instances": truth_instances,
                "matched_instances": matched_instances,
                "unmatched_instances": unmatched_instances,
                "addressable_instances": addressable_instances,
                "addressable_error_rate": f"{rate:.8f}",
            }
        )
        for group, count in sorted(protein_primary.items()):
            output.writerow(
                {"dimension": "primary_error", "group": group, "protein_cases": count}
            )
        for dimension, stats in (
            ("family", family_stats),
            ("class", class_stats),
            ("family_size_bin", size_stats),
            ("taxonomy_order", order_stats),
        ):
            for group, values in sorted(stats.items()):
                output.writerow(
                    {
                        "dimension": dimension,
                        "group": group,
                        "truth_instances": values["truth"],
                        "matched_instances": values["matched"],
                        "unmatched_instances": values["unmatched"],
                        "addressable_instances": values["addressable"],
                        "addressable_error_rate": (
                            f"{values['addressable'] / values['truth']:.8f}"
                            if values["truth"]
                            else ""
                        ),
                    }
                )
    run.record_output("gap_summary", summary_path, None, summary_fields)

    metrics = {
        "source_comparison_rows": source_rows,
        "comparison_rows": comparison_rows,
        "known_malformed_rows_excluded": malformed_rows,
        "gap_case_rows": writer.count,
        "hmm_model_count": count_hmm_models(hmm_path),
        "hmm_base_family_count": len(hmm_models),
        "raw_best_hit_count": len(raw_hits),
        "post_overlap_call_count": len(post_overlap),
        "comparison_genome_count": len(comparison_genomes),
        "taxonomy_order_resolved_genomes": sum(
            taxonomy_orders.get(genome) not in {None, "", "unresolved"}
            for genome in comparison_genomes
        ),
        "truth_family_instances": truth_instances,
        "matched_family_instances": matched_instances,
        "unmatched_family_instances": unmatched_instances,
        "preliminary_addressable_instances": addressable_instances,
        "preliminary_addressable_error_rate": rate,
        "addressable_error_ci_lower": lower,
        "addressable_error_ci_upper": upper,
        "go_no_go_threshold": threshold,
        "preliminary_gate": gate,
        "primary_error_counts": dict(sorted(protein_primary.items())),
        "seed_identity_rows": len(seed_identity),
        "boundary_gold_available": False,
    }
    metrics_path = json_dump_new(run.result_dir / "gap_metrics.json", metrics)
    run.record_output("gap_metrics", metrics_path, 1, list(metrics))
    for key, value in metrics.items():
        run.add_metric(f"gap_{key}", value)
    return metrics
