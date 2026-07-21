from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_model_artifact_manifest_contract() -> None:
    schema = json.loads(
        (ROOT / "schemas" / "model_artifact_manifest.schema.json").read_text(
            encoding="utf-8"
        )
    )
    required = set(schema["required"])
    assert {
        "artifact_id",
        "run_id",
        "model",
        "representation",
        "subject",
        "context_policy",
        "split_id",
    } <= required
    model_required = set(schema["properties"]["model"]["required"])
    assert {"model_revision", "weights_sha256", "license_snapshot_uri"} <= model_required
    subject = schema["properties"]["subject"]["properties"]
    assert subject["coordinate_convention"]["const"] == "1-based inclusive"
    assert schema["properties"]["context_policy"]["properties"]["overlap_residues"]


def test_esmc_example_config_is_non_executable_and_explicit() -> None:
    config = yaml.safe_load(
        (ROOT / "configs" / "models" / "esmc.example.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert config["status"] == "example_only"
    assert config["models"]["sequence_primary"]["model_revision"].startswith(
        "REPLACE_WITH_"
    )
    assert config["long_sequences"]["overlap_residues"] == 256
    assert config["long_sequences"]["forbid_silent_truncation"] is True
    assert config["lora_initial"]["dropout"] == 0.01


def test_met_wrapper_has_valid_bash_syntax() -> None:
    subprocess.run(
        ["bash", "-n", str(ROOT / "scripts" / "remote" / "met_run.sh")],
        check=True,
    )


def test_report_retains_phase0_gates_and_evidence_boundaries() -> None:
    report = (ROOT / "docs" / "esmc_2026_integration_report_zh.md").read_text(
        encoding="utf-8"
    )
    for value in ("32.84%", "5.6524%", "36", "5,829", "9,211", "53/73"):
        assert value in report
    assert "不是 CAZyme benchmark" in report
    assert "模型训练尚未授权" in report

