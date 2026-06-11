# Stage 18.8 OpenRouter Provider Resilience Assembly Review

Status: successful

Authoritative scope:

- `.codex_build/stage18_8_openrouter_provider_resilience_investigation_scope.md`

## Extracted DoD Checklist

| ID | DoD Item | Status | Evidence |
| --- | --- | --- | --- |
| D1 | Assembly ledger exists before final investigation/spec documentation is finalized. | met | This ledger was created before final spec documentation. |
| D2 | Investigation quantifies the observed failure pattern from the live artifact, including affected suites/cases, duplicate tier effects, elapsed time, and whether failures are lab reasoning failures or provider/adapter failures. | met | `docs/stage18_8_openrouter_provider_resilience_plan.md` suite summary and missing-choices attempt table. |
| D3 | Investigation maps the failure to current adapter behavior and identifies missing contracts in the OpenRouter boundary. | met | Current adapter behavior and root-cause sections in the plan. |
| D4 | Investigation checks current official OpenRouter documentation relevant to response shape, error bodies, router metadata, retries, and structured outputs. | met | Plan links OpenRouter chat completion, errors, router metadata, and structured output docs. |
| D5 | Proposed fix includes detailed implementation specs for response classification, sanitized diagnostics, retry/backoff/failover policy, eval reporting, and tests. | met | Proposed fix spec sections 1-9 plus test spec. |
| D6 | Proposed fix preserves LabFlow doctrine: deterministic validators remain authoritative, provider failures fail closed, secrets/raw prompts are not persisted, and local tests remain credential-free. | met | Safety and doctrine constraints plus diagnostic ownership/sanitization rules. |
| D7 | Proposed evidence gates are concrete and separate required local tests from optional live evidence. | met | Required local evidence and optional live evidence sections in the plan. |
| D8 | Investigation receives subagent spec-conformance review; valid findings are addressed; final ledger records evidence and status for every DoD item. | met | Subagent `019eb457-27b9-7bb0-b5ca-7a4429607ea4` reviewed twice; valid findings addressed; final statuses recorded here. |

## Target Contract

Stage 18.8 must explain the `openrouter_response_missing_choices` failures as
far as the available artifact, code, and public provider docs allow, then
produce an implementation-ready fix spec. It must not make provider failures
authoritative over lab truth, expose secrets, or require live credentials for
local tests.

## Planned Evidence

- Local artifact inspection of
  `artifacts/inference_eval_ladders/inference_eval_ladder_20260611T005857101049Z.json`.
- Code inspection of OpenRouter adapters and eval harnesses.
- Official OpenRouter documentation references.
- Subagent spec-conformance review.

No live OpenRouter, cloud, or paid compute run is authorized or required.

## Evidence Summary

Inspected artifact:

- `artifacts/inference_eval_ladders/inference_eval_ladder_20260611T005857101049Z.json`

Observed pattern:

- OpenRouter `control_parity`: 59/62;
- deterministic `control_parity`: 62/62;
- five OpenRouter planner attempts had `openrouter_response_missing_choices`;
- three of those counted as parity failures;
- two workflow-backed cases still passed because deterministic `validate_batch`
  was forced from request-owned workflow YAML;
- observed `missing_choices` attempts elapsed at roughly 62.3-62.8 seconds;
- no missing required tool calls or unsafe robot/tool behavior were identified
  in those cases.

Inspected code:

- `packages/labflow-agent/src/labflow_agent/openrouter.py`
- `packages/labflow-agent/src/labflow_agent/openrouter_answer.py`
- `packages/labflow-agent/src/labflow_agent/runtime.py`
- `scripts/run_inference_eval_ladder.py`
- `scripts/run_model_eval_comparison.py`
- `packages/labflow-agent/tests/test_openrouter_model.py`
- `packages/labflow-agent/tests/test_openrouter_answer.py`

Official provider docs checked:

- `https://openrouter.ai/docs/api/api-reference/chat/send-chat-completion-request`
- `https://openrouter.ai/docs/api/reference/errors-and-debugging`
- `https://openrouter.ai/docs/guides/features/router-metadata`
- `https://openrouter.ai/docs/guides/features/structured-outputs`

## Proposed Fix Summary

The plan proposes:

- a typed `OpenRouterHTTPResponse` boundary that preserves status, headers,
  retry headers, decoded body, sanitized preview, and elapsed time;
- error-first response classification before accepting `choices`;
- bounded retry/backoff and optional explicit failover;
- adapter/runtime-owned sanitized diagnostic details;
- optional router metadata summaries;
- configurable structured-output mode;
- hard live eval deadlines;
- provider-failure metrics separate from safety violations;
- local credential-free tests plus optional live evidence.

## Subagent Review

Reviewer: `019eb457-27b9-7bb0-b5ca-7a4429607ea4`

Initial findings addressed:

- Response classification order was too permissive. Fixed by requiring
  top-level error classification first and treating `finish_reason=error` as
  non-success.
- Retry/backoff lacked a typed HTTP boundary. Fixed by specifying
  `OpenRouterHTTPResponse` and transport error behavior.
- Diagnostic details needed adapter-owned provenance and stricter sanitization.
  Fixed with ownership and redaction/truncation contracts.
- Failover trace semantics needed a concrete data path. Fixed with
  `ProviderAttempt`, `ModelExecutionMetadata`, and an optional metadata provider
  protocol.
- Timeout analysis omitted the inference ladder's current default. Fixed by
  noting the `OPENROUTER_TIMEOUT_SECONDS=20` default and the artifact's missing
  effective config.

Re-review outcome:

- D2-D7 met.
- No remaining blocker.
- Non-blocking note about answer-composer provenance was addressed by adding a
  mirrored composer-provenance contract to the plan.

## Final Notes

- No implementation code was changed in this stage.
- No live OpenRouter call was made.
- No cloud or paid compute resources were launched, stopped, deleted, resized,
  restarted, or otherwise mutated.
