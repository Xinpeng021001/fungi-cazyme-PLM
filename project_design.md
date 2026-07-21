# Fungal Structure-Aware CAZyme Annotation Project — Design v2

**Project root:** `/array1/xinpeng/fungi-cazyme-PLM`
**Working title:** dbCAN-SF (Structure + Function) — fungal structure-aware CAZyme annotation and function decoding

Do not delete, rename, move, or overwrite any existing raw data.
The project is developed as a reproducible research repository, not a collection of scripts.

---

# 0. What changed from v1, and why

| # | v1 | v2 | Reason |
|---|----|----|--------|
| 1 | Started at data audit | Starts at **Phase 0 gap quantification + go/no-go probe** | v1 never tested its own premise that HMMs are insufficient for fungi |
| 2 | Novelty = "PLM for CAZyme annotation" | Novelty = **structure fusion + function decoding + fungal domain-level resolution** | CAZyLingua (BMC Bioinf 2025) and CAALM (2026) already occupy sequence-only PLM CAZyme annotation |
| 3 | Binary CAZyme classification was Task A | Binary is **demoted to a byproduct** of residue-level labeling | The v1 negative set was defined by dbCAN's own decision boundary → structurally caps performance at "agree with dbCAN" and scores real discoveries as false positives |
| 4 | Protein-level single/multi-label | **Residue-level token classification → domain pooling** | Fungal CAZymes are multi-modular (GH+CBM+linker+O-glyc region); protein-level single labels are biologically wrong for a large minority |
| 5 | Family softmax over closed set | **Function decoder into a semantic label space** built from the fam–substrate table | Enables zero-shot on unseen families; neither CAZyLingua nor CAALM can do this by construction |
| 6 | SaProt as "Stage 4, maybe" | Structure is a **primary novelty axis** with a falsifiable clan-level hypothesis, and Foldseek retrieval is added as its mandatory baseline | Structure was under-specified in v1 and its strongest baseline was missing |
| 7 | Fungal DAPT was a core hypothesis | **Demoted to optional, gated by a pre-registered kill criterion** | Highest cost, weakest evidence, plus MycoCosm data-use and ESM licence constraints |
| 8 | Temporal split described | Temporal split **plus version-matched baselines** and PLM-pretraining-contamination stratification | Comparing a model trained on old CAZy against HMMs built from new CAZy is not a valid test |
| 9 | No cost metrics | Runtime, memory, CPU-only feasibility are **first-class evaluation metrics** | A GPU-only tool that is 50x slower than HMMER will not be adopted by dbCAN users |
| 10 | fam-0 analysis was descriptive | **Retrospective fam-0 resolution** as a quantitative benchmark | CAZy GH0 holds ~126k entries but only 14 characterized — no ground truth otherwise |
| 11 | Licence/data policy unaddressed | **Blocking decisions in Phase 0** | ESM-C 600M weights are non-commercial and derivative weights inherit the licence; MycoCosm requires a genome reference or PI permission |

---

# 1. Positioning and novelty

**This section governs every other section. If a planned experiment does not serve a claim below, it is optional.**

## 1.1 Competitive landscape (as of 2026-07)

| Tool | Representation | Granularity | Output | Structure | Open-set |
|------|---------------|-------------|--------|-----------|----------|
| dbCAN / run_dbCAN V5 | HMM + DIAMOND + dbCAN-sub | domain (HMM envelope) | family, subfamily, EC, substrate | no | no |
| CAZyLingua (BMC Bioinformatics 2025) | ProtT5 embeddings + QDA + multiclass classifier | whole protein | family / subfamily | no | no |
| CAALM (2026, Apache-2.0, PyPI/Bioconda) | PLM embeddings, 3-level: binary → multi-label class → FAISS retrieval of family | whole protein | family only | no | not exposed |
| eCAMI / CUPP | k-mer / peptide clustering | protein | family, subfamily | no | no |

Conclusions that must be reflected in all writing:

1. "First PLM for CAZyme annotation" is **taken**. Do not claim it.
2. "PLM matches HMM on family assignment" is an **already-published result**, not a finding. CAZyLingua reported parity with HMM-based methods, beating only pure homology search.
3. What no published tool does: **structure-aware representation**, **domain-level resolution with boundaries**, **function/substrate decoding that generalizes to unseen families**, and **fungal specialization**.
4. CAALM's Level 2 is already retrieval-based (learned projection + FAISS). Therefore "contrastive retrieval over family labels" is **not by itself novel**. Novelty must come from what the retrieval is *into* — a function space, not a family-label space.

## 1.2 The three claims

**Claim 1 — Structure carries complementary signal, and we can say exactly where.**

Not "we added structure and it helped." The specific, falsifiable hypothesis:

> CAZy families are defined by sequence similarity, but CAZy **clans** are defined by fold. Therefore structural representation should improve (a) CAZyme detection, (b) clan assignment, (c) remote-homolog family assignment below ~30% identity, and (d) fam-0 placement — and should provide **little or no gain** for within-clan family discrimination among well-populated families, because families inside a clan share a fold.

