# Aim2 reuse contract

**Upstream:** `/array1/xinpeng/aim2_1_compare_cazy_dbcan`  
**Mode:** read-only  
**Primary date:** 2026-07-19

## Authority order

1. Final TSV/JSON artifacts under `scores/` and `results/`.
2. Exact command/process logs under `docs/process/`.
3. `SUMMARY_2026-07-19_2117.md` and `REPORT.md`.
4. Older narrative statements.

## Known corrections and inconsistencies

- AA7 was once described as mostly CAZy under-annotation. Later DIAMOND,
  phylogenetic, and plant-BBE tests support genuine superfamily over-calling;
  the later conclusion is authoritative.
- `PROJECT.md` text cites 527,942 fungal truth proteins while
  `scores/jgi_fungi/build_stats.tsv` records 527,941. This project preserves
  the numeric artifact count and logs the discrepancy.
- `generalizes=yes` can include zero-gain/no-harm cases; actionable retuning
  must also require a positive held-out F1 gain.
- The fungal raw score table lacks `overlap_kept`; overlap loss must be
  reconstructed from pre-overlap scores and per-genome post-filter outputs or
  reported unavailable.
- The current MycoCosm metadata has 3,836 data rows. The earlier 3,835 value was
  an inventory discrepancy, not a change to the 1,198-genome evaluation set.
- `compare_no-subfam.tsv` has 1,980,141 physical data rows, but its final row is
  a known malformed header-like sentinel (`protein_id`, `genome`,
  `cazyme_annotation`, `-`, `different-fn`). Normalized audits retain the source
  count, exclude exactly this one row, and fail if the anomaly count changes.
- Some Aim2 comparison genome IDs omit numeric JGI release suffixes. Alias import
  resolves only explicit suffix stripping plus the observed `Pgt_201_A1/B1` to
  `Pgt_A1/B1` rule and records the join method; it does not merge source records.
- The suffix normalization exposes 36 canonical-key collisions across
  `Lenrap1`/`Lenrap1_155` and `YarliW29`/`YarliW29_1`; all paired sequences
  differ. The alias importer emits a conflict table and fails instead of
  selecting one source record silently.

## Reused artifacts

- `scores/jgi_fungi/jgi_fungi_hmm_evaluation.tsv`
- `scores/jgi_fungi/hits.tsv`
- `scores/jgi_fungi/genome_support.tsv`
- `compare_results/new_results_no_subfam/compare_no-subfam.tsv`
- `compare_results/new_results_no_subfam/protein_domain.result_no-subfam.tsv`
- `results/overcall_assessment.tsv`
- `JGI_sequence_dbCAN/*/dbCAN_hmm_results.tsv`

No upstream artifact is edited by the importer.
