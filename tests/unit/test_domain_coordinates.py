import pytest

from fungi_cazyme_plm.data.aim2_import import valid_1based_inclusive


@pytest.mark.parametrize(
    ("start", "end", "length", "valid"),
    [
        (1, 1, 1, True),
        (1, 100, 100, True),
        (0, 10, 100, False),
        (11, 10, 100, False),
        (1, 101, 100, False),
    ],
)
def test_one_based_inclusive_coordinates(start: int, end: int, length: int, valid: bool) -> None:
    assert valid_1based_inclusive(start, end, length) is valid
