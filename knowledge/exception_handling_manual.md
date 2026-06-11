# Exception Handling Manual

## Scope

This manual defines LabFlow exception handling language for synthetic quantification, normalization, re-quantification, readiness, and JANUS-style artifact workflows. It is intended for RAG grounding and eval assertions.

## Synthetic And Non-Production Note

This document is synthetic and non-production. It is not a clinical, diagnostic, production lab, vendor, or proprietary SOP.

## Retrieval Tags

`exceptions`, `diagnostics`, `manual_review`, `blocking`, `robot_transfer`, `split_workflow`, `guardrails`

## Exception Rules

- Exceptions are first-class deterministic outputs.
- Blocking exceptions prevent robot-ready artifact generation.
- Invalid samples generate no robot transfer rows.
- The agent must report exception codes rather than rewriting them into vague prose.
- The agent must not invent missing values to resolve an exception.
- Manual review is allowed only when explicitly represented in status, exceptions, or audit records.
- Resolved or excluded samples must preserve ancestry and audit history.

## Diagnostic And Exception Codes

### Identity And Location

- `MISSING_SAMPLE_ID`: sample ID is absent.
- `DUPLICATE_SAMPLE_ID`: sample ID is reused in the same batch.
- `MISSING_SOURCE_LOCATION`: source container or source well is absent.
- `INVALID_SOURCE_LOCATION`: source well is outside A1-H12 or container is invalid.
- `DUPLICATE_SOURCE_LOCATION`: two samples claim the same source location.
- `MISSING_DESTINATION_LOCATION`: destination is required but absent.
- `INVALID_DESTINATION_LOCATION`: destination well is outside A1-H12 or container is invalid.
- `DUPLICATE_DESTINATION_LOCATION`: two samples target the same destination location.
- `DESTINATION_SUPPLIED_FOR_IN_PLACE`: in-place mode received a destination.

### Concentration And Volume

- `MISSING_AVAILABLE_VOLUME`: available source volume is absent.
- `INVALID_AVAILABLE_VOLUME`: available source volume is non-positive or malformed.
- `MISSING_CONCENTRATION`: stock concentration is absent.
- `INVALID_CONCENTRATION`: stock concentration is non-positive or malformed.
- `UNSUPPORTED_CONCENTRATION_UNIT`: concentration unit is outside the canonical `ng/uL` model.
- `SOURCE_CONCENTRATION_BELOW_TARGET`: source concentration cannot reach the requested target.
- `INSUFFICIENT_SOURCE_VOLUME`: source volume cannot cover transfer, 2 uL residual, and 1 uL aspiration margin.
- `SAMPLE_TRANSFER_BELOW_MINIMUM`: standard transfer would be below 1 uL.
- `SAMPLE_TRANSFER_ABOVE_MAXIMUM`: transfer exceeds configured maximum.
- `DILUENT_VOLUME_NEGATIVE`: transfer math would require negative diluent.
- `DESTINATION_VOLUME_EXCEEDED`: destination exceeds the 999 uL Matrix working volume.

### Quantification

- `MISSING_PLATE_BLANK`: a sample plate lacks the required blank well.
- `INVALID_SAMPLE_PLATE_LAYOUT`: expected 95 samples plus one blank was not satisfied.
- `MISSING_BATCH_STANDARD_CURVE`: no valid batch standard curve is available.
- `INVALID_BATCH_STANDARD_CURVE`: standard curve inputs are invalid or incomplete.
- `QC_STATUS_FAILED`: quantification or re-quantification failed QC.

### Split, In-Place, And RNA Re-Quant

- `SPLIT_REQUIRED_HIGH_CONCENTRATION`: high concentration requires split workflow instead of sub-1 uL standard transfer.
- `SPLIT_REQUANT_REQUIRED`: split child sample requires re-quant before follow-up normalization.
- `IN_PLACE_NORMALIZATION_SELECTED`: in-place mode was selected and must be represented explicitly.
- `IN_PLACE_NORMALIZATION_INVALID`: in-place setup violates the mode contract.
- `MISSING_REQUANT_RESULT`: expected RNA re-quant result is absent.
- `INVALID_REQUANT_RESULT`: RNA re-quant result is malformed, non-positive, or unmatched.
- `REQUANT_OUT_OF_ASSAY_RANGE`: re-quant result is outside configured assay range.
- `DOWNSTREAM_VOLUME_CONSTRAINT_FAILED`: downstream concentration cannot satisfy volume constraints.

### Artifact And Readiness

- `REQUIRED_ARTIFACT_MISSING`: a required manifest, standard curve, plan, or worklist input is absent.
- `JANUS_BLOCKED_FOR_INVALID_BATCH`: JANUS-style artifact generation was requested for an invalid batch.
- `COMMIT_MODE_NOT_AVAILABLE`: commit-mode artifact generation is blocked until durable dry-run and approval controls exist.

## Handling Guidance

- For concentration exceptions, recommend deterministic quantification or manual exclusion; do not infer a concentration.
- For blank or standard exceptions, recommend fixing the TSV/configuration and re-running quantification.
- For split exceptions, explain the child sample and re-quant requirement.
- For RNA re-quant exceptions, recommend repeat RiboGreen-style re-quant or manual review.
- For JANUS exceptions, explain that invalid or unapproved batches cannot produce robot-ready artifacts.

## Cross-References

- `batch_readiness_doctrine.md`
- `dna_quant_picogreen_sop.md`
- `dna_normalization_sop.md`
- `rna_norm_requant_sop.md`
- `janus_csv_worklist_spec.md`
- `ai_guardrails_policy.md`
