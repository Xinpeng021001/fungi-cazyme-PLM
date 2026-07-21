import csv
import gzip
import json
import hashlib
from pathlib import Path

from fungi_cazyme_plm.cli import main


FIXTURE_CONFIG = Path(__file__).parents[1] / "fixtures" / "config.yaml"
RESULT_ROOT = Path("/tmp/fcplm-fixture/results")


def test_phase0_fixture_smoke() -> None:
    before = set(RESULT_ROOT.glob("*")) if RESULT_ROOT.exists() else set()
    assert main(["smoke", "--config", str(FIXTURE_CONFIG)]) == 0
    created = set(RESULT_ROOT.glob("*")) - before
    assert len(created) == 1
    result = created.pop()

    gap = json.loads((result / "gap_metrics.json").read_text(encoding="utf-8"))
    assert gap["comparison_rows"] == 6
    assert gap["truth_family_instances"] == 6
    assert gap["primary_error_counts"] == {
        "concordant": 1,
        "hmm_model_absent": 1,
        "incomplete_domain_set": 1,
        "missed_entirely": 1,
        "overcall_only": 1,
        "wrong_family": 1,
    }

    with gzip.open(result / "gap_cases.tsv.gz", "rt", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    gh1_miss = next(row for row in rows if row["canonical_id"].endswith(":2"))
    cbm1_miss = next(
        row for row in rows if row["canonical_id"].endswith(":4") and row["family_base"] == "CBM1"
    )
    fam0 = next(row for row in rows if row["family_base"] == "GH0")
    assert "borderline_evalue" in gh1_miss["error_flags"]
    assert "borderline_coverage" in cbm1_miss["error_flags"]
    assert "fam0_open_set" in fam0["error_flags"]
    assert fam0["hmm_present"] == "false"

    function = json.loads((result / "function_label_audit.json").read_text())
    assert function["unique_families"] == 2
    assert function["high_level_polyspecific_families"] == 1
    structure = json.loads((result / "structure_availability.json").read_text())
    assert structure["exact_sequence_matches"] == 1
    assert structure["near_search_status"] == "not_run"
    report = json.loads((result / "phase0_report_summary.json").read_text())
    assert report["final_status"] == "blocked_pending_phase0_gates"

    before_second = set(RESULT_ROOT.glob("*"))
    assert main(["smoke", "--config", str(FIXTURE_CONFIG)]) == 0
    second = (set(RESULT_ROOT.glob("*")) - before_second).pop()
    for filename in ("gap_cases.tsv.gz", "function_labels_normalized.tsv.gz", "structure_availability.tsv.gz"):
        first_hash = hashlib.sha256((result / filename).read_bytes()).hexdigest()
        second_hash = hashlib.sha256((second / filename).read_bytes()).hexdigest()
        assert first_hash == second_hash
