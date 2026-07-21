"""Version-labelled identity to the available 2024 HMM build alignments."""

from __future__ import annotations

import csv
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..config import ProjectConfig
from ..data.fasta import iter_fasta, sequence_hashes
from ..data.identifiers import (
    family_base,
    genome_from_filename,
    is_fam0,
    parse_jgi_header,
    resolve_genome_alias,
    split_annotation,
)
from ..errors import DependencyError, ValidationError
from ..provenance import RunContext
from ..tableio import read_tsv


SEED_FIELDS = [
    "genome_id",
    "original_id",
    "family_base",
    "seed_id",
    "identity",
    "query_coverage",
    "target_coverage",
    "bitscore",
    "seed_reference_release",
]


def _collect_missing_queries(
    comparison_path: Path,
    msa_dir: Path,
    max_families: int | None,
) -> dict[str, set[tuple[str, str]]]:
    wanted: dict[str, set[tuple[str, str]]] = defaultdict(set)
    available = {family_base(path.stem) for path in msa_dir.glob("*.aln")}
    for row in read_tsv(comparison_path):
        expected = split_annotation(row.get("cazy_annotation", ""))
        predicted = split_annotation(row.get("dbcan_annotation", ""))
        for family, count in expected.items():
            if count <= predicted.get(family, 0) or family not in available or is_fam0(family):
                continue
            wanted[family].add((row["genome"], row["protein_id"]))
    if max_families is not None:
        selected = sorted(wanted, key=lambda family: (-len(wanted[family]), family))[:max_families]
        wanted = {family: wanted[family] for family in selected}
    return dict(wanted)


def _load_query_sequences(
    proteome_dir: Path,
    wanted: dict[str, set[tuple[str, str]]],
) -> tuple[dict[tuple[str, str], str], list[dict[str, str]]]:
    by_genome: dict[str, set[str]] = defaultdict(set)
    for keys in wanted.values():
        for genome, original_id in keys:
            by_genome[genome].add(original_id)
    sequences: dict[tuple[str, str], str] = {}
    observed_sources: dict[tuple[str, str], tuple[str, str]] = {}
    conflicts: list[dict[str, str]] = []
    resolved_files = []
    for path in (candidate for candidate in proteome_dir.iterdir() if candidate.is_file()):
        observed = genome_from_filename(path.name)
        genome, method = resolve_genome_alias(observed, set(by_genome))
        if genome is not None:
            resolved_files.append((0 if method == "exact_genome_id" else 1, path, genome))
    resolved_files.sort(key=lambda item: (item[0], item[1].name))
    for index, (_, path, genome) in enumerate(resolved_files, 1):
        observed_genome = genome_from_filename(path.name)
        ids = by_genome.get(genome)
        if not ids:
            continue
        if index % 100 == 0:
            print(f"[seed-identity] scanning proteome {index}/{len(resolved_files)}")
        for header, sequence in iter_fasta(path):
            parsed = parse_jgi_header(header, observed_genome)
            if parsed.original_id in ids:
                key = (genome, parsed.original_id)
                digest, _ = sequence_hashes(sequence)
                if key in sequences:
                    first_observed, first_digest = observed_sources[key]
                    if first_digest != digest:
                        conflicts.append(
                            {
                                "genome_id": genome,
                                "original_id": parsed.original_id,
                                "kept_observed_genome_id": first_observed,
                                "kept_sequence_sha256": first_digest,
                                "conflicting_observed_genome_id": parsed.genome_id,
                                "conflicting_sequence_sha256": digest,
                            }
                        )
                    continue
                sequences[key] = sequence
                observed_sources[key] = (parsed.genome_id, digest)
    return sequences, conflicts


def _write_family_fastas(
    family: str,
    keys: set[tuple[str, str]],
    sequences: dict[tuple[str, str], str],
    msa_path: Path,
    work_dir: Path,
) -> tuple[Path, Path, int]:
    query_path = work_dir / f"{family}.queries.faa"
    seed_path = work_dir / f"{family}.seeds.faa"
    query_count = 0
    with query_path.open("x", encoding="utf-8") as handle:
        for genome, original_id in sorted(keys):
            sequence = sequences.get((genome, original_id))
            if sequence is None:
                continue
            handle.write(f">{genome}|{original_id}\n{sequence}\n")
            query_count += 1
    with seed_path.open("x", encoding="utf-8") as handle:
        for seed_id, sequence in iter_fasta(msa_path):
            ungapped = sequence.replace("-", "").replace(".", "")
            if ungapped:
                handle.write(f">{seed_id.split()[0]}\n{ungapped}\n")
    return query_path, seed_path, query_count


