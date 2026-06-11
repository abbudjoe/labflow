# Varioskan TSV Import Specification

## Scope

This specification describes how LabFlow imports synthetic Varioskan-style TSV files for standards and sample plates before DNA or RNA quantification processing.

## Synthetic And Non-Production Note

This document is synthetic and non-production. It is not a clinical, diagnostic, production lab, vendor, or proprietary SOP.

## Retrieval Tags

`varioskan`, `tsv`, `schema_mapping`, `plate_reader`, `standards`, `blank`, `quantification`

## Required Concepts

- A TSV reading is an instrument reading, not a stock concentration.
- TSV parsing must be deterministic.
- Column names may vary, so LabFlow supports schema mapping rather than hard-coding one historical layout.
- Well coordinates must parse as A1-H12.
- Standards and sample plates are modeled as separate TSV inputs.
- The standards plate is run once per batch.
- Sample plates must include 95 samples plus one blank.

## Default Column Semantics

- `Plate ID`: plate identifier.
- `Well`: well coordinate.
- `Sample ID`: sample, standard, or blank identifier.
- `Reading`: numeric fluorescence reading.

## Schema Mapping Rules

- A schema mapping may rename plate ID, well, sample ID, or reading columns.
- Missing mapped columns block parsing.
- Invalid numeric readings block or flag the affected row according to deterministic parser behavior.
- The parser sorts readings deterministically by plate and well.

## Quantification Flow

- Standards TSV feeds standard curve fitting.
- Sample plate TSV feeds blank correction and concentration calculation.
- The quantification processor combines TSV readings with configured standard concentrations and dilution factors.
- Stock concentrations are reported in `ng/uL`.

## Diagnostic And Exception Codes

- `INVALID_BATCH_STANDARD_CURVE`: standards TSV cannot produce a valid linear curve.
- `MISSING_BATCH_STANDARD_CURVE`: standards TSV or curve artifact is absent.
- `MISSING_PLATE_BLANK`: sample plate TSV lacks the required blank.
- `INVALID_SAMPLE_PLATE_LAYOUT`: sample plate TSV does not match 95 samples plus one blank or contains duplicate wells.
- `QC_STATUS_FAILED`: parsed/processed result fails deterministic QC.
- `REQUIRED_ARTIFACT_MISSING`: a required TSV or parsed artifact is absent.

## RAG Answer Guidance

Use this document for TSV column, schema mapping, standards/sample plate separation, and parser behavior questions. Cite the DNA quantification SOP for concentration-calculation flow.

## Cross-References

- `dna_quant_picogreen_sop.md`
- `exception_handling_manual.md`
- `batch_readiness_doctrine.md`
- `labflow_dsl_reference.md`