This hypothesis predicts a specific *pattern* of results, including where the method should fail. Reporting that pattern is the contribution. A flat "fusion is better" table is not.

Supporting precedent to cite: new GH families are routinely assigned to clans via structural similarity (e.g. GH192/193/194 → clan GH-S), which is exactly the operation this model is asked to automate.

**Claim 2 — Function decoding generalizes to families the model has never seen.**

Existing tools output a family label from a closed set. This project outputs a position in a **function space** (substrate × linkage × EC × mechanism × mode), built from the lab's curated family–substrate table plus protein-level evidence.

Decisive experiment: **leave-whole-families-out**. Hold out entire CAZy families from training. Predict substrate/EC for their members with no family label available. A closed-set classifier scores 0 by construction. This is the single most differentiating experiment in the project.

**Claim 3 — Fungal, domain-level resolution.**

Fungal secreted CAZymes are modular. Residue-level labelling gives domain boundaries and architectures (GH+CBM), which protein-level tools cannot produce, and which feeds downstream CGC/substrate work in the dbCAN ecosystem.

## 1.3 Minimal publishable core

Everything below is required; everything not listed is optional.

1. A fungal benchmark with cluster / taxonomic / temporal / family-holdout splits and a leakage report.
2. Version-matched dbCAN, DIAMOND, Foldseek, CAZyLingua, CAALM baselines.
3. Sequence-only PLM ceiling (frozen + LoRA).
4. Structure retrieval baseline and structure-aware PLM, with the clan-level hypothesis tested.
5. Function decoder with leave-families-out zero-shot evaluation and the family→substrate lookup baseline.
6. Retrospective fam-0 resolution.
7. Runtime/memory table.

Fungal DAPT, full-proteome discovery, and multi-task EC prediction are **extensions**, not core.

---

# 2. Phase 0 — go/no-go (2 weeks, do this before anything else)

Five deliverables, all small, all decision-forcing.

## 2.1 Gap quantification

Run run_dbCAN V5 on the fungal CAZy gold set. Classify every disagreement:

* missed entirely (no hit);
* wrong family;
* right family, wrong boundaries;
* borderline E-value (within 1–2 orders of the threshold);
* multi-domain protein with an incomplete domain set;
* family present in CAZy but absent from the dbCAN HMM release.

Report the error spectrum by CAZy class, family size, taxonomic group, and sequence identity to the nearest dbCAN HMM seed.

**Decision rule:** if the total addressable error on fungi is below ~5% and is concentrated in cases a PLM cannot fix (e.g. fragments, gene-model errors), the family-assignment framing is dead and the project pivots to Claim 2 only (function decoding / within-family functional divergence).

## 2.2 Ceiling probe

30 largest fungal GH families, MMseqs2 cluster split at 30% identity, frozen ESM-2 650M mean-pooled embeddings + logistic regression, versus dbCAN HMM. Report macro-F1 on the low-identity stratum only.

One number. It sets expectations for everything downstream.

## 2.3 Function-label audit

Audit the existing family–substrate table:

* granularity — family or subfamily?
* single substrate per family or multi?
* controlled vocabulary or free text?
* coverage — how many families, which classes?
* provenance — literature, CAZy activities, dbCAN-sub, manual?

Then count, separately, **protein-level** substrate/EC evidence: CAZy characterized entries for fungi, BRENDA entries, entries with PDB structures. This count determines whether Claim 2 is viable — see §5.3.

## 2.4 Structure availability audit

For the fungal CAZy set, count: experimental PDB structures; AFDB entries reachable at ≥90% identity / ≥80% coverage; the remainder needing prediction. Reuse the CAZyme3D procedure and, where possible, CAZyme3D structures directly.

## 2.5 Blocking legal decisions

See §12. Produce a one-page decision memo. Do not start any training that depends on an undecided item.

**Phase 0 output:** `docs/00_phase0_decision_memo.md` with the error spectrum, the probe number, label counts, structure counts, and the licence/data decisions. Everything after this is conditional on it.

---

# 3. Data sources and audit

## 3.1 Sources and their roles

| Source | Role | Trust |
|--------|------|-------|
| CAZy fungal annotations | primary positive labels | high, but stratify by evidence |
| CAZy characterized subset | protein-level function labels; hard evaluation set | highest |
| CAZyme3D | structures + intra/inter-family structural clusters | in-house, reuse directly |
| family–substrate table | function label space | see §5.3 caveat |
| dbCAN-sub | subfamily → EC/substrate mapping; substrate baseline | in-house baseline |
| MycoCosm proteomes | matched negatives, taxonomic evaluation, discovery, optional DAPT | weak; automated gene models |
| dbCAN annotations on MycoCosm | weak labels, baseline, candidate list | **never gold standard** |

Preserve evidence type on every label. Never collapse "experimentally characterized" and "assigned by sequence similarity" into one label column.

## 3.2 Audit requirements

