# Changelog

## Unreleased

- Added the Chinese ESMC 2026 evidence and project-integration report plus a
  reproducible ReportLab PDF renderer and portable PDF output.
- Added an immutable model-artifact schema and pinned-config template covering
  model/license revisions, layers, pooling, long-sequence windows, structure,
  splits, hardware, and cost.
- Added the B8 ESMC 6B SAE retrieval baseline, current-release/legacy licence
  separation, sequence-first model roles, and targeted ESMFold2 policy.
- Documented and scripted reproducible execution on the met server, including
  clean-commit enforcement, GPU selection, environment capture, and immutable
  remote logs.
- Established an independent reproducible research repository.
- Added data-source inventory, manifests, append-only run logging, and schemas.
- Added read-only Aim2 import and Phase 0 gap, function-label, structure, and
  report commands.
- Recorded known legacy corrections and blocking data gaps.
- Validated a full 23-source SHA-256 inventory and deterministic fixture suite.
- Reproduced 1,198/1,198 MycoCosm policy matches, 875/826 HMM model counts,
  390/88 function-label counts, and CAZyme3D exact/90-80 coverage.
- Added explicit handling for a malformed Aim2 footer, versioned JGI aliases,
  accession-only CAZy headers, exact mapping duplicates, and deterministic gzip.
- Hard-failed and logged 36 different-sequence canonical alias conflicts; the
  Phase 0 decision remains blocked and model training has not started.
