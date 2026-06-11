# LF-SOP-004 Normalization And JANUS Dry-Run Worklist Review

## Document Control

- SOP ID: `LF-SOP-004`
- Title: Normalization And JANUS Dry-Run Worklist Review
- Version: `0.1`
- Effective date: synthetic demo only
- Owner: LabFlow AI Studio
- Review cycle: portfolio review before demo release
- Status: synthetic controlled SOP template

## Source Pattern References

This LabFlow SOP adapts public SOP control patterns for calculation review,
operator readiness, QC acceptance, records, and nonconformance handling. It does
not copy robot vendor procedures or create robot-ready instructions.

- Emory EIGC.004 Quantitation with Fluorescence:
  `https://www.cores.emory.edu/eigc/_includes/documents/sections/resources/eigc.004_-quantitation-with-fluorescence.pdf`
- NCI BRD PicoGreen SOP records:
  `https://brd.nci.nih.gov/brd/sop/download-pdf/1456`

## Synthetic And Non-Production Note

This document is not a clinical, diagnostic, production lab, vendor, or
proprietary SOP. JANUS-style worklists in LabFlow are synthetic dry-run previews
for portfolio demonstration only.

## Retrieval Tags

`controlled_sop`, `normalization`, `janus`, `dry_run`, `worklist_review`, `approval`, `audit`

## Purpose

Define controlled review of deterministic normalization plans and JANUS-style
dry-run previews.

## Scope

Applies to synthetic DNA normalization and RNA normalization/re-quantification
workflows that produce transfer plans or JANUS-style CSV previews.

## Responsibilities

- Operator: supplies complete source and destination sample metadata.
- Reviewer: confirms deterministic validation passed before previewing
  artifacts.
- LabFlow deterministic engine: calculates transfer volumes and blocks invalid
  rows.
- AI assistant: may explain blocked readiness and propose dry-run patches, but
  cannot approve commits or create robot-ready artifacts for invalid batches.

## Safety And Training Boundary

Real liquid handlers require site-specific training, maintenance, calibration,
labware validation, and vendor-approved methods. LabFlow does not provide real
robot instructions.

## Required Inputs

- Valid workflow YAML.
- Source concentration in `ng/uL`.
- Available source volume in `uL`.
- Destination state when standard new-container normalization is used.
- Target final concentration and volume, or target mass and volume.
- Approval token only for commit paths that have already passed dry-run policy.

## QC And Acceptance Criteria

- Molar targets are unsupported.
- Minimum transfer volume is 1 `uL`.
- Source residual dead volume is 2 `uL`.
- Robot aspiration safety margin is 1 `uL`.
- Matrix 96 x 1 mL working volume limit is 999 `uL`.
- Sub-1 `uL` standard transfers require split workflow, not rounding.
- Invalid samples generate no robot transfer rows.
- JANUS-style artifacts require deterministic validation.
- Dry-run is the safe default.
- Commit requires prior successful dry-run, matching approval token, and audit.

## Controlled Procedure Summary

1. Validate workflow YAML and batch readiness.
2. Compute transfer and diluent volumes deterministically.
3. Block rows with missing concentration, insufficient source volume, duplicate
   locations, destination overflow, unsupported units, or unresolved re-quant
   requirements.
4. Route high-concentration sub-1 `uL` transfers to split workflow.
5. Generate JANUS-style CSV preview only when deterministic validation supports
   it.
6. Record audit metadata for tool execution and artifact handling.

## Nonconformance Handling

- `MISSING_CONCENTRATION`
- `INSUFFICIENT_SOURCE_VOLUME`
- `SAMPLE_TRANSFER_BELOW_MINIMUM`
- `SPLIT_REQUIRED_HIGH_CONCENTRATION`
- `SPLIT_REQUANT_REQUIRED`
- `DUPLICATE_SOURCE_LOCATION`
- `DUPLICATE_DESTINATION_LOCATION`
- `DESTINATION_VOLUME_EXCEEDED`
- `JANUS_BLOCKED_FOR_INVALID_BATCH`
- `COMMIT_REQUIRES_DRY_RUN`
- `COMMIT_REQUIRES_APPROVAL`

The assistant must not bypass validation, round forbidden transfers, fabricate
worklist rows, or commit artifacts without approval.

## Records

- Validation report.
- Normalization plan.
- Dry-run JANUS preview when valid.
- Blocked artifact response when invalid.
- Approval/audit records for commit paths.

## LabFlow Enforcement Mapping

- `validate_batch`: readiness gate.
- `generate_normalization_plan`: deterministic transfer math.
- `generate_janus_csv`: dry-run preview and commit policy.
- Agent policy runtime: dry-run and approval enforcement.

## Cross-References

- `dna_normalization_sop.md`
- `janus_csv_worklist_spec.md`
- `batch_readiness_doctrine.md`
- `ai_guardrails_policy.md`
- `sop_alignment_mapping.md`
