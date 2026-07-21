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
9. GPU visibility currently fails; the official ESM-2 ceiling probe remains
   blocked and legacy ESM-C results are not an equivalent substitute.
10. Aim2 collapses versioned JGI labels for two namespaces, yielding 36
    different-sequence canonical ID conflicts; aliases cannot yet be promoted.
11. The 2025 fungal FASTA contains 68,811 accession-style records without a
    JGI genome field. They are retained with `unresolved_genome`, not assigned
    a fabricated taxonomy.
12. The comparison table contains a known malformed footer row and 1,196
    normalized genome labels, while the family-support set contains 1,198.
