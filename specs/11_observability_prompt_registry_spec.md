# Observability and Prompt Registry Specification

## Purpose

The project should demonstrate production AI thinking: prompt versioning, model abstraction, eval records, trace IDs, latency tracking, and regression reports.

## Prompt registry

Prompt files:

```text
prompts/runtime/rag_answer.md
prompts/runtime/agent_planner.md
prompts/runtime/diagnostic_explainer.md
prompts/runtime/patch_proposer.md
```

Prompt metadata:

```json
{
  "prompt_id": "diagnostic_explainer",
  "version": "0.1.0",
  "sha256": "...",
  "created_at": "...",
  "notes": "Initial grounded diagnostic explanation prompt."
}
```

## Model registry abstraction

Do not hard-code one provider throughout the code. Use adapter interfaces.

For tests, provide a deterministic fake model.

## Trace model

Each request should have:

- trace_id;
- request_id;
- prompt_id/version;
- model_id/version;
- retrieved chunk IDs;
- tool calls;
- latency_ms;
- token/cost placeholders where available;
- outcome status.

## Eval regression

Eval reports should include current metrics and baseline comparison.
