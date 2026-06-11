# API Contract

The FastAPI app is a local-first boundary for the same deterministic workflow,
RAG, agent, tool, eval, audit, and artifact capabilities used by CLI and VS
Code.

Base URL in local demos:

```text
http://localhost:8000
```

## Health

```http
GET /health
```

Returns service status.

## Workflow Validation

```http
POST /workflows/validate
```

Request:

```json
{
  "workflow_yaml": "..."
}
```

Response data:

- `ok`: true when no diagnostics exist;
- `diagnostics`: deterministic validation diagnostics with code, message,
  severity, path, and suggested action.

## RAG Query

```http
POST /rag/query
```

Request:

```json
{
  "question": "Why is this batch not robot-ready?"
}
```

Response data includes answer text, citations, retrieved chunk IDs, unsupported
status, and recommended tools.

## RAG Debug

```http
POST /rag/debug
```

Returns retrieval diagnostics:

- normalized terms;
- expanded query terms;
- source-family requirements;
- source-family counts;
- ranked top results;
- supplemented sources;
- missing required source families;
- stale sources;
- policy conflicts.

## Agent Diagnostic Explanation

```http
POST /agent/explain-diagnostic
```

Request:

```json
{
  "question": "Why is this batch not robot-ready?",
  "diagnostic_code": "MISSING_CONCENTRATION",
  "workflow_yaml": "...",
  "batch_id": "batch_001"
}
```

Response data is the structured agent response, including sources, tool calls,
next safe action, blocked reason, and trace metadata.

## Tool Execution

```http
POST /tools/execute
```

Request:

```json
{
  "tool_name": "generate_janus_csv",
  "arguments": {
    "plan_id": "examples/expected/generated/fixed_rna_norm_requant.normalization.yaml",
    "dry_run": true
  },
  "reason": "Portfolio dry-run preview"
}
```

Rules:

- read-only tools run in read-only mode;
- artifact tools require `dry_run=true` for dry-run mode;
- commit mode requires a prior dry-run audit event and approval token;
- invalid batches must not produce robot-facing artifacts.

## Eval Runs

```http
POST /evals/run
GET /evals/runs/{eval_run_id}
```

Runs and retrieves local RAG eval reports.

## Audit Events

```http
GET /audit/events
GET /audit/events/{audit_event_id}
```

Returns audit events created by controlled tool execution.

## Artifacts

```http
GET /artifacts/{artifact_id}
```

Returns committed artifact records from local storage. Dry-run previews are not
silently committed.

## Error Envelope

All API responses use a consistent envelope:

```json
{
  "ok": false,
  "trace_id": "trace_...",
  "error": {
    "code": "BAD_REQUEST",
    "message": "...",
    "details": {}
  }
}
```
