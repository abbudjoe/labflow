# Batch Readiness Doctrine

## Scope

This doctrine defines when a synthetic LabFlow batch can be considered robot-ready for dry-run artifact generation. It applies to DNA quantification, DNA normalization, RNA normalization/re-quantification, and JANUS-style worklist previews.

## Synthetic And Non-Production Note

This document is synthetic and non-production. It is not a clinical, diagnostic, production lab, vendor, or proprietary SOP.

## Retrieval Tags

`batch_readiness`, `robot_ready`, `validation`, `exceptions`, `janus`, `dry_run`, `workflow_dsl`

## Robot-Ready Rule

A batch is robot-ready only when deterministic readiness gates pass. A RAG answer may explain readiness doctrine, but it must not assert that a concrete batch is valid without deterministic validation output.

## Required Gates

- Batch ID is present.
- Workflow type is supported.
- Molarity fields are absent.
- Sample IDs are present and unique.
- Source locations are present, valid A1-H12 coordinates, and not duplicated.
- Destination locations are present when standard new-container normalization is required.
- Destination locations are valid A1-H12 coordinates and not duplicated.
- Concentrations are present in `ng/uL` when required.
- Available source volumes are present in `uL`.
- Transfer volumes satisfy minimum transfer, residual dead volume, and aspiration safety rules.
- Destination volumes do not exceed the Matrix 96 x 1 mL 999 uL working volume.
- DNA quantification has a separate standards plate with A1-H1 standards.
- Each sample plate has 95 samples and exactly one blank.
- RNA re-quant results exist and are valid when downstream concentration is required.
- Exceptions are resolved, excluded, or routed to manual review according to policy.
- Invalid samples are excluded from robot transfer rows.
- JANUS-style artifact generation is a dry-run preview unless later approval and artifact-store rules explicitly permit commit.

## Human SOP Alignment

Human SOPs define when an operator may proceed, when review is required, and which records must exist. LabFlow adapts that pattern into deterministic readiness gates: a RAG answer may explain the gates, but concrete readiness requires `validate_batch` or another deterministic tool result. This mirrors controlled-lab documentation without claiming clinical or production readiness.

## Readiness Outcomes

- `robot_ready`: deterministic validation passes and dry-run robot artifacts may be previewed.
- `not_robot_ready`: one or more blocking exceptions exist.
- `manual_review`: a human decision or repeat quant is required before robot artifacts can be trusted.
- `unsupported`: request uses an out-of-scope feature such as molarity.

## Diagnostic And Exception Codes

Common readiness blockers include:

- `MISSING_SAMPLE_ID`
- `DUPLICATE_SAMPLE_ID`
- `MISSING_SOURCE_LOCATION`
- `INVALID_SOURCE_LOCATION`
- `DUPLICATE_SOURCE_LOCATION`
- `MISSING_DESTINATION_LOCATION`
- `DUPLICATE_DESTINATION_LOCATION`
- `MISSING_CONCENTRATION`
- `UNSUPPORTED_CONCENTRATION_UNIT`
- `INSUFFICIENT_SOURCE_VOLUME`
- `SAMPLE_TRANSFER_BELOW_MINIMUM`
- `DESTINATION_VOLUME_EXCEEDED`
- `MISSING_BATCH_STANDARD_CURVE`
- `MISSING_PLATE_BLANK`
- `MISSING_REQUANT_RESULT`
- `INVALID_REQUANT_RESULT`
- `REQUIRED_ARTIFACT_MISSING`

## Tool Guidance

- Use `validate_workflow` to check LabFlow YAML shape and domain diagnostics.
- Use `validate_batch` before claiming readiness for a concrete batch.
- Use `generate_normalization_plan` to inspect transfer math.
- Use `generate_janus_csv` with `dry_run=true` only after deterministic validation passes.

## RAG Answer Guidance

When asked why a batch is not robot-ready, cite this doctrine and the relevant exception manual section, then recommend deterministic validation. Do not invent missing concentrations, blank wells, standards, sample IDs, or worklist rows.

## Cross-References

- `exception_handling_manual.md`
- `ai_guardrails_policy.md`
- `janus_csv_worklist_spec.md`
- `dna_quant_picogreen_sop.md`
- `dna_normalization_sop.md`
- `rna_norm_requant_sop.md`
- `labflow_dsl_reference.md`
- `sop_alignment_mapping.md`