The audit must report, in addition to the v1 list (proteome/protein/taxon counts, length distribution, non-standard residues, duplicate IDs and sequences, near-duplicates, class/family/subfamily/EC counts, multi-domain and conflicting labels, cross-source overlap, imbalance, missing metadata):

* per-family counts split by evidence type;
* number of proteins with ≥2 CAZy domains, and the domain-architecture distribution;
* number of fungal proteins with usable domain-boundary information, by source;
* structure availability per protein (PDB / AFDB / needs prediction) and pLDDT distribution where known;
* family–substrate table coverage joined onto the protein table;
* polyspecific families (families with >1 distinct substrate or >1 EC at the family level) — flagged explicitly;
* MycoCosm genomes with a published genome reference versus without (see §12.2);
* fam-0 counts for fungi, by class and by CAZy release.

Use stable sequence hashes to trace proteins across files. Parquet for processed tables, TSV for human-readable summaries.

## 3.3 Canonical protein/domain table

v1's canonical table was protein-level. v2 needs **two** tables.

`proteins.parquet`:

```text
canonical_id, original_id, source_database, genome_id, genome_published_ref,
species, genus, family, order, class, phylum,
sequence_hash, sequence_length, evidence_type, dataset_role,
structure_source, structure_path, mean_plddt
```

`domains.parquet`:

```text
canonical_id, domain_index, start, end, boundary_source, boundary_confidence,
cazy_class, cazy_family, cazy_subfamily, clan, ec_number,
substrate_label, substrate_label_source, substrate_label_level
```

`boundary_source` ∈ {cazy_curated, pdb, dbcan_hmm_envelope, structure_parse, none}.
`substrate_label_level` ∈ {protein, subfamily, family} — this field is what keeps §5.3 honest.

---

# 4. Tasks

v1's five tasks are restructured into four, because A and B collapse into one residue-level task.

## T1 — Residue-level CAZyme labelling (replaces v1 Task A + B)

Per residue, predict one of `{non-CAZyme, GH, GT, PL, CE, AA, CBM}`.
Post-process contiguous runs into domain segments.

Outputs: protein-level binary CAZyme call (byproduct), class multi-label (byproduct), and **domain boundaries** (new).

Evaluated as: per-residue macro-F1; domain-level precision/recall at IoU ≥ 0.5 and ≥ 0.75; boundary offset distribution against HMMER envelopes and against curated/PDB boundaries.

**Boundary-label problem — resolve in Phase 1, it is blocking.** CAZy does not systematically publish domain boundaries. Options, in descending order of quality:

1. curated/PDB boundaries for the characterized subset — gold, small;
2. structure-derived domain parsing on AF2/AFDB models (Chainsaw/Merizo-style) — independent of the baseline, medium size;
3. dbCAN HMM envelopes — large, but **circular**, since the baseline defines the labels.

Use (3) only as weak supervision for training, never for evaluation. Evaluate on (1) and (2). State this split explicitly in the paper.

## T2 — Domain-level family assignment

Per domain segment, predict CAZy family. Auxiliary head: **clan** (this is what tests Claim 1).

Report separately for abundant / medium / rare families, families absent from training, multi-domain proteins, and identity strata.

Minimum family support is configurable (10 / 20 / 50 / 100). Families below threshold move to the retrieval/function path rather than the softmax.

## T3 — Function decoding (new, Claim 2)

Per domain segment, predict a position in function space and decode to: substrate, linkage/anomeric specificity where available, EC (hierarchical), mechanism (retaining/inverting), and mode (endo/exo) where labelled.

Evaluated in three regimes:

* **seen families** — versus dbCAN-sub and versus the family→substrate lookup baseline;
* **held-out families (zero-shot)** — the decisive experiment;
* **characterized-only** — protein-level labels, no family inheritance.

## T4 — Open-set / fam-0

See §10. Not a classification task; a ranking and calibration task with a retrospective ground truth.

**Removed from v1:** standalone protein-level binary classification with an elaborate curated negative set as a headline task. It remains as a byproduct of T1 and as a diagnostic, for the reason in §5.2.

---

# 5. Label design and the three circularity problems

This project has three distinct circularity risks. Each needs an explicit mitigation, and each mitigation belongs in the paper's limitations section.

## 5.1 Circularity 1 — CAZy labels are themselves similarity-derived

CAZy families are defined by sequence similarity, and dbCAN HMMs are built from CAZy family members. A model supervised on CAZy labels learns to reproduce a similarity-based labelling function; the sequence-homology baseline is therefore unusually strong by construction.

Mitigations:

* report by identity stratum, and treat the low-identity stratum as the headline result;
* use the temporal split with **version-matched baselines** (§6.3);
* prioritize the characterized subset, where labels have independent experimental support;
* frame gains as "recovers curator decisions the HMM misses", not "beats CAZy".

## 5.2 Circularity 2 — negatives defined by the baseline

**This was the most damaging flaw in v1.** If negatives are "no dbCAN hit and no CAZyme-associated Pfam domain and no CAZy homolog", then:

