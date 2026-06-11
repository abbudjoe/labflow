# LF-SOP-001 DNA Quantification by Fluorescence

## Document Control

- SOP ID: `LF-SOP-001`
- Title: DNA Quantification by Fluorescence
- Version: `0.1`
- Effective date: synthetic demo only
- Owner: LabFlow AI Studio
- Review cycle: portfolio review before demo release
- Status: synthetic controlled SOP template

## Source Pattern References

This LabFlow SOP is adapted from public human-directed SOP patterns, not copied
procedure text. Reference examples include NCI BRD PicoGreen SOP records and
Emory Integrated Genomics Core fluorescence quantitation SOP structure.

- NCI BRD SOP M017 PicoGreen DNA quantification:
  `https://brd.nci.nih.gov/brd/sop/download-pdf/1456`
- NCI BRD Quant-iT PicoGreen dsDNA quantification of Illumina sequencing libraries:
  `https://brd.nci.nih.gov/brd/sop/download-pdf/3236`
- Emory EIGC.004 Quantitation with Fluorescence:
  `https://www.cores.emory.edu/eigc/_includes/documents/sections/resources/eigc.004_-quantitation-with-fluorescence.pdf`

## Synthetic And Non-Production Note

This document is not a clinical, diagnostic, production, vendor, or proprietary
SOP. It does not authorize real laboratory execution. It provides a realistic
controlled-document shape for synthetic LabFlow validation and RAG demos.

## Retrieval Tags

`controlled_sop`, `dna_quantification`, `picogreen`, `standard_curve`, `blank`, `qc_acceptance`, `lims_record`

## Purpose

Define the synthetic controlled workflow for converting fluorescence plate-reader
data into LabFlow DNA stock concentration records.

## Scope

Applies to synthetic dsDNA quantification workflows in LabFlow where
Varioskan-style TSV readings, standards, sample plate metadata, and dilution
factors are used to produce stock concentration records in `ng/uL`.

## Responsibilities

- Operator: prepares complete synthetic input files and reviews deterministic
  exceptions.
- Reviewer: confirms standards, blanks, and QC status before downstream use.
- LabFlow deterministic engine: parses readings, applies calculation rules, and
  emits explicit exceptions.
- AI assistant: may explain the SOP and retrieved evidence, but must not invent
  concentrations or QC results.

## Safety And Training Boundary

Real labs require documented training, PPE, biohazard controls, reagent handling,
and equipment-specific procedures. LabFlow models only synthetic data validation;
it does not provide real safety or instrument instructions.

## Required Inputs

- Standards TSV with known standard identifiers and readings.
- Sample plate TSV with sample IDs, wells, and readings.
- Plate metadata identifying one blank well per sample plate.
- Dilution factor for each sample plate.
- Standard concentrations keyed to the configured standards wells.

## QC And Acceptance Criteria

- Standards must be present on a separate standards plate.
- Standards default to A1-H1 and contain eight standards.
- Each sample plate must contain 95 samples plus one blank.
- Each sample plate must have exactly one blank for blank correction.
- Standard curve model is linear.
- Raw readings are not stock concentrations.
- Valid concentration output requires blank correction, standard-curve
  conversion, assay concentration, dilution-factor correction, and stock
  concentration reporting.
- Out-of-range or failed QC values require deterministic exception handling.

## Controlled Procedure Summary

1. Confirm required TSV files and plate metadata are present.
2. Validate standards plate identity, standard wells, and curve model.
3. Validate sample plate layout, sample IDs, wells, and blank.
4. Parse plate-reader readings as raw fluorescence values.
5. Apply blank correction and standard-curve conversion deterministically.
6. Apply dilution-factor correction to produce stock concentration in `ng/uL`.
7. Emit LIMS-ready concentration records only for valid samples.
8. Emit explicit exceptions for missing controls, invalid curves, missing blanks,
   malformed sample data, or QC failures.

## Nonconformance Handling

- `MISSING_BATCH_STANDARD_CURVE`: standards are absent or unusable.
- `INVALID_BATCH_STANDARD_CURVE`: standards do not satisfy curve requirements.
- `MISSING_PLATE_BLANK`: sample plate lacks the required blank.
- `INVALID_SAMPLE_PLATE_LAYOUT`: sample plate layout is invalid.
- `QC_STATUS_FAILED`: quantification result failed deterministic QC.
- `REQUIRED_ARTIFACT_MISSING`: downstream workflow expected missing quant output.

The assistant must not resolve nonconformance by inventing readings, standards,
blanks, sample IDs, or concentrations.

## Records

- Parsed reading artifact.
- Standard curve summary.
- Stock concentration manifest.
- Exception report.
- Audit event for tool execution.

## LabFlow Enforcement Mapping

- `parse_varioskan_tsv`: parses TSV-like input.
- `process_quantification`: enforces standards, blanks, curve, dilution, QC, and
  concentration output rules.
- RAG evals: verify that quantification questions retrieve SOP, TSV, and
  readiness sources.

## Cross-References

- `dna_quant_picogreen_sop.md`
- `varioskan_tsv_import_spec.md`
- `batch_readiness_doctrine.md`
- `exception_handling_manual.md`
- `sop_alignment_mapping.md`
