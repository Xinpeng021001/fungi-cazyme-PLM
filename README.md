# fungi-cazyme-PLM

Fungal structure-aware CAZyme annotation research repository. The first
milestone is a reproducible Phase 0 audit: quantify the fungi/dbCAN HMM gap,
audit function labels and local structure coverage, and make an explicit
go/no-go decision before any model training.

The scientific design is frozen in `project_design.md`. Current status,
decisions, and promoted run identifiers live in `project.md`.

## Safety and data policy

- Existing raw data under sibling projects is read-only.
- Large data are referenced through `configs/data_sources.local.yaml`; they are
  not copied into this repository.
- HMM envelopes are weak supervision, never an independent boundary gold set.
- Family-inherited substrate labels are weak labels, never hard function-test
  labels.
- ESM-C 600M legacy outputs may be audited but are not a release-compatible
  training dependency until licensing is resolved.

## Setup

```bash
conda env create -f envs/base.yaml
conda activate fungi-cazyme-base
python -m pip install -e .
cp configs/data_sources.example.yaml configs/data_sources.local.yaml
```

The checked-in local configuration on the current host is intentionally
gitignored. On another host, edit only that file or set the documented
environment variables.

After validating the first full inventory, set `pinned_snapshot` in the local
config. All non-inventory audit commands will then recompute source hashes and
fail before analysis if an input has drifted.

## Phase 0 commands

```bash
fcplm inventory --config configs/data_sources.local.yaml
fcplm import-aim2 --config configs/data_sources.local.yaml
fcplm phase0 gap --config configs/data_sources.local.yaml
fcplm phase0 labels --config configs/data_sources.local.yaml
fcplm phase0 structures --config configs/data_sources.local.yaml
fcplm report phase0 --config configs/data_sources.local.yaml
```

For a small deterministic check, run `make phase0-smoke`. `make phase0`
executes the full CPU audit and does not train a model or predict structures.
On the current snapshot, the full target intentionally exits non-zero at the
36 protein-alias conflicts. The already-valid downstream components can be
rerun independently with `--skip-aliases`; the promoted blocked decision and
component run IDs are recorded in `docs/00_phase0_decision_memo.md`.

Every command creates an append-only machine run under `logs/<run_id>/` and a
separate result directory under `results/phase0/<run_id>/`. Generated data are
not silently overwritten.

To retry a failed/partial run, pass `--resume <run_id>`. Resume requires the
same config hash and a pinned full snapshot, revalidates all inputs, and creates
a new immutable run whose manifest records `resume_from_run_id`; it never
overwrites the failed run.
