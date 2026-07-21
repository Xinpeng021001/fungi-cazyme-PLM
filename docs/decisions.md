# Decisions

## D001 — Independent repository

`fungi-cazyme-PLM` is an independent Git repository. The parent
`/array1/xinpeng` directory contains many large sibling projects and is not the
version-control boundary for this work.

## D002 — Aim2 is read-only

`../aim2_1_compare_cazy_dbcan` is a read-only upstream analysis. This project
records paths, checksums, schemas, and small normalized derivatives; it does
not move, rename, overwrite, or repair upstream artifacts in place.

## D003 — Numeric artifacts outrank narrative text

Final TSV artifacts are authoritative for counts and metrics. Process notes and
reports explain methods but may contain superseded interpretations. Known
examples are documented in `docs/legacy/aim2_reuse.md`.

## D004 — HMM envelopes are weak boundaries

run_dbCAN `Target From/To` coordinates are stored as weak supervision. They
cannot be used as an independent gold standard for a boundary model evaluated
against run_dbCAN.

## D005 — Family substrate mappings are weak labels

Family-level substrate mappings define vocabulary and weak supervision only.
Headline function evaluation requires protein-level characterized evidence.

## D006 — Legacy ESM-C 600M is audit-only

Existing ESM-C 600M embeddings and trained heads can be inventoried and used
to understand prior work. They do not determine the releasable encoder or
license of this project.

## D007 — No mutable latest pointer

Runs are addressed by immutable run IDs. A promoted run is written explicitly
to `project.md`; no `latest` symlink is created.

## D008 — Physical and logical record counts are both retained

The family–substrate file has one exact GH3 duplicate: 1,024 physical rows and
1,023 unique logical records. Function audits deduplicate exact rows while
reporting both counts. MycoCosm metadata currently contains 3,836 data rows;
the older 3,835 narrative value is superseded.

## D009 — Identifier conflicts are blocking, not silently deduplicated

Numeric version suffixes may be resolved with an explicit join method, but 36
canonical keys map to different sequences across two collapsed Aim2 genome
namespaces. The importer writes `protein_alias_conflicts` and exits non-zero.

## D010 — Accession-only CAZy records retain unresolved taxonomy

CAZy accession headers such as `AJP85509.1|GT1` are valid sequence records but
contain no JGI genome field. Their stable accession is retained and genome is
marked `unresolved_genome`; no taxonomy is inferred from the identifier.

## D011 — Current ESMC release and legacy artifacts are separate decisions

D006 remains unchanged for existing legacy ESM-C 600M embeddings, trained
heads, and `*-2024-12` artifacts. The Biohub 2026 ESMC/ESMFold2/SAE release is
a new candidate release whose official repository and model page state MIT
terms and provide local Hugging Face weights, including 6B.

No current artifact is approved merely from its display name. Before use, the
run must archive the exact model card and licence, immutable model and code
revisions, and weights SHA-256 in `model_artifact_manifest`. A current-release
decision is never applied retroactively to an unpinned legacy cache.

## D012 — Sequence-first ESMC roles are fixed for the first pilot

Current ESMC 300M is the schema/throughput smoke model. Current ESMC 600M is
the primary frozen per-task layer-sweep and optional LoRA candidate. ESMC 6B
is limited to a controlled dense upper-bound and layer-60 SAE retrieval pilot.
ESMC 6B SAE is baseline B8, not a replacement for the T3 function decoder.
ESMFold2 is restricted to high-value proteins without PDB/CAZyme3D/AFDB
coverage. ESM-2 650M remains the required continuity baseline.

## D013 — met runs use a clean commit and an immutable wrapper

The authoritative compute directory is
`met.unl.edu:/array1/xinpeng/fungi-cazyme-PLM`. Scientific commands run through
`scripts/remote/met_run.sh`, normally inside `tmux`. The wrapper rejects a
dirty worktree by default and records command arguments, Git commit, host,
selected GPUs, environment, stdout/stderr, exit status, and UTC timestamps in
an immutable run directory. A dirty smoke run can be explicit but cannot be
promoted.
