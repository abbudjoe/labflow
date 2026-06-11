# LabFlow DSL Reference

## Scope

This reference describes the synthetic LabFlow workflow YAML format used by the VS Code extension, deterministic validators, RAG explanations, and demo scenarios.

## Synthetic And Non-Production Note

This document is synthetic and non-production. It is not a clinical, diagnostic, production lab, vendor, or proprietary SOP.

## Retrieval Tags

`dsl`, `yaml`, `workflow_validation`, `schema`, `diagnostics`, `molarity_excluded`, `vscode`

## Rules

- Workflow files must use supported workflow types.
- Domain validation must enforce lab-specific rules beyond YAML shape.
- Molarity fields are unsupported.
- Robot-ready artifacts require deterministic validation outside the DSL parser.

## File Conventions

Recommended file extensions:

- `.labflow.yaml`
- `.workflow.yaml`

## Top-Level Sections

- `workflow`: workflow name, version, and workflow type.
- `batch`: batch ID, containers per batch, plate format, sample count, and blank well.
- `standards`: standards plate ID, wells, and curve model.
- `containers`: source and destination container type references.
- `normalization`: targets, transfer constraints, and mode settings.
- `requant`: RNA re-quant assay and result-handling policy.
- `samples`: sample records when inline sample data is used.

## Supported Workflow Types

- `DNA_QUANT`
- `DNA_NORMALIZATION`
- `RNA_NORMALIZATION_REQUANT`

## Unit Rules

- Concentration must be represented as `ng/uL`.
- Volume must be represented as `uL`.
- Mass must be represented as `ng`.
- Molarity fields are unsupported.
- `nM`, `fmol`, and `pmol` target modes are out of scope.

## Schema Validation

Schema validation checks:

- required top-level sections;
- primitive types;
- allowed workflow types;
- required nested keys;
- obvious enum or scalar constraints.

## Domain Validation

Domain validation checks:

- wells are valid A1-H12 coordinates;
- standards default to A1-H1;
- standards plate is separate from sample plates;
- sample plates have 95 samples plus one blank;
- blank well exists;
- source and destination occupancy are not duplicated;
- concentrations are present in canonical units;
- target volume does not exceed 999 uL working volume;
- sub-1 uL transfers trigger split workflow;
- in-place mode has no destination container;
- JANUS-style artifacts are blocked for invalid batches.

## Diagnostic And Exception Codes

DSL validation may surface domain codes including:

- `MISSING_PLATE_BLANK`
- `MISSING_BATCH_STANDARD_CURVE`
- `MISSING_CONCENTRATION`
- `UNSUPPORTED_CONCENTRATION_UNIT`
- `SAMPLE_TRANSFER_BELOW_MINIMUM`
- `SPLIT_REQUIRED_HIGH_CONCENTRATION`
- `DESTINATION_VOLUME_EXCEEDED`
- `DUPLICATE_SOURCE_LOCATION`
- `DUPLICATE_DESTINATION_LOCATION`

## RAG Answer Guidance

Use this document for workflow YAML structure, supported workflow types, schema-vs-domain validation, and molarity exclusion. For a concrete workflow file, recommend deterministic `validate_workflow`.

## Cross-References

- `dna_quant_picogreen_sop.md`
- `dna_normalization_sop.md`
- `rna_norm_requant_sop.md`
- `batch_readiness_doctrine.md`
- `ai_guardrails_policy.md`
- `exception_handling_manual.md`
