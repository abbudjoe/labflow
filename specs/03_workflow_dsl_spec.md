# LabFlow Workflow DSL Specification

## Purpose

The LabFlow DSL is a YAML configuration format for defining synthetic LIMS workflows. It should be understandable to humans, validated by JSON Schema, and checked by domain validators.

## File extension

Recommended:

```text
*.labflow.yaml
*.workflow.yaml
```

## Required top-level keys

```yaml
workflow:
  name: rna_norm_requant
  version: 0.1
  type: rna_norm_requant

batch:
  batch_id: RNA_BATCH_001
  containers_per_batch: 3
  plate_format: 96
  samples_per_plate: 95
  blank_well: H12

standards:
  standards_plate_id: RNA_STD_001
  wells:
    A1: STD_1
    B1: STD_2
    C1: STD_3
    D1: STD_4
    E1: STD_5
    F1: STD_6
    G1: STD_7
    H1: STD_8
  curve_model: linear

containers:
  source:
    registry_container_type: matrix_96_1ml_screwtop
  destination:
    registry_container_type: matrix_96_1ml_screwtop

normalization:
  target_concentration_ng_per_ul: 5
  target_final_volume_ul: 100
  minimum_transfer_volume_ul: 1
  source_residual_dead_volume_ul: 2
  robot_aspiration_safety_margin_ul: 1

requant:
  assay: RiboGreen
  result_handling: use_as_downstream_concentration
```

## Schema validation vs domain validation

Schema validation checks shape, required keys, primitive types, enums, and basic constraints.

Domain validation checks lab-specific rules, such as:

- standards wells are valid;
- one blank exists per sample plate;
- sample count does not exceed 95;
- target volume <= max working volume;
- no molarity fields are present;
- split workflow is triggered when transfer < 1 µL;
- JANUS generation is blocked for invalid batch.

## Diagnostic output shape

```json
{
  "code": "MISSING_PLATE_BLANK",
  "severity": "error",
  "message": "Sample plate DNA_PLATE_001 is missing required blank well.",
  "path": "batch.blank_well",
  "source": "domain_validator",
  "suggested_action": "Add a blank_well value or mark the plate for manual review."
}
```

## VS Code integration

The extension should surface diagnostics from schema and domain validation. It should not reimplement domain validation in TypeScript if the Python API can supply diagnostics.
