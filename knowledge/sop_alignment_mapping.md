# Public SOP Alignment Mapping

## Scope

This document maps public human-directed SOP patterns into LabFlow's synthetic
knowledge corpus. It exists so RAG answers can cite why LabFlow SOPs are shaped
like real lab documents while still making clear that LabFlow is not a clinical,
diagnostic, production, vendor, or proprietary system.

## Synthetic And Non-Production Note

This mapping is synthetic and portfolio-oriented. Public SOP/protocol examples
are used only for document-pattern alignment. LabFlow does not copy operational
instructions, validate real clinical procedures, or authorize robot execution.

## Retrieval Tags

`sop_alignment`, `public_sop_patterns`, `controlled_documents`, `human_sop`, `deterministic_validation`, `no_invention`

## Public Reference Examples

- NCI BRD PicoGreen SOP PDF:
  `https://brd.nci.nih.gov/brd/sop/download-pdf/1456`
- NCI BRD Quant-iT PicoGreen dsDNA quantification SOP PDF:
  `https://brd.nci.nih.gov/brd/sop/download-pdf/3236`
- protocols.io DNA quantification in plates PicoGreen protocol:
  `https://www.protocols.io/view/dna-quantification-in-plates-picogreen-protocol-bbjdiki6.pdf`
- protocols.io Quant-iT PicoGreen dsDNA quantification protocol:
  `https://www.protocols.io/view/qant-it-picogreen-dsdna-quantification-bftfjnjn.pdf`

## Common Human SOP Patterns

Public quantification SOPs and protocols commonly separate:

- scope and intended use;
- required inputs, reagents, instruments, or data files;
- plate layout expectations;
- standards, blanks, and controls;
- reading or measurement provenance;
- calculation and reporting provenance;
- acceptance criteria and exceptions;
- operator review or repeat-run decisions;
- records, exports, and traceability.

## LabFlow Adaptation

LabFlow adapts those patterns into synthetic software contracts:

- Scope becomes workflow type and supported analyte.
- Inputs become workflow YAML, TSV/CSV fixtures, sample manifests, and tool
  arguments.
- Plate layout becomes deterministic A1-H12 well validation, standards layout,
  and blank requirements.
- Controls become standards, blanks, QC status, and exception codes.
- Calculation provenance becomes deterministic core math, not LLM arithmetic.
- Acceptance criteria become readiness gates and validator diagnostics.
- Operator review becomes explicit manual review, exclusion, or repeat quant.
- Records become audit events, eval artifacts, and dry-run artifact previews.

## Controlled SOP Templates

LabFlow includes controlled SOP-style templates that follow the shape of public
laboratory SOPs while adapting all rules to the synthetic LabFlow domain:

- `controlled_sop_dna_quantification.md`: document control, fluorescence DNA
  quantification inputs, QC acceptance criteria, nonconformance, records, and
  deterministic quantification enforcement.
- `controlled_sop_rna_requant.md`: document control, RNA re-quant result review,
  downstream concentration source rules, manual review, records, and
  deterministic re-quant enforcement.
- `controlled_sop_normalization_worklist_review.md`: document control,
  normalization readiness, JANUS dry-run review, approval/audit policy, and
  deterministic artifact gating.

## Concentration Source Boundary

Policy questions about which trusted concentration source to use are supported
by the mapped SOP corpus. For RNA re-quant workflows, downstream steps use the
measured re-quant result.

Concrete requests for a missing numeric concentration are not supported unless
the value comes from trusted workflow data or deterministic tool output. The AI
must not invent, estimate, or infer missing sample concentrations.

## Deterministic Enforcement Surfaces

- `validate_workflow`: checks LabFlow YAML shape and domain diagnostics.
- `validate_batch`: checks concrete readiness before readiness claims.
- `process_quantification`: turns instrument-like readings and controls into
  stock concentration records.
- `generate_normalization_plan`: computes transfer and diluent volumes.
- `process_rna_requant`: attaches valid re-quant results as downstream
  concentration and blocks missing or invalid results.
- `generate_janus_csv`: produces dry-run previews only when validation permits.

## RAG Answer Guidance

Use this mapping when asked how LabFlow SOPs relate to real lab SOPs, how public
SOP patterns were adapted, or why the project separates human SOP guidance from
deterministic validation. Also cite the specific workflow SOP for domain rules.

## Cross-References

- `dna_quant_picogreen_sop.md`
- `dna_normalization_sop.md`
- `rna_norm_requant_sop.md`
- `controlled_sop_dna_quantification.md`
- `controlled_sop_rna_requant.md`
- `controlled_sop_normalization_worklist_review.md`
- `batch_readiness_doctrine.md`
- `ai_guardrails_policy.md`
- `janus_csv_worklist_spec.md`
