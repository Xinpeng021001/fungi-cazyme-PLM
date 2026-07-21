import json
from dataclasses import replace
from pathlib import Path

import pytest

from fungi_cazyme_plm.cli import _resolve_resume
from fungi_cazyme_plm.config import load_config
from fungi_cazyme_plm.errors import ConfigurationError


FIXTURE_CONFIG = Path(__file__).parents[1] / "fixtures" / "config.yaml"


def test_resume_requires_failed_status_same_config_and_pinned_inputs(tmp_path: Path) -> None:
    config = load_config(FIXTURE_CONFIG)
    raw = dict(config.raw)
    raw["pinned_snapshot"] = str(tmp_path / "snapshot.tsv")
    outputs = dict(config.outputs)
    outputs["logs_dir"] = tmp_path / "logs"
    config = replace(config, raw=raw, outputs=outputs)
    run_dir = outputs["logs_dir"] / "failed-run"
    run_dir.mkdir(parents=True)
    manifest = {
        "run_id": "failed-run",
        "status": "failed",
        "config_sha256": config.config_sha256,
    }
    (run_dir / "run.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert _resolve_resume(config, "failed-run") == "failed-run"

    manifest["status"] = "completed"
    (run_dir / "run.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="failed/partial"):
        _resolve_resume(config, "failed-run")