* the label function is dbCAN's decision boundary;
* the achievable ceiling is agreement with dbCAN;
* every true discovery — a CAZyme dbCAN missed — is scored as a **false positive**;
* the more thorough the exclusion pipeline, the worse this gets.

Mitigations:

1. **Do not headline protein-level binary classification.** It becomes a byproduct of T1 and a diagnostic.
2. Build a **curated hard-case test set** of 200–500 fungal proteins with orthogonal evidence: characterized non-CAZymes, characterized CAZymes missed or borderline in dbCAN, structural homologs without sequence homology, proteins from the Phase 0 error spectrum. Manual review is expected and is the point. Tool-paper credibility comes from this set, not from a million automatically-labelled negatives.
3. Where automatic negatives are used, keep the v1 taxonomy (matched negatives, hard negatives) but relabel every metric computed on them as **operational agreement**, not accuracy.
4. Report the **discovery-rate/precision trade-off** explicitly: for candidates the model calls positive and dbCAN calls negative, report the fraction supported by independent evidence (structure, characterized homolog, genomic context) instead of counting them as errors.

## 5.3 Circularity 3 — family-level substrate labels (threatens Claim 2)

If every member of family F inherits F's substrate from the family–substrate table, then substrate prediction is exactly family prediction composed with a lookup, and the function decoder demonstrates nothing.

Mitigations, all mandatory:

1. `substrate_label_level` is recorded on every label (protein / subfamily / family).
2. **Protein-level labels are the only evidence used for the hard evaluation.** Family-inherited labels may shape the label space and provide weak supervision; they may not serve as test labels for a headline claim.
3. **Polyspecific families are handled explicitly.** GH5, GH13, GH16, GH30, AA9 and similar families carry multiple activities; a single family-level substrate is wrong there. Treat them as multi-label, or exclude them from family-inherited supervision and keep them for the characterized-only evaluation — where they are, in fact, the most interesting cases.
4. **The lookup baseline is mandatory and must be reported next to every function-decoder result:** predict the family with dbCAN, then map through the family–substrate table. If the decoder does not beat that baseline on held-out families and on the characterized-only set, Claim 2 fails. Report it either way.
5. **Zero-shot evaluation holds out whole families**, so the lookup is unavailable at test time by construction.

---

# 6. Splits and leakage

Retain all of v1 §5, with four additions.

## 6.1 Sequence-cluster split

MMseqs2 clustering before splitting, thresholds 90/70/50/40/30%. Record identity threshold, coverage threshold, clustering mode, representative selection, and cluster-to-partition allocation. Close homologs must not cross partitions.

## 6.2 Taxonomic holdout

Species / genus / family / order holdouts. For fungi, order-level holdout is the meaningful one — species holdout is nearly free given MycoCosm redundancy.

## 6.3 Temporal holdout — with version-matched baselines (NEW)

Train on CAZy release *N*, test on entries added by release *N+k*.

**Every baseline must be rebuilt or downgraded to release *N*.** Comparing a model trained on old CAZy against dbCAN HMMs built from current CAZy is not a valid test, and reviewers will catch it. Record the exact CAZy release, the dbCAN database version, and the CAZyLingua/CAALM model versions used, and state whether their training data postdates *N*. Where a competitor cannot be retrained, say so and interpret its numbers as an upper bound.

## 6.4 Family-holdout split (NEW — for T3 zero-shot)

Hold out entire families, stratified by class and by size, so held-out families have no member in training. Two variants:

* **within-clan holdout** — a related family remains in training (easier; tests interpolation);
* **whole-clan holdout** — the entire clan is withheld (harder; tests genuine extrapolation).

Report both. The gap between them is itself a result.

## 6.5 PLM pretraining contamination (NEW)

Temporal splits do not fix this. ESM-2 and ESM-C were pretrained on UniRef, which contains essentially all CAZy proteins; a protein added to CAZy in 2025 was probably in the PLM's pretraining corpus in 2021, merely unannotated.

Required:

* record each encoder's pretraining corpus and cutoff in the model card;
* partition the test set into **PLM-seen** and **PLM-unseen** strata by that cutoff (approximate via UniProt first-seen date);
* report headline metrics on both strata.

This stratification is itself a methodological contribution — no CAZyme PLM paper has reported it.

## 6.6 Leakage report

Per split: maximum train-to-test identity; shared hashes, identifiers, genomes, taxa, clusters; database-version overlap; PLM-contamination stratum sizes; and, for T3, confirmation that no held-out family has a training member.

---

# 7. Model architecture

```text
                    protein sequence
                           │
        ┌──────────────────┴──────────────────┐
        │                                      │
   ESM-C / ESM-2                      structure source
   residue embeddings           (PDB → AFDB ≥90/80 → predicted)
        │                                      │
        │                            Foldseek 3Di tokens
        │                                      │
        │                              SaProt encoder
        │                            (AA+3Di residue embeddings)
        │                                      │
        └──────────► gated residue-level fusion ◄──────────┘
                     g = σ(W[h_seq ; h_str ; plddt])
                     h = g ⊙ h_str + (1−g) ⊙ h_seq
                               │
       ┌───────────────────────┼────────────────────────┐
       │                       │                        │
   H1 token head          H2 domain head          H3 function decoder
   per-residue class    (pool over segment)      project domain embedding
   {non-CAZyme, GH,      → family softmax          into function space;
    GT, PL, CE, AA,      → clan head (aux)         score against function
    CBM}                                           prototypes
       │                       │                        │
   boundaries             family / clan        substrate / EC / mechanism
                                                + novelty score
```

