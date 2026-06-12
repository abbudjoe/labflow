# Downstream QC Metric Reference

## Scope

This reference describes the small synthetic QC summary metrics used by LabFlow
Stage 19.

## Synthetic And Non-Production Note

This document is synthetic and non-production. It is not clinical,
diagnostic, production, or vendor guidance.

## Retrieval Tags

`ngs_qc`, `qc_metrics`, `read_count`, `q30`, `thresholds`, `manual_review`

## Supported Summary Metrics

LabFlow Stage 19 supports only CSV summary metrics:

- `read_count`: integer count of synthetic reads assigned to a sample summary.
- `q30_percent`: percentage of bases at or above Q30 in the synthetic summary.

The default thresholds are:

- minimum read count: `1000000`;
- minimum Q30 percent: `80.0`.

These thresholds are portfolio fixtures. They are not clinical, production, or
vendor acceptance criteria.

## Evaluation Rules

- Missing `read_count` or `q30_percent` creates `MISSING_QC_RESULT`.
- A read count below the configured minimum creates `QC_RESULT_FAILED`.
- A Q30 percentage below the configured minimum creates `QC_RESULT_FAILED`.
- Any failed or missing metric creates `DOWNSTREAM_QC_REVIEW_REQUIRED`.
- Threshold failures are downstream observations. They do not identify a lab
  process root cause.

## Out Of Scope

- FASTQ parsing.
- Alignment.
- Variant calling.
- Differential expression.
- Clinical QC logic.
- Instrument or run-level root-cause diagnosis.

## RAG Answer Guidance

Use this reference when explaining which QC metric failed. Pair it with
`ngs_qc_provenance_policy.md` before making any statement about what can or
cannot be inferred from a downstream QC failure.
