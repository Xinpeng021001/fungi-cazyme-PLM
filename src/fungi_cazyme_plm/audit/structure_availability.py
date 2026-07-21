"""Local CAZyme3D structure-reference availability audit."""

from __future__ import annotations

import csv
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..config import ProjectConfig
from ..data.fasta import iter_fasta, sequence_hashes
from ..data.identifiers import canonical_id, family_base, parse_cazy_header
from ..errors import DependencyError, ValidationError
from ..provenance import RunContext
from ..tableio import ArtifactTableWriter, json_dump_new


STRUCTURE_FIELDS = [
    "canonical_id",
    "genome_id",
    "original_id",
    "families",
    "sequence_sha256",
    "sequence_length",
    "cazyme3d_exact",
    "cazyme3d_near_90_80",
    "cazyme3d_accessions",
    "identity",
    "query_coverage",
    "target_coverage",
    "structure_source",
    "structure_kind",
    "experimental_pdb",
    "afdb_direct",
    "locally_predicted",
    "availability_status",
]

STRUCTURE_TYPES = {
    "sequence_length": "int64",
    "cazyme3d_exact": "bool",
    "cazyme3d_near_90_80": "bool",
    "identity": "float64",
    "query_coverage": "float64",
    "target_coverage": "float64",
    "experimental_pdb": "bool",
    "afdb_direct": "bool",
    "locally_predicted": "bool",
}


def _reference_hashes(path: Path) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = defaultdict(list)
    for header, sequence in iter_fasta(path):
        sha256, _ = sequence_hashes(sequence)
        mapping[sha256].append(header.split()[0])
    return dict(mapping)


