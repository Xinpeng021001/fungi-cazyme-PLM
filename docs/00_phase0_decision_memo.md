# Phase 0 decision memo

**Promoted report run:** `20260720T223947140648Z_f4a32c6e_fcplm-report-phase0---config-configs`  
**Decision status:** `blocked_pending_phase0_gates`

## Executive result

The preliminary addressable family-instance error rate is **0.3284** (95%
Wilson CI 0.3273–0.3295; pre-registered threshold 0.0500). The gap-only rule
therefore points to `continue_family_structure_claims`, but this is not a final
go decision while the blockers below remain open. No model training is
authorized by this memo.

## Immutable evidence runs

| Component | Run ID | Status |
|---|---|---|
| Full source inventory | `20260720T223727868017Z_f4a32c6e_fcplm-inventory---config-configs-dat` | completed |
| Aim2 family/metadata/domain import | `20260720T223920770299Z_f4a32c6e_fcplm-import-aim2---config-configs-d` | completed; aliases deliberately skipped |
| Protein alias integrity | `20260720T221212689966Z_f4a32c6e_fcplm-import-aim2---config-configs-d` | failed as required: 36 conflicts |
| Gap quantification | `20260720T223114389420Z_f4a32c6e_fcplm-phase0-gap---config-configs-da` | completed |
| Function-label audit | `20260720T221758618977Z_f4a32c6e_fcplm-phase0-labels---config-configs` | completed |
| CAZyme3D 90/80 audit | `20260720T221927641266Z_f4a32c6e_fcplm-phase0-structures---config-con` | completed |
| 2024 seed identity | `20260720T223424899864Z_f4a32c6e_fcplm-phase0-seed-identity---config-` | blocked by 3 conflicting query IDs |

The promoted full snapshot is
`source_snapshot_20260720T223749840028Z_9cd52c2661ae.tsv` with SHA-256
`ad50b1fba5ec2703747f0b7f37318422f1985eb8e1c0affdcfb3e17dfead51b5`.

## Evidence table

| Evidence | Result | Status |
|---|---|---|
| Aim2/MycoCosm reuse | 1,198/1,198 genomes matched; all published and non-restricted | complete |
| Protein alias integrity | 36 different-sequence collisions in `Lenrap1` and `YarliW29` namespaces | blocked |
| Weak domains | 536,133 HMM envelopes; zero invalid 1-based inclusive coordinates | complete, weak supervision only |
| HMM gap spectrum | 728,439 truth family instances; 262,137 unmatched; 239,217 preliminary addressable | complete, boundary gold absent |
| HMM database | 875 models representing 510 base families; 2024 snapshot has 826 models | complete |
| Function labels | 1,024 physical rows, 1,023 unique; 390 families; 88 polyspecific | weak labels only |
| CAZyme3D local coverage | exact 13,951; non-exact 90/80 15,720; total 29,671/524,926 (5.6524%) | complete, predicted-reference source |
| Frozen ESM-2 ceiling probe | no official cluster30 result | blocked by GPU preflight |
| Independent boundary evaluation | no curated/PDB boundary table | blocked |
| Licence/release decision | legacy ESM-C 600M is audit-only | blocked |

The comparison source has 1,980,141 physical data rows. One pre-registered
malformed footer is excluded, leaving 1,980,140 normalized protein rows across
1,196 comparison genome labels. This is distinct from the 1,198 genomes in the
family-support/metadata validation because two Aim2 `Pgt_201_*` labels were
collapsed upstream.

## Blocking items

- `protein_alias_integrity`: 36 canonical keys map to two different sequences.
- `seed_identity_2024`: 3 of 214,618 planned queries inherit those conflicts;
  the command exited non-zero before search.
- `ceiling_probe`: official frozen ESM-2 650M cluster30 run is absent.
- `protein_level_function_labels`: no characterized protein-level substrate/EC table.
- `independent_boundary_gold`: HMM envelopes cannot evaluate themselves.
- `licence_release_decision`: encoder and derivative-release terms are unresolved.

## Interpretation safeguards

- fam-0 remains open-set truth and is never used as a negative.
- HMM envelopes are weak supervision and do not score their own boundaries.
- Family-inherited substrate labels do not qualify for hard function evaluation.
- CAZyme3D is reported separately from experimental PDB and direct AFDB coverage.
- Any future seed identity is labelled against the available 2024 MSA, never as 2025 identity.
- The 32.84% addressable estimate is preliminary until alias conflicts and seed identity are adjudicated.

## Recommended next experiment

Manually adjudicate or namespace the 36 canonical ID conflicts, starting with
the 3 seed-query conflicts, then rerun the complete 2024 seed-identity audit.
Only after that should the official ESM-2 ceiling probe be scheduled; no
training should start from the current blocked state.