## 7.1 Fusion

The gate is conditioned on pLDDT so the model learns to discount unreliable structure. Two properties are required:

* **graceful degradation** — with structure tokens masked, the model must fall back to sequence-only performance. Report this ablation. Without it the tool cannot ship in run_dbCAN, since most query proteins will have no structure.
* **cost-aware** — structure is optional at inference. Measure both paths (§11.4).

Compare, in this order: sequence-only; structure-only; late fusion of independent classifiers; concatenation; gated fusion. Do not report only the winner.

## 7.2 Function decoder (Claim 2)

Function labels are encoded as structured attribute vectors, not free text:

```text
substrate polymer      (cellulose, xylan, chitin, starch, pectin, β-glucan, ...)
linkage / anomeric     (β-1,4, α-1,4, β-1,3, ...)
EC                     (4 hierarchical levels, partial allowed)
mechanism              (retaining / inverting / unknown)
mode                   (endo / exo / processive / unknown)
```

The attribute vocabulary comes from the family–substrate table, CAZy family activities, and dbCAN-sub. Each function label becomes a point in this space; a small encoder maps attribute vectors to embeddings.

Training: supervised contrastive alignment between domain embeddings and function embeddings, with weighting by `substrate_label_level` (protein-level labels weighted highest; family-inherited labels downweighted).

Inference: nearest function prototypes with calibrated distance. Attribute-wise decoding means partial answers are possible — "β-1,4 glucan-active, retaining, endo, EC 3.2.1.–" is a useful output for a protein with no family.

Why this is the differentiating design: a softmax over families cannot emit anything for a family it never saw. A function space can, because the attributes are shared across families. The `mode` attribute also connects directly to the dbCAN-Cat effort.

## 7.3 Training regimes

Stage 1 — frozen embeddings + lightweight heads (logistic regression, MLP, prototype, kNN). Establishes whether signal exists before spending on fine-tuning.
Stage 2 — LoRA/PEFT on the encoders, multi-task (H1 + H2 + H3) with configurable loss weights.
Stage 3 — full fine-tuning only if Stage 2 shows headroom and compute allows.

Losses: weighted cross-entropy, focal, class-balanced, hierarchical (class→family consistency), supervised contrastive for H3. All configurable in YAML.

---

# 8. Structure pipeline

## 8.1 Sourcing (do not fold everything)

1. experimental PDB where available;
2. **CAZyme3D structures directly** — the lab already holds ~870k CAZyme structures with intra- and inter-family structural-cluster analyses; reuse rather than recompute;
3. AFDB match at ≥90% identity and ≥80% coverage;
4. prediction only for the remainder, and only for: the benchmark test sets, fam-0 candidates, remote homologs, and the discovery shortlist.

ESMFold for throughput; ColabFold/AF2 for the small high-value sets. Record which was used per structure.

## 8.2 Quality handling

* record pLDDT per residue and mean pLDDT per domain;
* stratify every structure-dependent result by pLDDT;
* mask or downweight 3Di tokens in low-confidence regions — fungal linkers and Ser/Thr-rich O-glycosylated regions are predicted poorly and will otherwise inject noise;
* report the fraction of the fungal set for which usable structure exists. If it is low, that caps Claim 1's practical value and must be stated.

## 8.3 Structural clusters as an intermediate label

CAZyme3D already defines structural clusters (SCs) within families. Consider SC as an auxiliary target between clan and family — it is in-house, fold-based, and finer than clan.

---

# 9. Baselines and experiment matrix

## 9.1 Baselines (all mandatory; version-matched per §6.3)

| ID | Baseline | Serves |
|----|----------|--------|
| B0 | run_dbCAN V5 (HMM + DIAMOND + dbCAN-sub) | primary comparator, T1/T2/T3 |
| B1 | DIAMOND / MMseqs2 top-hit transfer vs CAZy | homology floor |
| B2 | **Foldseek vs CAZyme3D, nearest-structure label transfer** | the honest structure baseline |
| B3 | CAZyLingua | published PLM competitor |
| B4 | CAALM | published PLM competitor |
| B5 | dbCAN-sub | substrate comparator for T3 |
| B6 | **family→substrate lookup** (dbCAN family → table) | the honest function-decoder baseline |
| B7 | amino-acid composition / k-mer + gradient boosting | sanity floor |

B2 and B6 are the two baselines that decide whether Claims 1 and 2 survive. If Foldseek retrieval alone matches SaProt fusion, the conclusion is "use retrieval, not learned structural representation" — a clean, publishable result that saves substantial compute. Plan for that outcome rather than against it.

## 9.2 Experiment matrix

