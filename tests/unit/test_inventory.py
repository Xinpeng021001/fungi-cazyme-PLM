import csv
from dataclasses import replace
from pathlib import Path

import pytest

from fungi_cazyme_plm.config import load_config
from fungi_cazyme_plm.data.inventory import inspect_file, validate_snapshot
from fungi_cazyme_plm.errors import ValidationError
from fungi_cazyme_plm.tableio import sha256_file


FIXTURE_CONFIG = Path(__file__).parents[1] / "fixtures" / "config.yaml"


def test_fixture_latin1_metadata_and_counts() -> None:
    config = load_config(FIXTURE_CONFIG)
    assert config.project_root == FIXTURE_CONFIG.parents[2].resolve()
    spec = config.source("mycocosm_metadata")
    row = inspect_file("mycocosm_metadata", Path(spec["path"]), spec, quick=False)
    assert row.record_count == 1
    assert row.columns[0] == "portal"
    assert row.validation_status == "ok"


def test_inventory_count_mismatch_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "rows.tsv"
    path.write_text("a\n1\n", encoding="utf-8")
    row = inspect_file("changed", path, {"expected_records": 2}, quick=False)
    assert row.validation_status == "error"
    assert "observed 1" in row.validation_message


def test_snapshot_detects_content_drift(tmp_path: Path) -> None:
    source = tmp_path / "source.tsv"
    source.write_text("a\n1\n", encoding="utf-8")
    snapshot = tmp_path / "snapshot.tsv"
    with snapshot.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source_id", "sha256"], delimiter="\t")
        writer.writeheader()
        writer.writerow({"source_id": "changed", "sha256": sha256_file(source)})
    config = load_config(FIXTURE_CONFIG)
    config = replace(
        config,
        sources={"changed": {"path": str(source), "kind": "file"}},
    )
    source.write_text("a\n2\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="Input drift detected"):
        validate_snapshot(config, snapshot)
