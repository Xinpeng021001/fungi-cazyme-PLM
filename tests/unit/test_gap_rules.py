from collections import Counter

import pytest

from fungi_cazyme_plm.audit.gap_quantification import (
    RawHit,
    borderline_flags,
    classify_primary,
    wilson_interval,
)


@pytest.mark.parametrize(
    ("expected", "predicted", "models", "outcome"),
    [
        (Counter({"GH1": 1}), Counter({"GH1": 1}), {"GH1"}, "concordant"),
        (Counter({"GH1": 1}), Counter(), {"GH1"}, "missed_entirely"),
        (Counter({"GH1": 1}), Counter({"CBM1": 1}), {"GH1", "CBM1"}, "wrong_family"),
        (Counter({"GH1": 1, "CBM1": 1}), Counter({"GH1": 1}), {"GH1", "CBM1"}, "incomplete_domain_set"),
        (Counter(), Counter({"GH1": 1}), {"GH1"}, "overcall_only"),
        (Counter({"GH0": 1}), Counter(), {"GH1"}, "hmm_model_absent"),
    ],
)
def test_primary_error_precedence(expected, predicted, models, outcome) -> None:
    assert classify_primary(expected, predicted, models) == outcome


def test_wilson_interval_contains_point_estimate() -> None:
    lower, upper = wilson_interval(5, 100)
    assert lower < 0.05 < upper


def test_borderline_threshold_edges() -> None:
    assert borderline_flags(RawHit(1e-13, 0.35, 1.0)) == {"borderline_evalue"}
    assert borderline_flags(RawHit(1e-15, 0.25, 1.0)) == {"borderline_coverage"}
    assert borderline_flags(RawHit(1e-15, 0.35, 1.0)) == set()
    assert borderline_flags(RawHit(1.00001e-13, 0.35, 1.0)) == set()
