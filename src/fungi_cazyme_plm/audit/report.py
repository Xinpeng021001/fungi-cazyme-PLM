"""Phase 0 synthesis report and explicit decision gate."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import ProjectConfig
from ..provenance import RunContext
from ..tableio import json_dump_new, json_load


def _load_optional(directory: Path, name: str) -> dict[str, Any] | None:
    path = directory / name
    return json_load(path) if path.is_file() else None


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "not available"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def generate_phase0_report(
    config: ProjectConfig,
    run: RunContext,
    artifact_dir: Path | None = None,
    component_dirs: dict[str, Path] | None = None,
    promote: bool = False,
    write_process_log: bool = True,
) -> dict[str, Any]:
    source = artifact_dir or run.result_dir
    component_dirs = component_dirs or {}
    sources = {
        "aim2": component_dirs.get("aim2", source),
        "alias": component_dirs.get("alias", source),
        "gap": component_dirs.get("gap", source),
        "function": component_dirs.get("function", source),
        "structure": component_dirs.get("structure", source),
    }
    gap = _load_optional(sources["gap"], "gap_metrics.json")
    function = _load_optional(sources["function"], "function_label_audit.json")
    structure = _load_optional(sources["structure"], "structure_availability.json")
    aim2 = _load_optional(sources["aim2"], "aim2_import_summary.json")
    alias_conflicts = _load_optional(
        sources["alias"], "protein_alias_conflicts.metadata.json"
    )
    alias_conflict_count = int(alias_conflicts.get("rows", 0)) if alias_conflicts else None
    missing = [
        label
        for label, value in (
            ("Aim2 import", aim2),
            ("gap quantification", gap),
            ("function-label audit", function),
            ("structure audit", structure),
        )
        if value is None
    ]

    completed_gates = {
        "gap_quantification": gap is not None,
        "protein_alias_integrity": bool(
            aim2
            and aim2.get("protein_aliases", {}).get("status") != "skipped"
            and aim2.get("protein_aliases", {}).get("duplicate_conflicts") == 0
            and alias_conflict_count in {None, 0}
        ),
        "seed_identity_2024": bool(
            gap
            and (
                gap.get("seed_identity_rows", 0) > 0
                or gap.get("unmatched_family_instances", 0) == 0
            )
        ),
        "function_label_audit": function is not None,
        "structure_availability": bool(
            structure and structure.get("near_search_status") == "completed"
        ),
        "ceiling_probe": False,
        "protein_level_function_labels": bool(
            function and function.get("hard_function_evaluation_ready")
        ),
        "independent_boundary_gold": bool(gap and gap.get("boundary_gold_available")),
        "licence_release_decision": False,
    }
    blockers = [name for name, completed in completed_gates.items() if not completed]
    preliminary_gate = gap.get("preliminary_gate") if gap else "not_available"
    final_status = "blocked_pending_phase0_gates" if blockers else preliminary_gate

    lines = [
        "# Phase 0 decision memo",
        "",
        f"**Generated run:** `{run.run_id}`  ",
        f"**Artifact sources:** `{', '.join(f'{key}={value}' for key, value in sources.items())}`  ",
        f"**Decision status:** `{final_status}`",
        "",
        "## Executive result",
        "",
    ]
    if gap:
        lines.extend(
            [
                f"The preliminary addressable family-instance error rate is "
                f"**{_fmt(gap.get('preliminary_addressable_error_rate'))}** "
                f"(95% Wilson CI {_fmt(gap.get('addressable_error_ci_lower'))}–"
                f"{_fmt(gap.get('addressable_error_ci_upper'))}; threshold "
                f"{_fmt(gap.get('go_no_go_threshold'))}).",
                "",
                f"The automatic gap-only recommendation is `{preliminary_gate}`. "
                "It is not a final project decision until all blocking Phase 0 gates are complete.",
            ]
        )
    else:
        lines.append("Gap metrics are unavailable; no go/no-go inference is permitted.")
    lines.extend(["", "## Evidence table", "", "| Evidence | Result | Status |", "|---|---|---|"])
    if aim2:
        myco = aim2.get("mycocosm", {})
        lines.append(
            f"| Aim2/MycoCosm reuse | {myco.get('metadata_matched', 0)}/"
            f"{myco.get('evaluated_genomes', 0)} genomes matched; published/non-restricted | complete |"
        )
    else:
        lines.append("| Aim2/MycoCosm reuse | unavailable | missing |")
    if alias_conflict_count is not None:
        lines.append(
            f"| Protein alias integrity | {alias_conflict_count} conflicting canonical keys | "
            f"{'complete' if alias_conflict_count == 0 else 'blocked'} |"
        )
    if gap:
        lines.append(
            f"| HMM gap spectrum | {gap.get('truth_family_instances', 0):,} truth family instances; "
            f"{gap.get('unmatched_family_instances', 0):,} unmatched | complete, boundary gold absent |"
        )
    else:
        lines.append("| HMM gap spectrum | unavailable | missing |")
    if function:
        lines.append(
            f"| Function labels | {function.get('unique_families', 0)} mapped families; "
            f"{function.get('high_level_polyspecific_families', 0)} polyspecific | "
            "weak labels only |"
        )
    else:
        lines.append("| Function labels | unavailable | missing |")
    if structure:
        lines.append(
            f"| CAZyme3D local coverage | exact={structure.get('exact_sequence_matches', 0):,}; "
            f"90/80={structure.get('near_90_80_matches_excluding_exact', 0):,}; "
            f"coverage={_fmt(structure.get('local_structure_reference_coverage'))} | "
            f"near search {structure.get('near_search_status')} |"
        )
    else:
        lines.append("| CAZyme3D local coverage | unavailable | missing |")
    lines.extend(
        [
            "| Frozen ESM-2 ceiling probe | no official cluster30 result | blocked by GPU preflight |",
            "| Independent boundary evaluation | no curated/PDB boundary table | blocked |",
            "| Licence/release decision | legacy ESM-C 600M is audit-only | blocked |",
            "",
            "## Blocking items",
            "",
        ]
    )
    for blocker in blockers:
        lines.append(f"- `{blocker}`")
    if missing:
        lines.extend(["", "Missing run artifacts: " + ", ".join(missing) + "."])
    lines.extend(
        [
            "",
            "## Interpretation safeguards",
            "",
            "- fam-0 remains open-set truth and is never used as a negative.",
            "- HMM envelopes are weak supervision and do not score their own boundaries.",
            "- Family-inherited substrate labels do not qualify for hard function evaluation.",
            "- CAZyme3D is reported separately from experimental PDB and direct AFDB coverage.",
            "- Identity to an available MSA is labelled as 2024 seed-reference identity, not 2025.",
            "",
            "## Recommended next experiment",
            "",
        ]
    )
    if alias_conflict_count:
        recommendation = (
            f"Manually adjudicate or namespace the {alias_conflict_count} canonical ID conflicts, "
            "then rerun the 2024 seed-identity audit before any model training."
        )
    elif structure and structure.get("near_search_status") != "completed":
        recommendation = (
            "Complete the bounded CAZyme3D ≥90% identity/≥80% coverage search, then run the "
            "official ESM-2 650M cluster30 ceiling probe once GPU visibility is restored."
        )
    elif not completed_gates["ceiling_probe"]:
        recommendation = (
            "Run the official ESM-2 650M cluster30 ceiling probe; do not substitute legacy "
            "ESM-C 600M results."
        )
    else:
        recommendation = "Adjudicate the highest-priority gap cases and apply the pre-registered gate."
    lines.append(recommendation)
    lines.append("")

    report_path = run.result_dir / "00_phase0_decision_memo.generated.md"
    with report_path.open("x", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    run.record_output("phase0_decision_memo_generated", report_path, None, [])

    summary = {
        "run_id": run.run_id,
        "artifact_sources": {key: str(value) for key, value in sources.items()},
        "preliminary_gate": preliminary_gate,
        "final_status": final_status,
        "completed_gates": completed_gates,
        "blockers": blockers,
        "protein_alias_conflict_count": alias_conflict_count,
        "missing_artifacts": missing,
        "recommended_next_experiment": recommendation,
        "promoted": promote,
    }
    summary_path = json_dump_new(run.result_dir / "phase0_report_summary.json", summary)
    run.record_output("phase0_report_summary", summary_path, 1, list(summary))

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    process_dir = config.project_root / "docs" / "process"
    if write_process_log and process_dir.is_dir():
        process_path = process_dir / f"{timestamp}_phase0-report_{run.run_id}.md"
        with process_path.open("x", encoding="utf-8") as handle:
            handle.write(
                "# Phase 0 report generation\n\n"
                f"- Run ID: `{run.run_id}`\n"
                f"- Artifact sources: `{summary['artifact_sources']}`\n"
                f"- Result: `{final_status}`\n"
                f"- Generated memo: `{report_path}`\n"
                f"- Blockers: {', '.join(blockers) if blockers else 'none'}\n"
                f"- Next: {recommendation}\n"
            )
        run.record_output("scientific_process_log", process_path, None, [])

    if promote:
        promoted_path = config.project_root / "docs" / "00_phase0_decision_memo.md"
        promoted_path.write_text(report_path.read_text(encoding="utf-8"), encoding="utf-8")
        run.record_output("phase0_decision_memo_promoted", promoted_path, None, [])
    for key, value in summary.items():
        run.add_metric(f"report_{key}", value)
    return summary
