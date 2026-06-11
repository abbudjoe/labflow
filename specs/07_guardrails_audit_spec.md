# Guardrails, Approval, and Audit Specification

## Guardrail principles

1. Deterministic validators gate robot-ready artifacts.
2. AI does not mutate state silently.
3. AI does not invent missing data.
4. Every tool call is auditable.
5. High-risk actions require dry-run and approval.

## Action classes

### Read-only

- validate workflow;
- retrieve docs;
- explain exception;
- compare throughput;
- run evals.

### Artifact-generating dry-run

- generate JANUS CSV preview;
- generate normalization plan preview;
- generate patch proposal.

### Commit actions

- write generated artifact to artifact store;
- apply workflow patch;
- mark batch resolved.

Commit actions require:

- prior dry-run event ID;
- explicit approval token;
- deterministic validation pass;
- audit event.

## Audit event shape

```json
{
  "audit_event_id": "audit_001",
  "timestamp": "2026-06-08T12:00:00Z",
  "actor_type": "agent",
  "actor_id": "labflow-agent",
  "action": "generate_janus_csv",
  "mode": "dry_run",
  "workflow_id": "RNA_BATCH_001",
  "tool_name": "generate_janus_csv",
  "input_hash": "sha256:...",
  "result_status": "blocked",
  "exception_codes": ["MISSING_CONCENTRATION"],
  "approval_token_id": null,
  "artifact_ids": []
}
```

## Blocked actions

The system must block:

- JANUS generation with unresolved errors;
- commit without dry-run;
- commit without approval token;
- robot artifact generation for invalid samples;
- any attempt to use molarity mode;
- any attempt to infer missing concentrations.
