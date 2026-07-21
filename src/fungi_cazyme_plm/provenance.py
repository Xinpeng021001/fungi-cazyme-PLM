"""Append-only run logging and artifact provenance."""

from __future__ import annotations

import csv
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from .config import ProjectConfig
from .tableio import sha256_file


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _git_state(project_root: Path) -> tuple[str, bool]:
    try:
        commit_process = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=False,
            capture_output=True,
            text=True,
        )
        commit = (
            commit_process.stdout.strip() if commit_process.returncode == 0 else "UNBORN"
        )
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_root,
                check=False,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return commit or "UNBORN", dirty
    except OSError:
        return "UNAVAILABLE", True


def _tool_version(command: str, args: list[str]) -> str | None:
    executable = shutil.which(command)
    if not executable:
        return None
    try:
        proc = subprocess.run(
            [executable, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = (proc.stdout or proc.stderr).strip().splitlines()
    return value[0] if value else executable


class Tee(TextIO):
    def __init__(self, original: TextIO, log_handle: TextIO) -> None:
        self.original = original
        self.log_handle = log_handle

    def write(self, value: str) -> int:
        written = self.original.write(value)
        self.log_handle.write(value)
        self.log_handle.flush()
        return written

    def flush(self) -> None:
        self.original.flush()
        self.log_handle.flush()

    def isatty(self) -> bool:
        return self.original.isatty()


class RunContext:
    """One immutable command run with paired log and result directories."""

    def __init__(
        self,
        config: ProjectConfig,
        command: str,
        random_seed: int = 42,
        resume_from_run_id: str | None = None,
    ) -> None:
        self.config = config
        self.command = command
        self.random_seed = random_seed
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        slug = re.sub(r"[^a-z0-9.-]+", "-", command.lower().replace("_", "-")).strip("-")[:36]
        self.run_id = f"{timestamp}_{config.config_sha256[:8]}_{slug}"
        self.log_dir = config.outputs["logs_dir"] / self.run_id
        self.result_dir = config.outputs["results_dir"] / self.run_id
        self.log_dir.mkdir(parents=True, exist_ok=False)
        self.result_dir.mkdir(parents=True, exist_ok=False)
        self.run_path = self.log_dir / "run.json"
        self.events_path = self.log_dir / "events.jsonl"
        self.inputs_path = self.log_dir / "inputs.tsv"
        self.outputs_path = self.log_dir / "outputs.tsv"
        self.metrics_path = self.log_dir / "metrics.json"
        self._stdout_handle = None
        self._stderr_handle = None
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self.metrics: dict[str, Any] = {}
        commit, dirty = _git_state(config.project_root)
        self.manifest: dict[str, Any] = {
            "run_id": self.run_id,
            "command": command,
            "argv": sys.argv,
            "status": "running",
            "started_at_utc": utc_now(),
            "ended_at_utc": None,
            "config_path": str(config.path),
            "config_sha256": config.config_sha256,
            "git_commit": commit,
            "git_dirty": dirty,
            "random_seed": random_seed,
            "resume_from_run_id": resume_from_run_id,
            "result_dir": str(self.result_dir),
            "log_dir": str(self.log_dir),
            "error": None,
        }
        self._write_manifest()
        self._write_environment()
        self._initialize_artifact_tables()

    def _write_manifest(self) -> None:
        temporary = self.run_path.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(self.manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, self.run_path)

    def _write_environment(self) -> None:
        commit = self.manifest["git_commit"]
        values = {
            "python": sys.version.replace("\n", " "),
            "platform": platform.platform(),
            "hostname": socket.gethostname(),
            "cpu_count": os.cpu_count(),
            "git_commit": commit,
            "git_dirty": self.manifest["git_dirty"],
            "mmseqs": _tool_version("mmseqs", ["version"]),
            "taxonkit": _tool_version("taxonkit", ["version"]),
            "hmmsearch": _tool_version("hmmsearch", ["-h"]),
        }
        with (self.log_dir / "environment.txt").open("x", encoding="utf-8") as handle:
            for key, value in values.items():
                handle.write(f"{key}\t{value if value is not None else 'unavailable'}\n")

    def _initialize_artifact_tables(self) -> None:
        with self.inputs_path.open("x", encoding="utf-8", newline="") as handle:
            csv.writer(handle, delimiter="\t", lineterminator="\n").writerow(
                ["source_id", "path", "size_bytes", "sha256", "record_count", "schema"]
            )
        with self.outputs_path.open("x", encoding="utf-8", newline="") as handle:
            csv.writer(handle, delimiter="\t", lineterminator="\n").writerow(
                ["artifact_id", "path", "size_bytes", "sha256", "record_count", "columns"]
            )

    def __enter__(self) -> "RunContext":
        self._stdout_handle = (self.log_dir / "stdout.log").open("x", encoding="utf-8")
        self._stderr_handle = (self.log_dir / "stderr.log").open("x", encoding="utf-8")
        sys.stdout = Tee(self._original_stdout, self._stdout_handle)
        sys.stderr = Tee(self._original_stderr, self._stderr_handle)
        self.event("run_started", command=self.command)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc is None:
            self.manifest["status"] = "completed"
            self.event("run_completed")
        else:
            self.manifest["status"] = "failed"
            self.manifest["error"] = f"{exc_type.__name__}: {exc}"
            self.event("run_failed", error=self.manifest["error"])
            traceback.print_exception(exc_type, exc, tb, file=sys.stderr)
        self.manifest["ended_at_utc"] = utc_now()
        self._write_manifest()
        with self.metrics_path.open("w", encoding="utf-8") as handle:
            json.dump(self.metrics, handle, indent=2, sort_keys=True)
            handle.write("\n")
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr
        if self._stdout_handle:
            self._stdout_handle.close()
        if self._stderr_handle:
            self._stderr_handle.close()
        return False

    def event(self, event: str, **payload: Any) -> None:
        record = {"timestamp_utc": utc_now(), "event": event, **payload}
        with self.events_path.open("a", encoding="utf-8") as handle:
            json.dump(record, handle, sort_keys=True)
            handle.write("\n")

    def add_metric(self, key: str, value: Any) -> None:
        self.metrics[key] = value

    def record_input(
        self,
        source_id: str,
        path: str | Path,
        record_count: int | None = None,
        schema: str = "",
        digest: str | None = None,
    ) -> None:
        artifact = Path(path)
        stat = artifact.stat()
        file_digest = digest or (sha256_file(artifact) if artifact.is_file() else "directory")
        with self.inputs_path.open("a", encoding="utf-8", newline="") as handle:
            csv.writer(handle, delimiter="\t", lineterminator="\n").writerow(
                [source_id, artifact, stat.st_size, file_digest, record_count or "", schema]
            )

    def record_output(
        self,
        artifact_id: str,
        path: str | Path,
        record_count: int | None = None,
        columns: list[str] | None = None,
    ) -> None:
        artifact = Path(path)
        if not artifact.is_file():
            raise FileNotFoundError(f"Cannot record missing output: {artifact}")
        with self.outputs_path.open("a", encoding="utf-8", newline="") as handle:
            csv.writer(handle, delimiter="\t", lineterminator="\n").writerow(
                [
                    artifact_id,
                    artifact,
                    artifact.stat().st_size,
                    sha256_file(artifact),
                    record_count or "",
                    ",".join(columns or []),
                ]
            )
        self.event("output_recorded", artifact_id=artifact_id, path=str(artifact))
