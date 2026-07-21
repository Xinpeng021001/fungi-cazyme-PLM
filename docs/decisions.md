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
