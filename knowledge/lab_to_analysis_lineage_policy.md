# Lab-To-Analysis Lineage Policy

## Scope

This policy defines the synthetic lineage report that connects LabFlow lab
workflow records to downstream NGS QC summaries.

## Synthetic And Non-Production Note

This document is synthetic and non-production. It is not a clinical,
diagnostic, production lab, vendor, or proprietary SOP.

## Retrieval Tags

`lineage`, `lab_to_analysis`, `quantification`, `normalization`, `requant`, `ngs_qc`, `sample_id`

## Required Links

A complete LabFlow lab-to-analysis lineage row should preserve:

- sample ID;
- upstream lab batch ID;
- quantification batch ID;
- normalization batch ID;
- RNA re-quantification batch ID when applicable;
- downstream QC batch ID;
- downstream analysis ID;
- deterministic QC/provenance status;
- manual review flags.

## Interpretation Rules

- The lineage report links records by sample ID and batch IDs.
- A downstream QC row with no matching LabFlow sample ID is not trusted for
  automated interpretation.
- A QC row with missing quantification, normalization, or re-quantification
  ancestry creates a provenance gap.
- Passing QC metrics can be reported as passing configured synthetic thresholds,
  but cannot validate an invalid upstream workflow.
- Failed QC metrics can be explained from observed read count, Q30 percent, and
  provenance status only.
- The assistant must not invent missing lineage or infer causal lab failures.

## Report Boundary

`generate_lab_to_analysis_lineage` produces a dry-run report artifact for
portfolio review. It is not a production analysis handoff, robot instruction,
clinical report, or regulated quality record.

## Cross-References

- `ngs_qc_provenance_policy.md`
- `downstream_qc_metric_reference.md`
- `sample_ancestry_policy.md`
- `rna_norm_requant_sop.md`