| ID | Encoder | Structure | Head | Purpose |
|----|---------|-----------|------|---------|
| M1 | ESM-C frozen | – | linear/MLP | signal check |
| M2 | ESM-C LoRA | – | H1+H2 | sequence-only ceiling |
| M3 | SaProt frozen | ✔ | linear/MLP | structure PLM alone |
| M4 | SaProt LoRA | ✔ | H1+H2 | |
| M5 | ESM-C ⊕ SaProt gated fusion | ✔ | H1+H2(+clan) | **Claim 1** |
| M6 | M5 + function decoder | ✔ | H1+H2+H3 | **Claim 2** |
| M7 | M6 + fungal DAPT | ✔ | all | optional, gated (§13) |

Splits applied to each: cluster30, order-holdout, temporal, family-holdout (within-clan and whole-clan).
Represent every experiment in YAML. Never hard-code model settings.

---

# 10. Open-set and fam-0

## 10.1 The problem with v1's plan

CAZy's fam-0 groups are proteins the curators have seen and deliberately not assigned. GH0 alone holds on the order of 126,000 entries but only **14 characterized** proteins and 29 structures. With no ground truth, any fam-0 analysis is descriptive and unfalsifiable.

## 10.2 Retrospective fam-0 resolution (NEW — the fix)

Some fam-0 entries are later assigned to families, new or existing, as CAZy grows.

1. Take fam-0 entries from CAZy release *N*.
2. Look up their status in release *N+k*.
3. Label: still unassigned / assigned to an existing family / assigned to a newly created family.
4. Score the model using only release-*N* information, and evaluate against the later assignment.

Metrics: precision@k for the correct later family; AUROC for "will be assigned versus stays unassigned"; for entries that became new families, whether the model placed them in the correct clan (this is where Claim 1 pays off) and whether it clustered them together before the family existed.

This turns Task E into a measurable benchmark and maps onto the real use case — triage for curators. It is complementary to CAZy rather than competitive with it, which matters given the positioning considerations around the Henrissat group.

## 10.3 Novelty scoring

Retain the v1 list — confidence, embedding distance, nearest known family, energy, entropy, Mahalanobis, prototype distance, conformal prediction, OOD detection, clustering consistency, structural similarity — but select on the retrospective benchmark rather than reporting all of them. Add: **function-space distance** from H3, which is the only score that says *what the protein might do* rather than just *how unusual it is*.

## 10.4 Candidate discovery

Apply the selected model to MycoCosm proteins not confidently annotated by dbCAN. Rank by agreement across independent signals: model confidence, low training-set similarity, plausible domain architecture, structural similarity to known CAZymes, secretion signal, expression support, genomic clustering with transporters/TFs, taxonomic distribution.

Never present model-only predictions as validated CAZymes. Deliver a ranked, evidence-annotated shortlist suitable for experimental follow-up.

---

# 11. Evaluation

## 11.1 T1 — residue and domain level

Per-residue macro-F1; domain precision/recall at IoU 0.5 and 0.75; boundary offset distribution; protein-level binary metrics (precision, recall, specificity, F1, MCC, balanced accuracy, AUROC, AUPRC, calibration error) reported as *diagnostics* with the §5.2 caveat attached.

## 11.2 T2 — family and clan

Macro/micro/weighted F1, balanced accuracy, top-1/3/5, per-family precision and recall, hierarchical consistency (class→clan→family), confusion matrices at family and clan level.

**Claim-1 test:** report the fusion-versus-sequence-only delta separately for (a) clan assignment, (b) family assignment within clan, (c) identity <30%, (d) rare families, (e) fam-0. The hypothesis predicts large deltas for (a), (c), (d), (e) and near-zero for (b). Report it whichever way it comes out.

## 11.3 T3 — function decoding

Substrate accuracy and macro-F1; EC accuracy at each hierarchy level; mechanism/mode accuracy; and, for zero-shot, all of the above on held-out families, always alongside B5 and B6.

## 11.4 Cost (NEW — mandatory)

For every model and baseline:

```text
seconds per 1,000 proteins (GPU)
seconds per 1,000 proteins (CPU, or "not feasible")
peak GPU memory
peak RAM
structure-prediction time if required
model size on disk
```

HMMER annotates a fungal proteome in minutes on a laptop. Any accuracy claim must be read against this table, and the sequence-only degradation path (§7.1) must have its own row.

## 11.5 Statistics

Bootstrap confidence intervals; paired tests on identical test proteins; no claims from small metric differences.

**Vary the split, not just the seed.** Run 3–5 independent cluster partitions rather than 3 seeds on one partition — partition variance dominates initialization variance in this setting. Report seed variance additionally where cheap.

---

# 12. Blocking legal and licensing decisions

Resolve in Phase 0. Record in `docs/decisions.md`. Do not start dependent work first.

## 12.1 Encoder licence