def _run_mmseqs_search(
    config: ProjectConfig,
    run: RunContext,
    fungal_fasta: Path,
    reference_fasta: Path,
    threads: int,
) -> tuple[Path, dict[tuple[str, str], dict[str, Any]]]:
    configured = config.raw.get("tools", {}) if isinstance(config.raw.get("tools"), dict) else {}
    mmseqs = configured.get("mmseqs") or shutil.which("mmseqs")
    if not mmseqs:
        raise DependencyError("MMseqs2 is required for the ≥90%/≥80% structure audit")
    work_dir = run.result_dir / "structure_mmseqs_work"
    work_dir.mkdir(parents=True, exist_ok=False)
    output_path = run.result_dir / "cazyme3d_90_80.m8"
    identity_min = float(config.phase0.get("thresholds", {}).get("structure_identity_min", 0.90))
    coverage_min = float(config.phase0.get("thresholds", {}).get("structure_coverage_min", 0.80))
    command = [
        str(mmseqs),
        "easy-search",
        str(fungal_fasta),
        str(reference_fasta),
        str(output_path),
        str(work_dir),
        "--threads",
        str(threads),
        "--min-seq-id",
        str(identity_min),
        "-c",
        str(coverage_min),
        "--cov-mode",
        "0",
        "--max-seqs",
        "1",
        "--format-output",
        "query,target,fident,qcov,tcov,evalue,bits",
    ]
    print("[structures] running MMseqs2 90/80 search")
    proc = subprocess.run(command, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ValidationError(f"MMseqs structure search failed: {(proc.stderr or proc.stdout)[-2000:]}")
    matches: dict[tuple[str, str], dict[str, Any]] = {}
    if output_path.is_file():
        with output_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 7:
                    continue
                query, target, identity, qcov, tcov, evalue, bits = parts[:7]
                parsed = parse_cazy_header(query)
                fident = float(identity)
                if fident > 1.0:
                    fident /= 100.0
                key = (parsed.genome_id, parsed.original_id)
                matches[key] = {
                    "accession": target,
                    "identity": fident,
                    "query_coverage": float(qcov),
                    "target_coverage": float(tcov),
                    "evalue": float(evalue),
                    "bitscore": float(bits),
                }
    return output_path, matches


def audit_structure_availability(
    config: ProjectConfig,
    run: RunContext,
    with_mmseqs: bool = False,
    threads: int = 16,
) -> dict[str, Any]:
    fungal_fasta = config.source_path("cazy_fungi_2025")
    reference_fasta = config.source_path("cazyme3d_sequences")
    run.record_input("cazy_fungi_2025", fungal_fasta, schema="cazy_fasta")
    run.record_input("cazyme3d_sequences", reference_fasta, schema="protein_fasta")
    print("[structures] hashing 178,356 CAZyme3D ID50 reference sequences")
    reference_hashes = _reference_hashes(reference_fasta)
    near_matches: dict[tuple[str, str], dict[str, Any]] = {}
    mmseqs_output = None
    if with_mmseqs:
        mmseqs_output, near_matches = _run_mmseqs_search(
            config, run, fungal_fasta, reference_fasta, threads
        )
        run.record_output(
            "cazyme3d_90_80_matches_raw",
            mmseqs_output,
            len(near_matches),
            ["query", "target", "fident", "qcov", "tcov", "evalue", "bits"],
        )

    writer = ArtifactTableWriter(
        run.result_dir / "structure_availability",
        STRUCTURE_FIELDS,
        STRUCTURE_TYPES,
    )
    total = 0
    exact_count = 0
    near_count = 0
    no_local_count = 0
    for header, sequence in iter_fasta(fungal_fasta):
        total += 1
        if total % 100_000 == 0:
            print(f"[structures] audited {total:,} fungal CAZy records")
        parsed = parse_cazy_header(header)
        sha256, _ = sequence_hashes(sequence)
        exact_accessions = reference_hashes.get(sha256, [])
        near = near_matches.get((parsed.genome_id, parsed.original_id))
        exact = bool(exact_accessions)
        near_available = bool(near) and not exact
        exact_count += int(exact)
        near_count += int(near_available)
        no_local_count += int(not exact and not near)
        if exact:
            accessions = ";".join(exact_accessions)
            identity = 1.0
            qcov = 1.0
            tcov = 1.0
            status = "cazyme3d_exact"
        elif near:
            accessions = str(near["accession"])
            identity = near["identity"]
            qcov = near["query_coverage"]
            tcov = near["target_coverage"]
            status = "cazyme3d_90_80"
        else:
            accessions = ""
            identity = None
            qcov = None
            tcov = None
            status = "no_local_structure_reference"
        writer.write(
            {
                "canonical_id": canonical_id(parsed.genome_id, parsed.original_id, "cazy2025"),
                "genome_id": parsed.genome_id,
                "original_id": parsed.original_id,
                "families": ";".join(family_base(value) for value in parsed.families_raw),
                "sequence_sha256": sha256,
                "sequence_length": len(sequence),
                "cazyme3d_exact": exact,
                "cazyme3d_near_90_80": near_available,
                "cazyme3d_accessions": accessions,
                "identity": identity,
                "query_coverage": qcov,
                "target_coverage": tcov,
                "structure_source": "CAZyme3D_ID50" if (exact or near) else None,
                "structure_kind": "predicted_reference" if (exact or near) else None,
                "experimental_pdb": False,
                "afdb_direct": False,
                "locally_predicted": False,
                "availability_status": status,
            }
        )
    writer.close()
    run.record_output(
        "structure_availability_tsv", writer.tsv_path, writer.count, STRUCTURE_FIELDS
    )
    if writer.parquet_path.exists():
        run.record_output(
            "structure_availability_parquet", writer.parquet_path, writer.count, STRUCTURE_FIELDS
        )
    expected = config.source("cazy_fungi_2025").get("expected_records")
    if expected is not None and total != int(expected):
        raise ValidationError(
            f"Fungal structure audit row drift: expected {expected}, observed {total}"
        )
    summary = {
        "fungal_cazy_records": total,
        "cazyme3d_reference_records": sum(len(values) for values in reference_hashes.values()),
        "cazyme3d_unique_sequence_hashes": len(reference_hashes),
        "exact_sequence_matches": exact_count,
        "near_90_80_matches_excluding_exact": near_count,
        "local_structure_reference_total": exact_count + near_count,
        "local_structure_reference_coverage": (
            (exact_count + near_count) / total if total else 0.0
        ),
        "no_local_structure_reference": no_local_count,
        "near_search_status": "completed" if with_mmseqs else "not_run",
        "experimental_pdb_coverage": None,
        "afdb_direct_coverage": None,
        "source_separation_enforced": True,
        "bulk_structure_prediction_run": False,
    }
    summary_path = json_dump_new(run.result_dir / "structure_availability.json", summary)
    run.record_output("structure_availability_summary", summary_path, 1, list(summary))
    for key, value in summary.items():
        run.add_metric(f"structure_{key}", value)
    return summary

