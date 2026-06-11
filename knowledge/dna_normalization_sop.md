# DNA Normalization SOP

## Scope

This synthetic SOP describes deterministic DNA normalization for LabFlow batches. It covers standard new-container normalization, in-place normalization, and high-concentration split handling for dsDNA samples.

## Synthetic And Non-Production Note

This document is synthetic and portfolio-oriented. It is not a clinical, diagnostic, production lab, vendor, or proprietary SOP.

## Retrieval Tags

`dna_normalization`, `transfer_volume`, `split_workflow`, `in_place_normalization`, `ng_per_ul`, `janus`, `molarity_excluded`

## Canonical Units

- Concentration: `ng/uL`.
- Volume: `uL`.
- Mass: `ng`.
- Molar targets, `nM`, `fmol`, and `pmol` are out of scope.

## Standard New-Container Rules

- Standard normalization requires a source container and destination container.
- Destination wells must be valid A1-H12 coordinates.
- The target may be final concentration plus final volume, or final mass plus final volume.
- For concentration targets:

```text
sample_transfer_volume_ul =
  target_concentration_ng_per_ul
  * target_final_volume_ul
  / source_concentration_ng_per_ul

diluent_volume_ul =
  target_final_volume_ul - sample_transfer_volume_ul
```

- For mass targets:

```text
sample_transfer_volume_ul =
  target_mass_ng / source_concentration_ng_per_ul

diluent_volume_ul =
  target_final_volume_ul - sample_transfer_volume_ul
```

- Required source volume is:

```text
sample_transfer_volume_ul
  + source_residual_dead_volume_ul
  + robot_aspiration_safety_margin_ul
```

- LabFlow defaults are 2 uL source residual dead volume and 1 uL robot aspiration safety margin.
- The minimum transfer volume is 1 uL.
- The Matrix 96 x 1 mL working volume limit is 999 uL.
- Diluent is added before sample transfer.
- Invalid samples generate no robot transfer.

## Human SOP Alignment

Human lab SOPs often separate setup assumptions, calculation rules, acceptance criteria, exceptions, operator review, and records. LabFlow adapts that pattern into deterministic normalization planning: source concentration and volume must come from trusted inputs, transfer and diluent volumes are computed by `generate_normalization_plan`, low-volume or high-concentration conditions become diagnostics, and JANUS-style outputs remain gated dry-run previews. The AI may summarize these rules, but it must not perform unsourced transfer math or invent sample values.

## In-Place Normalization Rules

- In-place normalization has no destination container.
- Only diluent is added to the source well.
- No sample transfer occurs.
- Mixing is skipped.
- A destination supplied for in-place normalization is invalid.
- In-place selection must be explicit and traceable in the plan.

## Split Workflow Rules

- If the calculated sample transfer volume is below 1 uL because the source concentration is high, LabFlow must trigger split workflow.
- The system must not silently round a sub-1 uL transfer up or down for standard normalization.
- The split workflow uses a 1 uL source sample transfer to create a diluted child sample.
- The child sample requires re-quantification.
- Follow-up normalization uses the measured child concentration, not an inferred concentration.

## Diagnostic And Exception Codes

- `MISSING_CONCENTRATION`: stock concentration is absent.
- `INVALID_CONCENTRATION`: stock concentration is non-positive or malformed.
- `UNSUPPORTED_CONCENTRATION_UNIT`: a unit outside `ng/uL` is supplied.
- `SOURCE_CONCENTRATION_BELOW_TARGET`: source cannot reach the requested target.
- `INSUFFICIENT_SOURCE_VOLUME`: available source volume is below required source volume.
- `SAMPLE_TRANSFER_BELOW_MINIMUM`: transfer would be below 1 uL and must not be rounded.
- `SAMPLE_TRANSFER_ABOVE_MAXIMUM`: calculated transfer violates configured limits.
- `DILUENT_VOLUME_NEGATIVE`: target math would require negative diluent.
- `DESTINATION_VOLUME_EXCEEDED`: destination volume exceeds the 999 uL working volume.
- `SPLIT_REQUIRED_HIGH_CONCENTRATION`: split workflow is required for a high-concentration sample.
- `SPLIT_REQUANT_REQUIRED`: a split child sample must be re-quantified before follow-up normalization.
- `IN_PLACE_NORMALIZATION_SELECTED`: in-place mode was selected.
- `IN_PLACE_NORMALIZATION_INVALID`: in-place configuration violates rules.

## RAG Answer Guidance

Use this document to answer questions about transfer formulas, canonical units, in-place normalization, split workflow, and why molarity requests are unsupported. For robot artifact questions, cite `janus_csv_worklist_spec.md` as well.

## Cross-References

- `dna_quant_picogreen_sop.md`
- `rna_norm_requant_sop.md`
- `batch_readiness_doctrine.md`
- `exception_handling_manual.md`
- `janus_csv_worklist_spec.md`
- `sample_ancestry_policy.md`
- `labflow_dsl_reference.md`
- `sop_alignment_mapping.md`
