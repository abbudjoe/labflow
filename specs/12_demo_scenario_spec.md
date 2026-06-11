# Demo Scenario Specification

## Primary demo workflow

`examples/workflows/invalid_rna_norm_requant.workflow.yaml`

Must include:

- 3 containers per batch.
- Standards plate A1-H1.
- One sample plate missing blank.
- One sample missing concentration.
- One high-concentration sample requiring split workflow.
- One in-place normalization case.
- JANUS worklist generation blocked until errors resolved.

## Supporting examples

- `valid_dna_quant.workflow.yaml`
- `valid_dna_normalization.workflow.yaml`
- `valid_rna_norm_requant.workflow.yaml`
- `invalid_missing_blank.workflow.yaml`
- `invalid_molar_target.workflow.yaml`
- `invalid_duplicate_well.workflow.yaml`

## Expected artifacts

- validation report JSON;
- exception report CSV;
- JANUS CSV preview;
- audit log JSONL;
- eval report JSON;
- demo screenshots optionally.
