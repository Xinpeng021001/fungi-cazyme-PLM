# Phase 0 initial audit

## Purpose

Implement and exercise the Phase 0 repository foundation without training a
PLM, running DAPT, or predicting new structures. Existing Aim2 and legacy
artifacts were treated as read-only inputs.

## Input snapshot

- Full inventory run: `20260720T223727868017Z_f4a32c6e_fcplm-inventory---config-configs-dat`
- Snapshot: `source_snapshot_20260720T223749840028Z_9cd52c2661ae.tsv`
- Snapshot SHA-256: `ad50b1fba5ec2703747f0b7f37318422f1985eb8e1c0affdcfb3e17dfead51b5`
- Sources: 23 logical sources and 2,635 directory members

## Commands

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python -m fungi_cazyme_plm.cli inventory --config configs/data_sources.local.yaml
PYTHONPATH=src .venv/bin/python -m fungi_cazyme_plm.cli import-aim2 --config configs/data_sources.local.yaml
PYTHONPATH=src .venv/bin/python -m fungi_cazyme_plm.cli import-aim2 --config configs/data_sources.local.yaml --skip-aliases
PYTHONPATH=src .venv/bin/python -m fungi_cazyme_plm.cli phase0 gap --config configs/data_sources.local.yaml
PYTHONPATH=src .venv/bin/python -m fungi_cazyme_plm.cli phase0 labels --config configs/data_sources.local.yaml
PYTHONPATH=src .venv/bin/python -m fungi_cazyme_plm.cli phase0 structures --config configs/data_sources.local.yaml --threads 16
PYTHONPATH=src .venv/bin/python -m fungi_cazyme_plm.cli phase0 seed-identity --config configs/data_sources.local.yaml --threads 16
```

## QC and results

- Tests: 30 passed, including deterministic output checks, drift detection,
  CAZy/JGI headers, fam-0, multiset logic, coordinates, threshold edges,
  Latin-1 metadata, AA18 quoting, and duplicate-conflict failure.
- Aim2: 511 family rows; 1,198/1,198 policy-valid genomes; 536,133 weak
  domains; no coordinate errors.
- Alias audit: 1,980,140 expected keys, no missing keys, 36 conflicting keys;
  all paired sequences differ. The run failed intentionally.
- Gap: 728,439 truth family instances; 239,217 preliminary addressable misses;
  rate 0.328397, 95% Wilson CI 0.327319–0.329476.
- Function: 1,023 unique mappings, 390 families, 88 high-level polyspecific;
  no protein-level characterized hard labels.
- Structure: 13,951 exact plus 15,720 non-exact 90/80 CAZyme3D matches;
  29,671/524,926 total local-reference coverage (5.6524%).
- Seed identity: 211 families and 214,618 queries planned; three queries have
  different-sequence identifier conflicts, so the command failed before search.

## Interpretation and limitations

The preliminary gap-only CI is entirely above 5%, but it is not a final go
decision. Protein aliases, 2024 seed identity, the ESM-2 ceiling probe,
protein-level function labels, independent boundaries, and licensing remain
blocking. CAZyme3D is a predicted-reference source and is not counted as
experimental PDB or direct AFDB coverage.

## Next action

Adjudicate or namespace the 36 alias conflicts (starting with the three seed
queries), rerun seed identity, then execute the official frozen ESM-2 cluster30
probe only after GPU preflight succeeds.
