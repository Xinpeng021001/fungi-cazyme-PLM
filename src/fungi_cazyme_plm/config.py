"""Configuration loading and validation."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .errors import ConfigurationError


def _expand(value: Any) -> Any:
    if isinstance(value, str):
        return os.path.expanduser(os.path.expandvars(value))
    if isinstance(value, list):
        return [_expand(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand(item) for key, item in value.items()}
    return value


def _deep_merge(base: dict[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _deep_merge(dict(result[key]), value)
        else:
            result[key] = value
    return result


@dataclass(frozen=True)
class ProjectConfig:
    """Resolved project configuration."""

    path: Path
    raw: dict[str, Any]
    project_root: Path
    outputs: dict[str, Path]
    sources: dict[str, dict[str, Any]]
    phase0: dict[str, Any]
    config_sha256: str

    def source_path(self, source_id: str) -> Path:
        try:
            return Path(self.sources[source_id]["path"])
        except KeyError as exc:
            raise ConfigurationError(f"Missing configured source: {source_id}") from exc

    def source(self, source_id: str) -> dict[str, Any]:
        try:
            return self.sources[source_id]
        except KeyError as exc:
            raise ConfigurationError(f"Missing configured source: {source_id}") from exc


def load_config(path: str | Path) -> ProjectConfig:
    """Load a local source config and merge the tracked Phase 0 defaults."""

    config_path = Path(path).expanduser().resolve()
    if not config_path.is_file():
        raise ConfigurationError(f"Configuration file does not exist: {config_path}")
    with config_path.open("rb") as handle:
        config_bytes = handle.read()
    try:
        loaded = yaml.safe_load(config_bytes.decode("utf-8")) or {}
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"Cannot parse YAML config {config_path}: {exc}") from exc
    loaded = _expand(loaded)
    if not isinstance(loaded, dict):
        raise ConfigurationError("Top-level configuration must be a mapping")

    project_root_value = loaded.get("project_root")
    if not project_root_value:
        raise ConfigurationError("project_root is required")
    project_root = Path(project_root_value).expanduser().resolve()

    phase0_path = project_root / "configs" / "phase0.yaml"
    phase0: dict[str, Any] = {}
    if phase0_path.is_file():
        with phase0_path.open("r", encoding="utf-8") as handle:
            phase0_loaded = yaml.safe_load(handle) or {}
        if not isinstance(phase0_loaded, dict):
            raise ConfigurationError("configs/phase0.yaml must contain a mapping")
        phase0 = _expand(phase0_loaded)
    if isinstance(loaded.get("phase0"), Mapping):
        phase0 = _deep_merge(phase0, loaded["phase0"])

    raw_outputs = loaded.get("outputs", {})
    if not isinstance(raw_outputs, Mapping):
        raise ConfigurationError("outputs must be a mapping")
    defaults = {
        "logs_dir": project_root / "logs",
        "results_dir": project_root / "results" / "phase0",
        "interim_dir": project_root / "data" / "interim",
        "processed_dir": project_root / "data" / "processed",
        "snapshots_dir": project_root / "data" / "manifests" / "snapshots",
    }
    outputs = {
        key: Path(raw_outputs.get(key, default)).expanduser().resolve()
        for key, default in defaults.items()
    }

    sources = loaded.get("sources")
    if not isinstance(sources, Mapping) or not sources:
        raise ConfigurationError("sources must be a non-empty mapping")
    normalized_sources: dict[str, dict[str, Any]] = {}
    for source_id, spec in sources.items():
        if not isinstance(spec, Mapping) or not spec.get("path"):
            raise ConfigurationError(f"Source {source_id!r} requires a path")
        normalized = dict(spec)
        normalized["path"] = str(Path(normalized["path"]).expanduser().resolve())
        normalized.setdefault("kind", "file")
        if normalized["kind"] not in {"file", "directory"}:
            raise ConfigurationError(
                f"Source {source_id!r} kind must be 'file' or 'directory'"
            )
        normalized_sources[str(source_id)] = normalized

    hash_payload = json.dumps(
        {"source_config": loaded, "effective_phase0": phase0},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    return ProjectConfig(
        path=config_path,
        raw=loaded,
        project_root=project_root,
        outputs=outputs,
        sources=normalized_sources,
        phase0=phase0,
        config_sha256=hashlib.sha256(hash_payload).hexdigest(),
    )