def compute_seed_identity(
    config: ProjectConfig,
    run: RunContext,
    threads: int = 8,
    max_families: int | None = None,
) -> Path:
    """Compute best within-family identity to 2024 MSA members for HMM misses."""

    configured = config.raw.get("tools", {}) if isinstance(config.raw.get("tools"), dict) else {}
    mmseqs = configured.get("mmseqs") or shutil.which("mmseqs")
    if not mmseqs:
        raise DependencyError("MMseqs2 is required for the seed-identity audit")
    comparison_path = config.source_path("aim2_protein_comparison")
    msa_dir = config.source_path("dbcan_msa_2024")
    proteome_dir = config.source_path("aim2_proteomes")
    run.record_input("aim2_protein_comparison", comparison_path, schema="aim2_protein_comparison")
    run.record_input("dbcan_msa_2024", msa_dir, schema="aligned_fasta_directory", digest="directory")
    run.record_input("aim2_proteomes", proteome_dir, schema="protein_fasta_directory", digest="directory")

    wanted = _collect_missing_queries(comparison_path, msa_dir, max_families)
    print(
        f"[seed-identity] {len(wanted)} families, "
        f"{sum(len(values) for values in wanted.values()):,} protein-family misses"
    )
    sequences, identifier_conflicts = _load_query_sequences(proteome_dir, wanted)
    conflict_path = run.result_dir / "seed_identity_identifier_conflicts.tsv"
    conflict_fields = [
        "genome_id",
        "original_id",
        "kept_observed_genome_id",
        "kept_sequence_sha256",
        "conflicting_observed_genome_id",
        "conflicting_sequence_sha256",
    ]
    with conflict_path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=conflict_fields, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(identifier_conflicts)
    run.record_output(
        "seed_identity_identifier_conflicts",
        conflict_path,
        len(identifier_conflicts),
        conflict_fields,
    )
    if identifier_conflicts:
        raise ValidationError(
            f"Seed-identity input has {len(identifier_conflicts)} conflicting canonical IDs"
        )
    missing_sequence_count = sum(
        key not in sequences for keys in wanted.values() for key in keys
    )
    if missing_sequence_count:
        raise ValidationError(f"Missing sequences for {missing_sequence_count} seed-identity queries")

    work_dir = run.result_dir / "seed_identity_work"
    work_dir.mkdir(parents=True, exist_ok=False)
    output_path = run.result_dir / "seed_identity.tsv"
    target_coverage = float(
        config.phase0.get("thresholds", {}).get("seed_target_coverage_min", 0.80)
    )
    match_count = 0
    with output_path.open("x", encoding="utf-8", newline="") as output_handle:
        writer = csv.DictWriter(
            output_handle, fieldnames=SEED_FIELDS, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        for index, family in enumerate(sorted(wanted), 1):
            print(f"[seed-identity] family {index}/{len(wanted)}: {family}")
            msa_path = msa_dir / f"{family}.aln"
            query_path, seed_path, query_count = _write_family_fastas(
                family, wanted[family], sequences, msa_path, work_dir
            )
            if query_count == 0:
                continue
            result_path = work_dir / f"{family}.m8"
            tmp_dir = work_dir / f"{family}.tmp"
            command = [
                str(mmseqs),
                "easy-search",
                str(query_path),
                str(seed_path),
                str(result_path),
                str(tmp_dir),
                "--threads",
                str(threads),
                "--min-seq-id",
                "0.0",
                "-c",
                str(target_coverage),
                "--cov-mode",
                "2",
                "-e",
                "1000",
                "--max-seqs",
                "1",
                "--format-output",
                "query,target,fident,qcov,tcov,bits",
            ]
            proc = subprocess.run(command, check=False, capture_output=True, text=True)
            if proc.returncode != 0:
                raise ValidationError(
                    f"MMseqs failed for {family}: {(proc.stderr or proc.stdout)[-1000:]}"
                )
            if not result_path.is_file():
                continue
            with result_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) < 6:
                        continue
                    query, seed_id, identity, qcov, tcov, bits = parts[:6]
                    genome, original_id = query.split("|", 1)
                    fident = float(identity)
                    if fident > 1.0:
                        fident /= 100.0
                    writer.writerow(
                        {
                            "genome_id": genome,
                            "original_id": original_id,
                            "family_base": family,
                            "seed_id": seed_id,
                            "identity": f"{fident:.8f}",
                            "query_coverage": qcov,
                            "target_coverage": tcov,
                            "bitscore": bits,
                            "seed_reference_release": "2024",
                        }
                    )
                    match_count += 1
    run.record_output("seed_identity", output_path, match_count, SEED_FIELDS)
    run.add_metric("seed_identity_families", len(wanted))
    run.add_metric("seed_identity_matches", match_count)
    run.add_metric("seed_identity_missing_sequences", missing_sequence_count)
    return output_path
