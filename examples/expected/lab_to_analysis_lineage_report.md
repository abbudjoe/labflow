# Lab-To-Analysis Lineage Report

Synthetic downstream QC provenance summary. This is not a clinical, diagnostic, production, or root-cause report.

## Thresholds

- Minimum read count: `1000000`
- Minimum Q30 percent: `80.0`

## Summary

- Records: `8`
- Manual review required: `7`

## Lineage

| Sample | Quant Batch | Normalization Batch | Re-Quant Batch | QC Batch | QC Status | Provenance Status | Exceptions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RNA_DEMO_FAILED_VALID_UPSTREAM_001 | RNA_QUANT_001 | RNA_NORM_001 | RNA_REQUANT_001 | QC_BATCH_001 | FAIL | DOWNSTREAM_QC_REVIEW_REQUIRED | QC_RESULT_FAILED, DOWNSTREAM_QC_REVIEW_REQUIRED |
| RNA_DEMO_LOW_Q30_001 | RNA_QUANT_001 | RNA_NORM_001 | RNA_REQUANT_001 | QC_BATCH_001 | FAIL | DOWNSTREAM_QC_REVIEW_REQUIRED | QC_RESULT_FAILED, DOWNSTREAM_QC_REVIEW_REQUIRED |
| RNA_DEMO_LOW_READS_001 | RNA_QUANT_001 | RNA_NORM_001 | RNA_REQUANT_001 | QC_BATCH_001 | FAIL | DOWNSTREAM_QC_REVIEW_REQUIRED | QC_RESULT_FAILED, DOWNSTREAM_QC_REVIEW_REQUIRED |
| RNA_DEMO_MISSING_ANCESTRY_001 | RNA_QUANT_001 |  | RNA_REQUANT_001 | QC_BATCH_001 | PASS | QC_PROVENANCE_GAP | QC_PROVENANCE_GAP, DOWNSTREAM_QC_REVIEW_REQUIRED |
| RNA_DEMO_MISSING_QC_001 | RNA_QUANT_001 | RNA_NORM_001 | RNA_REQUANT_001 |  | MISSING | DOWNSTREAM_QC_REVIEW_REQUIRED | MISSING_QC_RESULT, DOWNSTREAM_QC_REVIEW_REQUIRED |
| RNA_DEMO_STD_001 | RNA_QUANT_001 | RNA_NORM_001 | RNA_REQUANT_001 | QC_BATCH_001 | PASS | LINKED |  |
| RNA_DEMO_UPSTREAM_INVALID_001 | RNA_QUANT_BAD_001 | RNA_NORM_BAD_001 | RNA_REQUANT_BAD_001 | QC_BATCH_001 | PASS | QC_PROVENANCE_GAP | QC_PROVENANCE_GAP, DOWNSTREAM_QC_REVIEW_REQUIRED |
| RNA_QC_UNKNOWN_001 |  |  |  | QC_BATCH_001 | PASS | UNMATCHED_QC_SAMPLE_ID | UNMATCHED_QC_SAMPLE_ID, DOWNSTREAM_QC_REVIEW_REQUIRED |

## Interpretation Boundary

- Failed downstream QC requires review, but does not identify a lab root cause by itself.
- Passing downstream QC does not retroactively validate an invalid or incomplete upstream lab batch.
- Unmatched sample IDs and provenance gaps require manual review.
