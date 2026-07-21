# Live limitations

1. CAZy families and dbCAN HMMs share a similarity-derived label history;
   metrics partly measure reproduction of curator/database decisions.
2. Automatically defined non-CAZymes measure operational agreement, not
   biological truth. Novel candidates must not be counted automatically as
   false positives.
3. Family-inherited substrate labels collapse function prediction into family
   lookup unless protein-level evidence and whole-family holdouts are used.
4. HMM envelope coordinates are circular boundary labels.
5. A 2025 HMM seed alignment was not found locally. Identity to the available
   2024 MSA is recorded with an explicit reference-release field.
6. CAZyme3D is a local predicted-structure resource; it must not be reported as
   experimental PDB coverage.
7. ESM-C/ESM-2 pretraining contamination remains possible in temporal splits.
8. MycoCosm gene models can contain fragmented or fused proteins.
9. The official ESM-2 ceiling probe remains absent. A 2026-07-21 read-only
   check sees eight RTX A5500 GPUs on `met`, but the pinned ESM-2/ESMC runtime,
   memory behavior, and cluster30 probe have not been validated. Legacy ESM-C
   results are not an equivalent substitute.
10. Aim2 collapses versioned JGI labels for two namespaces, yielding 36
    different-sequence canonical ID conflicts; aliases cannot yet be promoted.
11. The 2025 fungal FASTA contains 68,811 accession-style records without a
    JGI genome field. They are retained with `unresolved_genome`, not assigned
    a fabricated taxonomy.
12. The comparison table contains a known malformed footer row and 1,196
    normalized genome labels, while the family-support set contains 1,198.
13. The 2026 ESMC article is a preprint and contains no fungal CAZyme-specific
    benchmark. Its EC-CATH datasets are short, single-domain, and curated; the
    reported results cannot be transferred directly to fungal multi-domain
    proteins.
14. Biohub tutorials use random stratified splits and, in the LoRA example,
    silent truncation at 1,024 tokens. Those settings are demonstrations, not
    acceptable headline evaluation or long-sequence policy for this project.
15. ESMC pretraining uses large UniRef/JGI/MGnify corpora. Temporal CAZy label
    holdout does not prove sequence-level novelty; PLM-seen/unseen strata are
    approximate and must be reported as such.
16. ESMC SAE feature descriptions are agent-generated hypotheses. They may be
    incomplete or wrong for rare fungal biology and must never be written into
    hard substrate, EC, mechanism, or boundary labels.
17. The current Biohub release and legacy `*-2024-12` artifacts may have
    different model cards and terms. Current MIT statements do not resolve an
    unpinned legacy cache; every run still requires an exact revision, weight
    hash, and licence snapshot.
18. Long-protein window merging can create boundary artifacts and duplicate
    evidence. Window coordinates, overlaps, domain coverage, and merge method
    are part of the model artifact and require explicit tests.
19. The present met GPUs have 24 GB each. ESMC 6B and ESMFold2 may require
    sharding, lower precision, or smaller batches; tutorial H100 runtimes are
    not valid cost estimates for this environment.