* ESM-C 300M and the ESM code are under the permissive Cambrian Open License.
* **ESM-C 600M weights are under the Cambrian Non-Commercial License.** 6B is API-only.
* "Derivative Work" explicitly includes models created by fine-tuning or continued training. Derivatives inherit the licence terms and require "Built with ESM" attribution.
* ESM-2 650M is MIT.

Consequence: if the model is to ship inside run_dbCAN — which has commercial users — then DAPT or fine-tuning on ESM-C 600M pulls the whole tool under non-commercial terms. Choose deliberately between ESM-C 300M, ESM-2 650M, and accepting a non-commercial release. This is an architecture decision, not an implementation detail.

Check SaProt's licence and its base-model licence on the same basis before Stage 3.

## 12.2 MycoCosm data-use policy

JGI restricts use of MycoCosm genome data to genomes with an associated published reference, or with explicit PI permission. Consequences:

* the DAPT corpus must be restricted to published genomes unless permission is obtained;
* `genome_published_ref` is a required column in `proteins.parquet`;
* the dataset card must record, per genome, the reference or permission basis;
* released weights trained on unpublished genomes are a real risk. Do not defer this to Phase 9.

## 12.3 Release plan

Decide now what ships: a Python package, HuggingFace weights, a run_dbCAN V5 module, or all three. Design backwards from that — it determines model size, inference cost, CPU fallback, and licence.

---

# 13. Fungal DAPT — optional, gated

Demoted from core hypothesis to conditional extension.

Reasons: highest compute cost; weakest supporting evidence; CAZyme families are conserved across kingdoms, so pulling representations toward fungi may discard informative cross-kingdom homology signal; MycoCosm gene models are automated and contain fragmented and fused predictions plus heavy inter-genome redundancy, so an unfiltered corpus teaches annotation artifacts; and §12 constrains both the corpus and the resulting weights.

If attempted:

* deduplicate aggressively (MMseqs2 at ≤50% identity) and filter obviously broken gene models;
* mix in non-fungal proteins to limit forgetting; prefer adapter-based DAPT and low learning rates;
* report the full v1 training-statistics list (tokens, truncation, masking, batch, optimizer, schedule, steps, checkpoints, validation loss, hardware, runtime, memory, seed);
* run a smoke → pilot → full ladder.

**Pre-registered kill criterion**, written into `project.md` before the pilot runs:

> If pilot DAPT does not improve macro-F1 on the low-identity (<30%) stratum of the cluster-split benchmark by at least X points, with non-overlapping bootstrap confidence intervals against generic ESM-C, the DAPT branch is abandoned and the compute is redirected to structure and function-decoder work.

Fix X in Phase 0 from the §2.2 probe. A criterion chosen after seeing results is not a criterion.

---

# 14. Repository, environments, code, documentation

## 14.1 Repository structure

```text
/array1/xinpeng/fungi-cazyme-PLM/
├── project.md
├── README.md
├── CHANGELOG.md
├── LICENSE
├── pyproject.toml
├── Makefile
├── configs/
│   ├── data_paths.yaml
│   ├── dataset.yaml
│   ├── splits.yaml
│   ├── function_space.yaml        # NEW: attribute vocabulary + label mapping
│   ├── models/
│   ├── training/
│   └── experiments/
├── envs/
│   ├── base.yaml
│   ├── embeddings.yaml
│   ├── training.yaml
│   ├── saprot.yaml
│   └── structure.yaml
├── docs/
│   ├── 00_phase0_decision_memo.md   # NEW
│   ├── 01_data_inventory.md
│   ├── 02_data_quality_control.md
│   ├── 03_dataset_design.md
│   ├── 04_leakage_and_splits.md
│   ├── 05_baselines.md
│   ├── 06_embedding_models.md
│   ├── 07_structure_pipeline.md
│   ├── 08_fusion_models.md
│   ├── 09_function_decoder.md       # NEW
│   ├── 10_open_set_fam0.md
│   ├── 11_evaluation.md
│   ├── 12_reproducibility.md
│   ├── 13_results_and_decisions.md
│   ├── decisions.md                 # NEW: licence, data policy, architecture
│   └── limitations.md               # NEW: the three circularities, maintained live
├── data/
│   ├── raw/
│   ├── external/
│   ├── interim/
│   ├── processed/
│   ├── structures/
│   └── splits/
├── src/
│   ├── data/
│   ├── models/
│   ├── structure/
│   ├── functionspace/
│   └── utils/
├── scripts/
│   ├── audit/
│   ├── prepare_data/
│   ├── make_splits/
│   ├── extract_embeddings/
│   ├── structure/
│   ├── train/
│   ├── evaluate/
│   └── report/
├── workflows/
├── notebooks/
├── tests/
├── models/
├── embeddings/
├── results/
│   ├── tables/
│   ├── figures/
│   ├── predictions/
│   ├── metrics/
│   └── reports/
└── logs/
```

Do not duplicate large raw files. Prefer configuration references or documented symlinks.

## 14.2 Environments

