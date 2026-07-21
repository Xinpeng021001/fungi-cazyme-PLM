from pathlib import Path

from fungi_cazyme_plm.data.inventory import inspect_file


def test_trailing_blank_line_is_not_a_record(tmp_path: Path) -> None:
    source = tmp_path / "table.tsv"
    source.write_text("name\nvalue\n\n", encoding="utf-8")
    row = inspect_file("table", source, {"expected_records": 1}, quick=False)
    assert row.record_count == 1
    assert row.validation_status == "ok"


def test_unique_record_inventory_removes_exact_duplicates(tmp_path: Path) -> None:
    source = tmp_path / "table.tsv"
    source.write_text("name\tvalue\na\t1\na\t1\nb\t2\n", encoding="utf-8")
    row = inspect_file(
        "table",
        source,
        {"expected_records": 2, "unique_records": True},
        quick=False,
    )
    assert row.record_count == 2
    assert row.validation_status == "ok"
