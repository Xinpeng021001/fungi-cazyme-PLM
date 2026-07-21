# dbCAN-SF operational project record

**Design source:** `project_design.md`  
**Current milestone:** Phase 0 audit + repository foundation  
**Status vocabulary:** planned / implemented / smoke-tested / validated /
completed / blocked

## Status snapshot

| Work item | Status | Evidence / next action |
|---|---|---|
| Independent repository and schemas | validated | Independent Git boundary; typed schemas and CLI in place |
| External-source inventory | validated | Full 23-source SHA-256 snapshot promoted |
| Aim2 read-only importer | blocked | Family/metadata/domains validated; 36 alias conflicts hard-fail |
| Fungal HMM gap classification | validated | 1,980,140 normalized rows; preliminary rate 32.84% |
| Function-label audit | validated | 390 families/88 polyspecific; protein-level hard labels missing |
| Local structure-availability audit | validated | CAZyme3D exact + MMseqs 90/80 completed; 5.6524% local coverage |
| ESM-2 ceiling probe | blocked | GPU preflight currently fails; legacy ESM-C is not a substitute |
| Independent domain-boundary gold | blocked | No curated/PDB boundary table found locally |
| Phase 0 decision | blocked | Preliminary gap rule says continue; six blocking gates remain |

## Promoted run

The promoted decision report is
`20260720T223947140648Z_f4a32c6e_fcplm-report-phase0---config-configs`.
Its component runs are listed in `docs/00_phase0_decision_memo.md`. The full
source snapshot is `source_snapshot_20260720T223749840028Z_9cd52c2661ae.tsv`
(SHA-256 `ad50b1fba5ec2703747f0b7f37318422f1985eb8e1c0affdcfb3e17dfead51b5`).
No mutable `latest` symlink is used.

## Immediate next actions

1. Adjudicate or namespace the 36 `Lenrap1`/`YarliW29` canonical conflicts.
2. Rerun the complete 2024-MSA seed-identity audit (214,618 planned queries).
3. Restore GPU visibility and run the frozen ESM-2 650M cluster30 ceiling probe.
4. Acquire protein-level characterized labels and make the licence decision.

## Unresolved blockers

- Exact 2025 HMM build seed alignments.
- CAZy clan mapping.
- Protein-level characterized fungal substrate/EC evidence.
- Independent curated or PDB-derived domain boundaries.
- Encoder/release licensing and a functioning GPU environment.
- Thirty-six different-sequence canonical ID collisions; three block the
  current seed-identity query set.
