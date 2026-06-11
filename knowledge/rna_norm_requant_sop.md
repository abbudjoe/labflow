# RNA Normalization and Re-Quantification SOP

## Scope

This synthetic SOP describes LabFlow total RNA normalization followed by re-quantification. It covers the downstream concentration rule, manual review conditions, and the optimized three-container batch pattern used in demos.

## Synthetic And Non-Production Note

This document is synthetic and portfolio-oriented. It is not a clinical, diagnostic, production lab, vendor, or proprietary SOP, and it does not describe real patient testing.

## Retrieval Tags

`rna_normalization`, `requant`, `ribogreen`, `downstream_concentration`, `manual_review`, `three_container_batching`, `ancestry`

## Rules

- RNA workflow analyte is `total_RNA`.
- Upstream post-extraction quant may be modeled as Qubit RNA or Nanodrop.
- Normalization and sample-prep re-quantification use a RiboGreen-style assay in the synthetic workflow.
- Re-quantification is performed on the normalized RNA or an intermediate RNA dilution plate.
- The measured re-quant value becomes the downstream concentration.
- Policy questions about which trusted concentration source downstream RNA steps should use are supported by this SOP: use the measured re-quant value.
- Concrete requests for a missing sample's numeric re-quant concentration are not supported unless the value is present in trusted workflow data or deterministic tool output.
- LabFlow does not assume a default percent tolerance between expected and observed concentration.
- Missing, invalid, non-positive, or out-of-assay-range re-quant results require manual review or repeat quant.
- A sample without an expected normalized child record must not be accepted as a valid re-quant result.
- Follow-up decisions must cite the deterministic re-quant result or the exception that blocks it.
- RNA optimized batching models three containers per batch to reduce robot idle time.

## Human SOP Alignment

Public quantification SOPs commonly distinguish expected inputs, measurement provenance, acceptance criteria, exceptions, review decisions, and records. LabFlow adapts that pattern synthetically: re-quant CSV rows are trusted inputs, the deterministic `process_rna_requant` tool validates them, valid measured re-quant results become downstream concentration, and missing or invalid values route to repeat quant or manual review. The AI may explain this policy with citations, but it must not invent numeric concentration values.

## Expected Inputs

- Normalization config using `RNA_NORMALIZATION_REQUANT`.
- Input sample manifest with source concentration in `ng/uL`, available volume in `uL`, and source/destination locations.
- Re-quant CSV with `sample_id` and `requant_concentration_ng_per_ul`.
- Optional assay min/max concentration policy and downstream concentration threshold.

## Expected Outputs

- Normalization plan rows.
- Re-quant result rows with downstream concentration.
- Downstream concentration manifest.
- Ancestry records linking source, normalized child, and re-quant result.
- Exceptions for missing, invalid, unmatched, out-of-range, or downstream-infeasible re-quant results.

## Diagnostic And Exception Codes

- `MISSING_REQUANT_RESULT`: expected sample has no re-quant value.
- `INVALID_REQUANT_RESULT`: re-quant value is malformed, non-positive, or unmatched to an expected sample.
- `REQUANT_OUT_OF_ASSAY_RANGE`: re-quant value is outside configured assay limits.
- `DOWNSTREAM_VOLUME_CONSTRAINT_FAILED`: downstream concentration cannot satisfy volume constraints.
- `SPLIT_REQUANT_REQUIRED`: a split child requires re-quant before follow-up normalization.
- `QC_STATUS_FAILED`: quant or re-quant QC failed.

## RAG Answer Guidance

Use this document when asked whether RNA re-quant uses percent tolerance, how downstream concentrations are chosen, or why a re-quant result requires manual review. For policy questions, say downstream steps use the measured re-quant value. For missing numeric values, say the answer is unsupported without trusted workflow data or deterministic tool output.

## Cross-References

- `dna_normalization_sop.md`
- `sample_ancestry_policy.md`
- `exception_handling_manual.md`
- `batch_readiness_doctrine.md`
- `throughput_optimization_case.md`
- `labflow_dsl_reference.md`
- `sop_alignment_mapping.md`
