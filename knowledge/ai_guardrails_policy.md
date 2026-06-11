# AI Guardrails Policy

## Scope

This policy defines what the LabFlow AI assistant may explain, retrieve, propose, validate, dry-run, and block in the synthetic workflow studio.

## Synthetic And Non-Production Note

This document is synthetic and non-production. It is not a clinical, diagnostic, production lab, vendor, or proprietary SOP, and it does not authorize real laboratory execution.

## Retrieval Tags

`ai_guardrails`, `rag`, `citations`, `tools`, `dry_run`, `approval`, `audit`, `no_invention`

## Rules

- Deterministic validators own lab truth.
- The AI may retrieve, explain, summarize, propose patches, and call deterministic tools.
- The AI must cite retrieved knowledge chunks for domain claims.
- If the corpus does not support an answer, the AI must say it is not supported.
- The AI must not invent missing sample IDs, concentrations, source locations, destination wells, standards, blanks, or JANUS worklist rows.
- The AI must not bypass deterministic validation.
- The AI must not present synthetic workflows as clinical, diagnostic, or production-ready.
- The AI may answer SOP policy questions about which trusted data source should be used, but it must not supply a missing numeric lab value without trusted workflow data or deterministic tool output.

## Human SOP Alignment

LabFlow assumes real laboratories already have controlled human SOPs. The AI assistant is an interpretation and workflow-development aid over mapped SOP knowledge, not a replacement for SOP ownership, validation, operator review, or records. Public SOP patterns inform the structure of the synthetic corpus; they do not authorize clinical, production, proprietary, or robot-ready execution.

## Tool And Mutation Rules

- Read-only actions include retrieval, validation, exception explanation, throughput comparison, and eval runs.
- Artifact-generating actions must use dry-run first.
- Commit actions require a prior dry-run event ID, explicit approval token, deterministic validation pass, and audit event.
- Every tool call must create an audit event.
- A failed or blocked tool call still requires an audit event.
- Local commit-mode artifact records require a prior successful dry-run audit event and a matching approval token.
- The Stage 10 artifact store is local and synthetic; it records approved artifacts for demos and tests, not production robot execution.

## Robot Artifact Rules

- JANUS-style worklists require deterministic validation.
- Invalid batches must not generate robot-ready artifacts.
- Invalid samples must not appear in robot transfer rows.
- A dry-run preview may be shown only when deterministic planning supports it.
- The AI must not repair a worklist by guessing values.

## Unsupported Requests

The assistant must block or decline requests to:

- use molarity, `nM`, `fmol`, or `pmol` target modes;
- infer a missing concentration;
- fabricate a blank or standards plate;
- create robot-ready artifacts for invalid samples;
- commit changes without dry-run and approval;
- claim clinical, diagnostic, or production readiness.

## Diagnostic And Exception Codes

- `COMMIT_MODE_NOT_AVAILABLE`: commit mode is unavailable until guardrail storage exists.
- `COMMIT_REQUIRES_DRY_RUN`: commit was requested without a prior dry-run audit event.
- `COMMIT_REQUIRES_APPROVAL`: commit was requested without a matching approval token.
- `DRY_RUN_NOT_SUCCESSFUL`: commit was requested from a blocked or failed dry-run.
- `DRY_RUN_INPUT_MISMATCH`: commit inputs do not match the approved dry-run inputs.
- `JANUS_BLOCKED_FOR_INVALID_BATCH`: invalid batch blocks artifact generation.
- `MISSING_CONCENTRATION`: AI must not invent concentration.
- `MISSING_PLATE_BLANK`: AI must not invent blank data.
- `MISSING_BATCH_STANDARD_CURVE`: AI must not invent standard curve data.
- `UNSUPPORTED_CONCENTRATION_UNIT`: molarity or noncanonical units are unsupported.

## RAG Answer Guidance

Use this policy for questions about what the AI can do, why a tool call is blocked, why citations are required, why dry-run is mandatory, or why missing lab data cannot be guessed.

## Cross-References

- `batch_readiness_doctrine.md`
- `exception_handling_manual.md`
- `janus_csv_worklist_spec.md`
- `labflow_dsl_reference.md`
- `sample_ancestry_policy.md`
- `sop_alignment_mapping.md`
