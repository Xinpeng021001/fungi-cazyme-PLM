from collections import Counter

import pytest

from fungi_cazyme_plm.data.identifiers import (
    cazy_class,
    family_base,
    is_fam0,
    parse_cazy_header,
    parse_jgi_header,
    resolve_genome_alias,
    split_annotation,
)


def test_parse_cazy_2024_header() -> None:
    parsed = parse_cazy_header("1|Test1_GeneCatalog.faa|GH1|CBM1")
    assert (parsed.original_id, parsed.genome_id) == ("1", "Test1")
    assert parsed.families_raw == ("GH1", "CBM1")


def test_parse_cazy_2025_header() -> None:
    parsed = parse_cazy_header("GH1_2|12345|Test1_GeneCatalog.faa")
    assert parsed.original_id == "12345"
    assert parsed.genome_id == "Test1"
    assert parsed.families_raw == ("GH1_2",)


def test_parse_accession_style_cazy_header_without_inventing_a_genome() -> None:
    parsed = parse_cazy_header("AJP85509.1|CBM1|CE1|3.1.1.1")
    assert parsed.original_id == "AJP85509.1"
    assert parsed.genome_id == "unresolved_genome"
    assert parsed.families_raw == ("CBM1", "CE1")
    assert parsed.identifier_type == "accession"


@pytest.mark.parametrize(
    ("raw", "base", "klass"),
    [
        ("GH5_7.hmm", "GH5", "GH"),
        ("'AA18'", "AA18", "AA"),
        ("CBM1", "CBM1", "CBM"),
    ],
)
def test_family_normalization(raw: str, base: str, klass: str) -> None:
    assert family_base(raw) == base
    assert cazy_class(raw) == klass


def test_annotations_are_multisets_and_fam0_is_open_set() -> None:
    assert split_annotation("GH1+GH1+CBM1_2") == Counter({"GH1": 2, "CBM1": 1})
    assert is_fam0("GH0")
    assert not is_fam0("GH10")


def test_jgi_identifier_variants() -> None:
    assert parse_jgi_header("jgi|Test1|42|description").original_id == "42"
    assert parse_jgi_header("jgi-Test1-42-description").genome_id == "Test1"
    assert parse_jgi_header("42", "Test1").original_id == "42"


def test_versioned_genome_aliases_are_explicit() -> None:
    known = {"AcreTS7", "LlaRV95", "Pgt_A1"}
    assert resolve_genome_alias("AcreTS7_1", known)[0] == "AcreTS7"
    assert resolve_genome_alias("LlaRV95_379_1", known)[0] == "LlaRV95"
    assert resolve_genome_alias("Pgt_201_A1", known)[0] == "Pgt_A1"
    assert resolve_genome_alias("unknown_1", known)[0] is None