Conda, separated by dependency weight: `base` (Polars/Pandas, PyArrow, Biopython, scikit-learn, plotting, YAML, testing, linting); `embeddings` (PyTorch, ESM-C/ESM-2, Transformers); `training` (PyTorch, Lightning/Accelerate, PEFT/LoRA, tracking, evaluation); `saprot`; `structure` (Foldseek, structure parsing, ESMFold/ColabFold interfaces).

Pin versions. Include creation and activation commands. Before choosing CUDA/PyTorch versions, inspect available GPUs, driver, CUDA compatibility, compilers, disk, RAM, and scheduler. Never assume a GPU type.

## 14.3 Code requirements

Unchanged from v1 and still correct: CLI arguments and `--help`; config files; input validation; informative errors; recorded seeds; logs; no hard-coded absolute paths beyond the project root; restartability; no silent overwrites; metadata beside outputs; docstrings and type hints; basic tests; chunked FASTA processing.

Provenance on every model and embedding artifact: source dataset, sequence hash, model name and version, checkpoint, layer, pooling, date, environment, config file, git commit. For structure-derived artifacts add: structure source, predictor and version, mean pLDDT.

## 14.4 Documentation policy

`project.md` is the source of truth: objective, hypotheses (§1.2, stated as falsifiable predictions), data inventory, dataset roles, modelling strategy, experiment matrix, completed/current tasks, unresolved questions, decisions with rationale, risks, next actions, links, dated changelog.

Step status vocabulary: `planned / implemented / smoke-tested / validated / completed / blocked`. Writing code does not make a step complete.

`docs/limitations.md` is maintained continuously, not written at submission time. It starts with the three circularities in §5 and the contamination issue in §6.5.

---

# 15. Phase plan

| Phase | Deliverable | Gate |
|-------|-------------|------|
| **0** | Error spectrum, ceiling probe, label audit, structure audit, licence/data memo | **Go/no-go for the whole framing** |
| 1 | Repo scaffolding, data inventory, canonical protein + domain tables, boundary-label decision | Boundary source resolved |
| 2 | Splits (cluster, taxonomic, temporal, family-holdout) + leakage report + contamination strata | Leakage report clean |
| 3 | Baselines B0–B7, version-matched, on all splits | Baseline table frozen |
| 4 | M1–M2 sequence-only, frozen then LoRA | Sequence ceiling known |
| 5 | Structure pipeline + B2 + M3–M4 | Structure coverage and quality known |
| 6 | M5 fusion + clan-hypothesis test | **Claim 1 resolved** |
| 7 | Function space + M6 + zero-shot family holdout + B6 comparison | **Claim 2 resolved** |
| 8 | Retrospective fam-0 benchmark + fungal discovery shortlist | Claim 3 supporting evidence |
| 9 | Optional DAPT (kill criterion), packaging, model/dataset cards, release | Ship decision |

Phases 6 and 7 are the paper. Phases 0–5 exist to make them credible. If Phase 0 or the Phase 3 baseline table shows no headroom, stop and re-scope rather than proceeding.

---

# 16. Immediate actions

1. Inspect `/array1/xinpeng/fungi-cazyme-PLM` recursively. Non-destructive inventory only.
2. Identify actual paths for MycoCosm proteomes, dbCAN annotations, `cazy-fungi-annotation`, the family–substrate table, taxonomy metadata, CAZyme3D structures, existing splits, scripts, and environments. Do not infer meaning from filenames; record anything unresolved as unresolved.
3. Create repository scaffolding without moving raw data.
4. Create the first version of `project.md`, `README.md`, `CHANGELOG.md`, `docs/00_phase0_decision_memo.md`, `docs/01_data_inventory.md`, `docs/decisions.md`, `docs/limitations.md`, environment YAMLs, and config templates.
5. Implement the inventory script; smoke-test it.
6. **Run Phase 0 §2.1 (error spectrum) and §2.2 (ceiling probe).** These are the point of the first fortnight.
7. **Audit the family–substrate table (§2.3) and count protein-level function labels.** Claim 2 lives or dies here.
8. Resolve §12 licence and data-policy questions; write the decision memo.
9. Present findings, blocking problems, and a recommended next experiment. Update `project.md`.

Do not launch full embedding extraction, structure prediction at scale, DAPT, or fine-tuning during this phase.

---

# 17. Decision principles

* A strong benchmark beats a large leaky one.
* Experimental labels beat computational predictions; never merge the two silently.
* Quantify the gap before building the model that closes it.
* Every baseline must be version-matched to the training cutoff.
* Report where the method should fail, and check whether it does.
* The honest baseline (B2 for structure, B6 for function) goes next to every headline number.
* fam-0 proteins are open-set candidates, never negatives.
* Demonstrate value before scaling — for DAPT and for structure prediction alike.
* Cost is a result, not a footnote.
* Preserve full provenance; keep `project.md` and `docs/limitations.md` synchronized with reality.
* Prefer a smaller defensible claim over a larger unfalsifiable one.

## Closing deliverables

1. Concise audit summary.
2. Directory and file tree created.
3. Exact commands executed.
4. Files created or modified.
5. Problems detected, including unresolved data questions.
6. Recommended next experiment.
7. Updated `project.md`.