"""Command-line entry point for the Phase 0 research workflow."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Sequence

from .audit.function_labels import audit_function_labels
from .audit.gap_quantification import quantify_gap
from .audit.report import generate_phase0_report
from .audit.seed_identity import compute_seed_identity
from .audit.structure_availability import audit_structure_availability
from .config import ProjectConfig, load_config
from .data.aim2_import import import_aim2
from .data.inventory import inventory_sources, validate_snapshot
from .errors import ConfigurationError, FCPLMError
from .provenance import RunContext


def _add_config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        default="configs/data_sources.local.yaml",
        help="Local YAML data-source configuration",
    )
    parser.add_argument(
        "--resume",
        metavar="FAILED_RUN_ID",
        help="Retry from a failed/partial run in a new immutable run directory",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fcplm",
        description="Auditable Phase 0 workflow for fungi CAZyme PLM research",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory", help="Validate and snapshot data sources")
    _add_config(inventory)
    inventory.add_argument("--quick", action="store_true", help="Use metadata digests")
    inventory.add_argument(
        "--against", type=Path, help="Validate current full hashes against a prior snapshot"
    )

    importer = subparsers.add_parser("import-aim2", help="Normalize read-only Aim2 outputs")
    _add_config(importer)
    importer.add_argument("--skip-aliases", action="store_true")
    importer.add_argument("--skip-domains", action="store_true")

    phase0 = subparsers.add_parser("phase0", help="Run a Phase 0 audit")
    phase0_sub = phase0.add_subparsers(dest="phase0_command", required=True)

    gap = phase0_sub.add_parser("gap", help="Quantify fungi/dbCAN family gaps")
    _add_config(gap)
    gap.add_argument("--seed-identity", type=Path)
    gap.add_argument("--no-overlap-reconstruction", action="store_true")

    seed = phase0_sub.add_parser("seed-identity", help="Search misses against 2024 MSA seeds")
    _add_config(seed)
    seed.add_argument("--threads", type=int, default=8)
    seed.add_argument("--max-families", type=int)

    labels = phase0_sub.add_parser("labels", help="Audit substrate/function labels")
    _add_config(labels)

    structures = phase0_sub.add_parser("structures", help="Audit CAZyme3D availability")
    _add_config(structures)
    structures.add_argument(
        "--exact-only", action="store_true", help="Skip the MMseqs2 90/80 near-match search"
    )
    structures.add_argument("--threads", type=int, default=16)

    all_phase0 = phase0_sub.add_parser("all", help="Run the complete Phase 0 workflow")
    _add_config(all_phase0)
    all_phase0.add_argument("--quick-inventory", action="store_true")
    all_phase0.add_argument("--skip-aliases", action="store_true")
    all_phase0.add_argument("--skip-domains", action="store_true")
    all_phase0.add_argument("--skip-seed-identity", action="store_true")
    all_phase0.add_argument("--exact-structures-only", action="store_true")
    all_phase0.add_argument("--threads", type=int, default=16)
    all_phase0.add_argument("--max-seed-families", type=int)
    all_phase0.add_argument("--promote", action="store_true")

    report = subparsers.add_parser("report", help="Generate a decision memo")
    report_sub = report.add_subparsers(dest="report_command", required=True)
    report_phase0 = report_sub.add_parser("phase0")
    _add_config(report_phase0)
    report_phase0.add_argument("--from-run", type=Path)
    report_phase0.add_argument("--aim2-run", type=Path)
    report_phase0.add_argument("--alias-run", type=Path)
    report_phase0.add_argument("--gap-run", type=Path)
    report_phase0.add_argument("--function-run", type=Path)
    report_phase0.add_argument("--structure-run", type=Path)
    report_phase0.add_argument("--promote", action="store_true")

    smoke = subparsers.add_parser("smoke", help="Run the deterministic fixture workflow")
    _add_config(smoke)
    return parser


def _command_text(argv: Sequence[str]) -> str:
    return "fcplm " + " ".join(shlex.quote(item) for item in argv)


def _resolve_resume(config: ProjectConfig, value: str | None) -> str | None:
    if value is None:
        return None
    if not config.raw.get("pinned_snapshot"):
        raise ConfigurationError("--resume requires a pinned_snapshot in the local config")
    candidate = Path(value)
    manifest_path = candidate / "run.json" if candidate.is_dir() else None
    if manifest_path is None or not manifest_path.is_file():
        manifest_path = config.outputs["logs_dir"] / value / "run.json"
    if not manifest_path.is_file():
        raise ConfigurationError(f"Cannot find resume manifest: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as handle:
        previous = json.load(handle)
    if previous.get("status") not in {"failed", "partial"}:
        raise ConfigurationError(
            f"--resume only accepts failed/partial runs; observed {previous.get('status')!r}"
        )
    if previous.get("config_sha256") != config.config_sha256:
        raise ConfigurationError("--resume config hash differs from the prior run")
    run_id = previous.get("run_id")
    if not run_id:
        raise ConfigurationError("Resume manifest has no run_id")
    return str(run_id)


def _run_phase0_all(config: ProjectConfig, run: RunContext, args: argparse.Namespace) -> None:
    snapshot, _ = inventory_sources(config, run, quick=args.quick_inventory)
    run.add_metric("phase0_inventory_snapshot", str(snapshot))
    import_aim2(
        config,
        run,
        include_aliases=not args.skip_aliases,
        include_domains=not args.skip_domains,
    )
    seed_path = None
    if not args.skip_seed_identity:
        seed_path = compute_seed_identity(
            config,
            run,
            threads=args.threads,
            max_families=args.max_seed_families,
        )
    quantify_gap(config, run, seed_identity_path=seed_path)
    audit_function_labels(config, run)
    audit_structure_availability(
        config,
        run,
        with_mmseqs=not args.exact_structures_only,
        threads=args.threads,
    )
    generate_phase0_report(config, run, promote=args.promote)


def _run_smoke(config: ProjectConfig, run: RunContext) -> None:
    inventory_sources(config, run, quick=False)
    import_aim2(config, run, include_aliases=True, include_domains=True)
    quantify_gap(config, run, reconstruct_overlap=True)
    audit_function_labels(config, run)
    audit_structure_availability(config, run, with_mmseqs=False, threads=1)
    generate_phase0_report(config, run, write_process_log=False)


def dispatch(args: argparse.Namespace, argv: Sequence[str]) -> None:
    config = load_config(args.config)
    command = _command_text(argv)
    resume_from = _resolve_resume(config, args.resume)
    if resume_from and args.command == "inventory":
        raise ConfigurationError("Inventory runs are validated with --against, not --resume")
    with RunContext(config, command, resume_from_run_id=resume_from) as run:
        pinned_snapshot = config.raw.get("pinned_snapshot")
        if pinned_snapshot and args.command != "inventory":
            pinned_path = Path(str(pinned_snapshot)).resolve()
            print(f"[fcplm] validating pinned input snapshot: {pinned_path}")
            validate_snapshot(config, pinned_path)
            run.add_metric("pinned_snapshot", str(pinned_path))
            run.event("pinned_snapshot_validated", path=str(pinned_path))
        if resume_from:
            run.event("run_resumed", resume_from_run_id=resume_from)
        if args.command == "inventory":
            if args.against:
                validate_snapshot(config, args.against)
                run.add_metric("validated_snapshot", str(args.against.resolve()))
            else:
                inventory_sources(config, run, quick=args.quick)
        elif args.command == "import-aim2":
            import_aim2(
                config,
                run,
                include_aliases=not args.skip_aliases,
                include_domains=not args.skip_domains,
            )
        elif args.command == "phase0" and args.phase0_command == "gap":
            quantify_gap(
                config,
                run,
                seed_identity_path=args.seed_identity,
                reconstruct_overlap=not args.no_overlap_reconstruction,
            )
        elif args.command == "phase0" and args.phase0_command == "seed-identity":
            compute_seed_identity(
                config, run, threads=args.threads, max_families=args.max_families
            )
        elif args.command == "phase0" and args.phase0_command == "labels":
            audit_function_labels(config, run)
        elif args.command == "phase0" and args.phase0_command == "structures":
            audit_structure_availability(
                config,
                run,
                with_mmseqs=not args.exact_only,
                threads=args.threads,
            )
        elif args.command == "phase0" and args.phase0_command == "all":
            _run_phase0_all(config, run, args)
        elif args.command == "report" and args.report_command == "phase0":
            component_dirs = {
                key: value.resolve()
                for key, value in {
                    "aim2": args.aim2_run,
                    "alias": args.alias_run,
                    "gap": args.gap_run,
                    "function": args.function_run,
                    "structure": args.structure_run,
                }.items()
                if value is not None
            }
            generate_phase0_report(
                config,
                run,
                artifact_dir=args.from_run.resolve() if args.from_run else None,
                component_dirs=component_dirs,
                promote=args.promote,
            )
        elif args.command == "smoke":
            _run_smoke(config, run)
        else:  # pragma: no cover - argparse prevents this
            raise FCPLMError(f"Unsupported command: {args}")
        print(f"[fcplm] completed run {run.run_id}")
        print(f"[fcplm] results: {run.result_dir}")
        print(f"[fcplm] logs: {run.log_dir}")


def main(argv: Sequence[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    try:
        dispatch(parser.parse_args(values), values)
    except (FCPLMError, FileExistsError, FileNotFoundError) as exc:
        print(f"fcplm: error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
