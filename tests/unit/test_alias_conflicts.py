from dataclasses import replace
from pathlib import Path

import pytest

from fungi_cazyme_plm.config import load_config
from fungi_cazyme_plm.data.aim2_import import import_protein_aliases
from fungi_cazyme_plm.errors import ValidationError
from fungi_cazyme_plm.provenance import RunContext


FIXTURE_CONFIG = Path(__file__).parents[1] / "fixtures" / "config.yaml"


def test_duplicate_canonical_alias_is_a_hard_failure(tmp_path: Path) -> None:
    comparison = tmp_path / "comparison.tsv"
    comparison.write_text(
        "protein_id\tgenome\tcazy_annotation\tdbcan_annotation\tresult\n"
        "1\tTest1\tGH1\tGH1\tsame\n",
        encoding="utf-8",
    )
    proteomes = tmp_path / "proteomes"
    proteomes.mkdir()
    (proteomes / "Test1_GeneCatalog.faa").write_text(
        ">jgi|Test1|1|exact\nMKTAA\n", encoding="utf-8"
    )
    (proteomes / "Test1_1_GeneCatalog.faa").write_text(
        ">jgi|Test1_1|1|versioned\nGGGGG\n", encoding="utf-8"
    )
    config = load_config(FIXTURE_CONFIG)
    sources = dict(config.sources)
    sources["aim2_protein_comparison"] = {"path": str(comparison), "kind": "file"}
    sources["aim2_proteomes"] = {"path": str(proteomes), "kind": "directory"}
    outputs = {key: tmp_path / key for key in config.outputs}
    config = replace(config, outputs=outputs, sources=sources)

    with pytest.raises(ValidationError, match="duplicate_conflicts=1"):
        with RunContext(config, "alias-conflict-test") as run:
            import_protein_aliases(config, run)
    conflict_tables = list((outputs["results_dir"]).glob("*/protein_alias_conflicts.tsv.gz"))
    assert len(conflict_tables) == 1
