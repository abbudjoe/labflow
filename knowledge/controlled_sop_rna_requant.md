# LF-SOP-003 RNA Normalization Re-Quantification Review

## Document Control

- SOP ID: `LF-SOP-003`
- Title: RNA Normalization Re-Quantification Review
- Version: `0.1`
- Effective date: synthetic demo only
- Owner: LabFlow AI Studio
- Review cycle: portfolio review before demo release
- Status: synthetic controlled SOP template

## Source Pattern References

This LabFlow SOP is adapted from public human-directed RNA quantification and
fluorescence quantitation SOP patterns. It does not copy operational procedure
text.

- MD Anderson / CIMAC-CIDC RiboGreen microplate reader SOP record:
  `https://brd.nci.nih.gov/brd/sop/show/2706`
- Emory EIGC.004 Quantitation with Fluorescence:
  `https://www.cores.emory.edu/eigc/_includes/documents/sections/resources/eigc.004_-quantitation-with-fluorescence.pdf`
- Thermo Fisher RiboGreen RNA kit manual:
  `https://tools.thermofisher.com/content/sfs/manuals/mp11490.pdf`

## Synthetic And Non-Production Note

This document is not a clinical, diagnostic, production, vendor, or proprietary
SOP. It defines synthetic review controls for LabFlow RNA normalization and
re-quantification demos.

## Retrieval Tags

`controlled_sop`, `rna_requant`, `ribogreen`, `downstream_concentration`, `manual_review`, `trusted_concentration_source`

## Purpose

Define how LabFlow reviews synthetic RNA re-quantification results before using
them as downstream concentrations.

## Scope

Applies to synthetic total RNA normalization workflows where normalized samples
or intermediate dilution plates are re-quantified and reviewed before downstream
workflow decisions.

## Responsibilities

- Operator: provides re-quant result rows for expected normalized or child
  samples.
- Reviewer: resolves missing, invalid, out-of-range, or unmatched re-quant
  results.
- LabFlow deterministic engine: validates re-quant rows and updates downstream
  concentration only when results are trusted.
- AI assistant: may explain which trusted value should be used, but must not
  invent a missing numeric concentration.

## Safety And Training Boundary

Real labs require training, PPE, reagent handling, instrument setup, and RNA
integrity controls. LabFlow models only synthetic data review and deterministic
validation.

## Required Inputs

- RNA normalization workflow YAML.
- Expected normalized sample IDs or split child sample IDs.
- Re-quant CSV with `sample_id` and `requant_concentration_ng_per_ul`.
- Optional assay limits and downstream concentration thresholds.

## QC And Acceptance Criteria

- Re-quant result must match an expected normalized or child sample.
- Re-quant concentration must be present, positive, and numeric.
- Out-of-assay-range values require repeat quant or manual review.
- LabFlow does not assume a default percent tolerance between expected and
  observed concentration.
- The measured re-quant value becomes the downstream concentration.
- A policy question about which concentration source to use is supported: use
  the measured re-quant result.
- A concrete request for a missing numeric concentration is unsupported without
  trusted workflow data or deterministic tool output.

## Controlled Procedure Summary

1. Confirm the workflow identifies the expected normalized or child samples.
2. Load re-quant result rows from the trusted synthetic input file.
3. Match each result row to an expected sample.
4. Validate concentration format, positivity, and configured assay limits.
5. Promote valid measured re-quant values to downstream concentration.
6. Route missing, invalid, unmatched, or out-of-range values to repeat quant or
   manual review.
7. Record ancestry and review status.

## Nonconformance Handling

- `MISSING_REQUANT_RESULT`: expected sample has no re-quant value.
- `INVALID_REQUANT_RESULT`: result is malformed, non-positive, or unmatched.
- `REQUANT_OUT_OF_ASSAY_RANGE`: result is outside configured assay limits.
- `DOWNSTREAM_VOLUME_CONSTRAINT_FAILED`: downstream concentration cannot satisfy
  volume constraints.
- `SPLIT_REQUANT_REQUIRED`: split child requires re-quant before follow-up
  normalization.

The assistant must not repair these conditions by guessing a concentration.

## Records

- Re-quant result table.
- Downstream concentration manifest.
- Ancestry events.
- Exception report.
- Audit event for deterministic tool execution.

## LabFlow Enforcement Mapping

- `process_rna_requant`: validates result rows and promotes valid measured
  values to downstream concentration.
- `validate_batch`: blocks robot readiness when required re-quant data is
  missing or invalid.
- RAG evals: verify that concentration-source questions retrieve the RNA SOP and
  do not collapse into unsupported missing-value refusal.

## Cross-References

- `rna_norm_requant_sop.md`
- `sample_ancestry_policy.md`
- `batch_readiness_doctrine.md`
- `ai_guardrails_policy.md`
- `sop_alignment_mapping.md`
