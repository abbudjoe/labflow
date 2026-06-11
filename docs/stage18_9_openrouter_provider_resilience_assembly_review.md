# Stage 18.9 OpenRouter Provider Resilience Assembly Review

Status: successful

Authoritative scope:

- `.codex_build/stage18_9_openrouter_provider_resilience_implementation_scope.md`

## Extracted DoD Checklist

| ID | DoD Item | Status | Evidence |
| --- | --- | --- | --- |
| D1 | Assembly ledger exists before code edits and records final evidence/status. | met | This ledger was created before code edits. |
| D2 | OpenRouter client boundary preserves sanitized HTTP status, headers, decoded body, response preview, elapsed time, and retry header context. | met | Implemented typed boundary and regression tests. |
| D3 | OpenRouter response classification is error-first, handles missing choices, finish_reason error, malformed message/content, and sanitized provider error bodies. | met | Provider error precedence, finish_reason error, and provider code taxonomy tests pass. |
| D4 | Retry/backoff is bounded, retryable-only, records attempts, and fails closed after exhaustion without retrying schema/model-output failures. | met | Retry success, retry exhaustion, failover, and schema-no-retry tests pass. |
| D5 | Diagnostics are adapter/runtime-owned, sanitized, do not persist secrets/raw prompts/raw provider bodies, and expose provider failure metadata in traces/evals. | met | Metadata leakage and trace execution metadata tests pass. |
| D6 | Inference eval reports provider failures separately from safety violations and record effective timeout/retry/metadata/failover config. | met | Focused tests and no-live artifact verify report shape. |
| D7 | Docs/env examples explain provider failure vs safety violation, retry/failover defaults, metadata opt-in, and live eval timeout recommendations. | met | `.env.example`, `docs/inference_adapter.md`, and `docs/inference_eval_ladders.md`. |
| D8 | Required local tests and no-live smoke pass without OpenRouter credentials or cloud resources. | met | `46 passed`; no-live ladder wrote `inference_eval_ladder_20260611T021501123957Z`. |
| D9 | Subagent spec-conformance review is clean or valid findings are addressed. | met | Reviewer pass 2 and final quick check are clean. |

## Target Contract

Stage 18.9 must harden the OpenRouter provider boundary while preserving
LabFlow's core doctrine: deterministic validators own lab truth, provider
failures fail closed, local tests remain credential-free, and provider
diagnostics must be sanitized.

No live OpenRouter, cloud, or paid compute run is authorized or required.

## Review Pass 1

Reviewer: Raman (`019eb46e-7ead-7fa2-b239-76f344a294d0`)

Outcome: `review-failed`

Valid findings addressed:

- Valid JSON provider error bodies could leak provider metadata values through `body_text_preview`.
- 200-level provider error codes were not mapped or retried.
- Grounded answer eval composer diagnostics were too lossy and could misclassify model-output schema failures as provider failures.
- Exhausted retry/failover metadata dropped prior attempts.
- Assembly documents needed final evidence/status updates.

Post-fix evidence:

```text
46 passed in 1.55s
Wrote /Users/joseph/labflow/artifacts/inference_eval_ladders/inference_eval_ladder_20260611T021501123957Z.json
Wrote /Users/joseph/labflow/artifacts/inference_eval_ladders/inference_eval_ladder_20260611T021501123957Z.md
```

## Review Pass 2

Reviewer: Raman (`019eb46e-7ead-7fa2-b239-76f344a294d0`)

Outcome: clean, with one non-blocking preview edge note.

## Final Quick Check

Reviewer: Raman (`019eb46e-7ead-7fa2-b239-76f344a294d0`)

Outcome: clean.

Additional hardening after pass 2:

- `_http_response_from_raw()` now emits `body_text_preview` only when JSON decoding fails.
- Valid JSON non-object bodies do not persist previews.
- Added `test_http_response_preview_is_only_for_invalid_json`.
