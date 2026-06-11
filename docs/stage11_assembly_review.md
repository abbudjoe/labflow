# Stage 11 Assembly Review

Review date: 2026-06-09

Stage: `11_fastapi_api`

Authoritative spec: `.codex_build/prompts/11_fastapi_api.md`

Status: `successful`

## Target Contract

Expose local validation, RAG, agent, tools, evals, audit events, and artifacts through a FastAPI API with trace IDs, structured errors, local filesystem artifact persistence, OpenAPI docs, FastAPI TestClient coverage, and no cloud dependency.

## Extracted DoD Checklist

| DoD item | Status | Evidence |
| --- | --- | --- |
| D1: Read project doctrine/specs before implementation | met | Read Stage 11 prompt, `specs/08_api_spec.md`, and required project doctrine files from prior stage context. |
| D2: Add `apps/api/src/labflow_api/main.py` | met | Added FastAPI app factory and router registration. |
| D3: Add `routes/health.py` | met | Added `GET /health`. |
| D4: Add `routes/workflows.py` | met | Added `POST /workflows/validate`. |
| D5: Add `routes/rag.py` | met | Added `POST /rag/query`. |
| D6: Add `routes/agent.py` | met | Added `POST /agent/explain-diagnostic`. |
| D7: Add `routes/tools.py` | met | Added `POST /tools/execute`. |
| D8: Add `routes/evals.py` | met | Added `POST /evals/run` and `GET /evals/runs/{eval_run_id}`. |
| D9: Add `routes/audit.py` | met | Added `GET /audit/events` and `GET /audit/events/{audit_event_id}`. |
| D10: Add `routes/artifacts.py` | met | Added `GET /artifacts/{artifact_id}`. |
| D11: Add `settings.py` | met | Added settings, shared API state, and local file artifact store. |
| D12: Implement required endpoints from `specs/08_api_spec.md` | met | OpenAPI reports all 10 required paths. |
| D13: Use local filesystem artifact store | met | `LocalFileArtifactStore` persists committed artifact records under configurable local path. |
| D14: Include trace ID in responses | met | Shared `envelope` and `error_envelope` include `trace_id`; tests assert success, not-found, validation-error, and unexpected-error trace IDs. |
| D15: Return structured errors and do not swallow tool errors | met | App-level handlers return structured errors for known, validation, and unexpected errors; tool route returns deterministic tool result payload including blocked/error statuses. |
| D16: Require no cloud dependency | met | Implementation uses local paths and in-process stores only; no cloud SDK or credentials. |
| D17: Add API tests with FastAPI TestClient | met | Added `apps/api/tests/test_fastapi_api.py`. |
| D18: API starts locally and OpenAPI docs are available | met | `create_app().openapi()` succeeds and TestClient retrieves `/openapi.json`. |
| D19: Tests/lint/type pass | met | Focused API tests `9 passed`; full `make test` `108 passed`; lint and type passed. |
| D20: Reference repo not modified and no cloud mutation | met | Reference repo status remains `?? .DS_Store`; no cloud commands run. |
| D21: Assembly subagent review clean | met | Reviewer Kierkegaard found two valid structured-error findings; both were fixed and re-review was clean. |

## Planned Evidence Commands

```text
uv run --python python3 --with pytest --with pydantic --with pyyaml --with fastapi --with httpx env PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src:apps/api/src python -m pytest apps/api/tests -q
make test
make lint
make type
uv run --python python3 --with fastapi --with pydantic --with pyyaml env PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src:apps/api/src python -c "from labflow_api.main import create_app; app = create_app(); assert app.openapi()['paths']['/health']"
git -C /Users/joseph/ngs_lab_automation status --short
```

## Changed Files

- `Makefile`
- `apps/api/pyproject.toml`
- `apps/api/src/labflow_api/main.py`
- `apps/api/src/labflow_api/routes/__init__.py`
- `apps/api/src/labflow_api/routes/_shared.py`
- `apps/api/src/labflow_api/routes/agent.py`
- `apps/api/src/labflow_api/routes/artifacts.py`
- `apps/api/src/labflow_api/routes/audit.py`
- `apps/api/src/labflow_api/routes/evals.py`
- `apps/api/src/labflow_api/routes/health.py`
- `apps/api/src/labflow_api/routes/rag.py`
- `apps/api/src/labflow_api/routes/tools.py`
- `apps/api/src/labflow_api/routes/workflows.py`
- `apps/api/src/labflow_api/settings.py`
- `apps/api/tests/test_fastapi_api.py`

## Implementation Summary

- Added FastAPI app factory with required route registration and structured exception handlers.
- Added shared local API state over the existing RAG index, agent runtime, tool runtime, eval runner, audit store, and artifact records.
- Added local filesystem persistence for committed artifact records.
- Added trace ID envelopes for success and error responses.
- Added TestClient coverage for health/OpenAPI, workflow validation, RAG, agent diagnostic explanation, tool dry-run/commit, audit lookup, artifact lookup, eval run lookup, and structured not-found errors.

## Evidence

```text
uv run --python python3 --with pytest --with pydantic --with pyyaml --with fastapi --with httpx env PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src:apps/api/src python -m pytest apps/api/tests -q
# 9 passed, 1 warning

make test
# 108 passed, 1 warning

make lint
# All checks passed

make type
# mypy success in 75 source files; VS Code extension compile succeeded

uv run --python python3 --with fastapi --with pydantic --with pyyaml env PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src:apps/api/src python -c "from labflow_api.main import create_app; app = create_app(); paths = app.openapi()['paths']; assert '/health' in paths and '/tools/execute' in paths; print(len(paths))"
# 10

git -C /Users/joseph/ngs_lab_automation status --short
# ?? .DS_Store
```

## Review Findings

Reviewer: Kierkegaard (`019eae4e-5b6f-77d3-a01c-50eeda9972f7`)

Initial classification: `review-failed`

Findings addressed:

- P1: FastAPI request validation errors bypassed the API envelope and trace ID contract. Fixed by adding a `RequestValidationError` handler that returns `VALIDATION_ERROR` with trace ID and validation details.
- P2: Unexpected runtime errors could still return default 500 payloads without trace IDs. Fixed by adding a catch-all exception handler returning structured `INTERNAL_ERROR` without stack leakage.

Re-review classification: `clean`

Reviewer conclusion: D14, D15, and D21 are met.

## Residual Risks

- The API stores eval reports and runtime audit state in process memory; durable persistence belongs in later cloud/API hardening work.
- Local artifact persistence writes committed artifact records as JSON files, not production robot files or cloud artifacts.
- TestClient emits a Starlette deprecation warning about `httpx`; tests pass and this is dependency ecosystem noise rather than a LabFlow behavior failure.

## Final Classification

`successful`
