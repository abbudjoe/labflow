# API Specification

## Framework

FastAPI.

## Endpoints

### Health

```http
GET /health
```

### Workflow validation

```http
POST /workflows/validate
```

Request:

```json
{
  "workflow_yaml": "..."
}
```

Response:

```json
{
  "ok": false,
  "diagnostics": []
}
```

### RAG query

```http
POST /rag/query
```

### Agent explain diagnostic

```http
POST /agent/explain-diagnostic
```

### Tool execution

```http
POST /tools/execute
```

Request:

```json
{
  "tool_name": "generate_janus_csv",
  "arguments": {"plan_id": "...", "dry_run": true}
}
```

### Eval run

```http
POST /evals/run
GET /evals/runs/{eval_run_id}
```

### Audit events

```http
GET /audit/events
GET /audit/events/{audit_event_id}
```

### Artifacts

```http
GET /artifacts/{artifact_id}
```

## API rules

- API must not require cloud credentials.
- API returns structured errors.
- API must not swallow tool errors.
- API must include trace IDs.
