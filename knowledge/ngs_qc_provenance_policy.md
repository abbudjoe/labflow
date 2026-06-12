# NGS QC Provenance Policy

## Scope

This policy defines how LabFlow links synthetic downstream NGS QC summary
metrics back to upstream quantification, normalization, and RNA re-quantification
records.

## Synthetic And Non-Production Note

This document is synthetic and non-production. It is not a clinical,
diagnostic, production lab, vendor, or proprietary SOP, and it does not define a
real sequencing quality system.

## Retrieval Tags

`ngs_qc`, `downstream_qc`, `provenance`, `sample_id`, `manual_review`, `no_causal_inference`

## Core Rules

- Downstream QC is a summary-metric review surface, not a FASTQ parser,
  aligner, variant caller, or differential expression workflow.
- QC rows must link to LabFlow sample IDs and batch IDs before they can be used
  in lineage summaries.
- Passing downstream QC does not retroactively validate an invalid upstream lab
  batch.
- Failing downstream QC requires review, but it does not prove a lab root cause
  by itself.
- The AI may explain observed QC metrics and provenance gaps, but it must not
  infer that quantification, normalization, re-quantification, or robot handling
  caused a downstream QC failure unless deterministic evidence explicitly says
  so.
- Unmatched QC sample IDs require manual review.
- Missing upstream ancestry requires manual review.

## Diagnostic And Exception Codes

- `UNMATCHED_QC_SAMPLE_ID`: downstream QC row does not match known LabFlow sample
  identity.
- `MISSING_QC_RESULT`: expected QC result is absent or missing a required metric.
- `QC_RESULT_FAILED`: downstream summary metrics failed configured synthetic
  thresholds.
- `QC_PROVENANCE_GAP`: QC data cannot be fully linked to upstream LabFlow
  lineage.
- `DOWNSTREAM_QC_REVIEW_REQUIRED`: QC or provenance evidence requires manual
  review.

## RAG Answer Guidance

Use this policy when answering whether downstream QC can validate a lab batch,
whether a QC failure proves a lab cause, or why unmatched QC sample IDs require
manual review. Cite lineage policy when discussing quantification,
normalization, or re-quantification links.

## Cross-References

- `downstream_qc_metric_reference.md`
- `lab_to_analysis_lineage_policy.md`
- `sample_ancestry_policy.md`
- `ai_guardrails_policy.md`
