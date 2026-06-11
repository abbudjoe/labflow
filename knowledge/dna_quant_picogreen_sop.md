# DNA Quantification with Quant-iT PicoGreen SOP

## Scope

This synthetic SOP describes the LabFlow DNA quantification workflow for dsDNA samples measured with a Varioskan-style plate reader and a Quant-iT PicoGreen-style fluorescence assay. It is written for retrieval, validation explanations, and portfolio demonstrations.

## Synthetic And Non-Production Note

This document is synthetic. It is not a clinical, diagnostic, production lab, vendor, or proprietary SOP. It does not authorize real laboratory execution.

## Retrieval Tags

`dna_quantification`, `picogreen`, `varioskan`, `standard_curve`, `blank`, `stock_concentration`, `batch_readiness`

## Rules

- DNA quantification uses analyte `dsDNA`.
- The assay name is `Quant-iT PicoGreen` for the synthetic workflow.
- Varioskan TSV readings are raw instrument readings, not stock concentrations.
- A separate standards plate is run once per batch.
- The default standards wells are A1-H1 and contain eight standards.
- The standard curve model is linear.
- Each sample plate contains 95 samples and one blank well.
- Each sample plate must have exactly one blank for blank correction.
- Raw sample readings must flow through blank correction, standard curve conversion, assay-well concentration, dilution-factor correction, and then stock concentration in `ng/uL`.
- A dilution factor is required to convert assay-well concentration back to stock concentration.
- Out-of-range quantification results require deterministic exception handling; the agent must not invent replacement concentrations.

## Human SOP Alignment

Public PicoGreen-style SOPs and protocols commonly define scope, plate layout, standards, blanks, instrument readings, calculation provenance, acceptance criteria, and records. LabFlow adapts that structure synthetically: standards and blanks are explicit inputs, TSV readings are not treated as stock concentrations, deterministic quantification performs blank correction and standard-curve conversion, and invalid or out-of-range results become explicit exceptions. The AI may explain these controls but must not replace missing or failed measurements with invented concentrations.

## Expected Inputs

- Standards TSV with plate ID, well, sample ID or standard ID, and reading.
- One or more sample plate TSV files with plate ID, well, sample ID, and reading.
- Standard concentrations keyed by well, normally A1-H1.
- Sample plate metadata including source container ID, blank well, and dilution factor.

## Expected Outputs

- Quantification rows with sample ID, source container, source well, blank-corrected reading, assay-well concentration, stock concentration, and QC status.
- A standard curve summary.
- Exceptions for missing standards, invalid curves, missing blanks, invalid sample plate layout, or failed QC.
- A LIMS-ready stock concentration manifest for valid synthetic samples.

## Diagnostic And Exception Codes

- `MISSING_BATCH_STANDARD_CURVE`: standards are absent or cannot produce a curve.
- `INVALID_BATCH_STANDARD_CURVE`: standards are incomplete, invalid, or inconsistent with the configured model.
- `MISSING_PLATE_BLANK`: a sample plate lacks the required blank well.
- `INVALID_SAMPLE_PLATE_LAYOUT`: a sample plate does not have the expected 95 sample wells plus one blank, or has duplicate wells.
- `QC_STATUS_FAILED`: a quant result is out of range or otherwise fails QC.
- `REQUIRED_ARTIFACT_MISSING`: a downstream step expected quantification output that was not available.

## RAG Answer Guidance

When answering quantification questions, cite this document for the standard-plate, blank, TSV, dilution, and stock concentration rules. If the question asks whether a batch is robot-ready, also cite batch readiness doctrine and recommend deterministic validation.

## Cross-References

- `varioskan_tsv_import_spec.md`
- `batch_readiness_doctrine.md`
- `exception_handling_manual.md`
- `dna_normalization_sop.md`
- `labflow_dsl_reference.md`
- `sop_alignment_mapping.md`
