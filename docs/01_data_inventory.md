# Data inventory

The machine-readable catalog is `data/manifests/source_catalog.tsv`. A full
inventory run writes an immutable source snapshot under
`data/manifests/snapshots/` and records its digest in the run log.

## Confirmed local resources

- Aim2 fungal HMM evaluation and per-genome run_dbCAN outputs.
- CAZy fungal FASTA snapshots for 2024 and 2025.
- dbCAN HMM databases for 2024 and the current 875-model release.
- 2024 family MSAs only; exact 2025 build alignments are missing.
- MycoCosm metadata for all 1,198 evaluated genomes; all are published and
  non-restricted in the supplied snapshot.
- Current family–substrate mapping.
- CAZyme3D ID50 sequences/archive.
- Legacy temporal PLM and structure artifacts under `dbcan4-advanced`.

The current family–substrate file contains 1,024 physical rows but 1,023
unique logical records (one exact GH3 duplicate). Audits deduplicate the exact
row and report both counts. The current MycoCosm CSV contains 3,836 data rows;
the earlier 3,835 inventory value is superseded, while the acceptance criterion
remains 1,198/1,198 evaluated genomes matched.

The Aim2 protein comparison table contains 1,980,141 physical rows and one
pre-registered malformed footer row. Its normalized protein-row count is
therefore 1,980,140; both counts are emitted in gap metrics.

## Blocking missing resources

- Independent protein-level characterized substrate/EC table.
- CAZy family-to-clan mapping.
- Independent curated/PDB domain-boundary table.
- Exact 2025 HMM seed alignments.

## Storage rule

The workspace filesystem is already heavily utilized. Large inputs are
referenced in place and never duplicated into this repository.
