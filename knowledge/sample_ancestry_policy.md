# Sample Ancestry Policy

## Scope

This policy defines how LabFlow tracks synthetic sample identity across quantification, normalization, in-place updates, split child samples, RNA re-quantification, manual review, and exclusion.

## Synthetic And Non-Production Note

This document is synthetic and non-production. It is not a clinical, diagnostic, production lab, vendor, or proprietary SOP.

## Retrieval Tags

`ancestry`, `sample_id`, `parent_child`, `split_workflow`, `requant`, `audit`, `manual_review`

## Core Rules

- Sample ID is mandatory.
- Sample ancestry is tracked by sample ID.
- Parent sample ID, child sample ID, source location, and destination location must be preserved when applicable.
- A derived sample must not overwrite the identity of its parent.
- Split workflow creates a child sample and requires re-quant before follow-up normalization.
- RNA re-quant results attach to the expected normalized sample or child sample.
- In-place normalization updates the source well without a destination transfer and must still create an ancestry event.
- Manual overrides, exclusions, and corrections must be explicit and audited.
- The agent must not invent parent/child relationships.

## Human SOP Alignment

Human SOP records commonly preserve sample identity, derived-sample links, review decisions, and exclusions. LabFlow adapts that pattern into deterministic ancestry events. Re-quant, split, in-place normalization, manual override, and exclusion records are explicit state transitions, not model-generated guesses.

## Ancestry Event Types

- `QUANTIFIED`: instrument-derived stock concentration is assigned.
- `NORMALIZED_STANDARD`: source sample is transferred into a destination container.
- `NORMALIZED_IN_PLACE`: source sample is diluted in place.
- `SPLIT_CREATED`: high-concentration source creates a diluted child sample.
- `REQUANTIFIED`: re-quant result becomes downstream concentration.
- `MANUAL_OVERRIDE`: human decision changes state.
- `EXCLUDED`: sample is intentionally removed from robot-transfer eligibility.

## Location Rules

- Source container and source well are required for valid samples.
- Destination container and well are required for standard new-container normalization.
- Destination must be absent for in-place normalization.
- Duplicate source locations block execution.
- Duplicate destination locations block execution.

## Diagnostic And Exception Codes

- `MISSING_SAMPLE_ID`
- `DUPLICATE_SAMPLE_ID`
- `MISSING_SOURCE_LOCATION`
- `INVALID_SOURCE_LOCATION`
- `DUPLICATE_SOURCE_LOCATION`
- `MISSING_DESTINATION_LOCATION`
- `INVALID_DESTINATION_LOCATION`
- `DUPLICATE_DESTINATION_LOCATION`
- `DESTINATION_SUPPLIED_FOR_IN_PLACE`
- `SPLIT_REQUIRED_HIGH_CONCENTRATION`
- `SPLIT_REQUANT_REQUIRED`
- `INVALID_REQUANT_RESULT`

## RAG Answer Guidance

Use this policy when answering how split children are tracked, why duplicate wells block execution, or why a re-quant row must match an expected normalized sample. For artifact questions, cite the JANUS spec as well.

## Cross-References

- `dna_normalization_sop.md`
- `rna_norm_requant_sop.md`
- `exception_handling_manual.md`
- `janus_csv_worklist_spec.md`
- `ai_guardrails_policy.md`
- `sop_alignment_mapping.md`
