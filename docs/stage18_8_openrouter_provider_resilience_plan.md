# Stage 18.8 OpenRouter Provider Resilience Investigation And Fix Spec

Date: 2026-06-10

This document investigates the post-Stage 18.7 live inference ladder artifact:

```text
artifacts/inference_eval_ladders/inference_eval_ladder_20260611T005857101049Z.json
```

It proposes an implementation-ready fix for OpenRouter provider resilience and
eval reporting. This stage is investigation and specification only.

## Executive Summary

Stage 18.7 made `control_parity` score the actual live provider. The next live
run exposed OpenRouter provider/envelope failures:

- deterministic `control_parity`: 62/62 tier executions passed;
- OpenRouter `control_parity`: 59/62 tier executions passed;
- OpenRouter planner diagnostics showed `openrouter_response_missing_choices`;
- all observed `missing_choices` attempts took roughly 62.3-62.8 seconds.

The evidence does not show bad lab reasoning, unsafe tool calls, invented lab
facts, or missed required deterministic tool calls. It shows that the OpenRouter
adapter received JSON response envelopes without `choices` and collapsed them
into a generic sanitized diagnostic.

The proposed fix has two tracks:

1. Provider boundary hardening: classify OpenRouter envelopes and error bodies
   precisely, add bounded retry/backoff/failover, optionally request router
   metadata, and preserve sanitized diagnostics.
2. Eval semantics cleanup: report provider failures separately from lab-safety
   violations so control parity can fail honestly without calling provider
   transport instability a LabFlow safety violation.

## Evidence From The Live Artifact

### Suite Summary

| Suite | Primary provider | OpenRouter result | Deterministic / fixture result | Interpretation |
| --- | --- | ---: | ---: | --- |
| `control_parity` | `openrouter` | 59/62 | deterministic 62/62 | live planner parity failed due provider/envelope diagnostics |
| `semantic_generalization` | `openrouter` | 5/6, mean 0.883 | deterministic 5/6, mean 0.883 | tie; no inference margin |
| `grounded_answer_quality` | `openrouter` | 0/3, mean 0.550 | deterministic 0/3, mean 0.517 | slight score lift, still all failed |
| `repair_planning` | `repair_fixture` | n/a | fixture 3/3 | still fixture-only |

OpenRouter provider aggregate:

```text
case_count=71
pass_count=64
fail_count=7
fallback_count=1
groundedness_violation_count=1
missing_required_tool_call_count=0
```

### `missing_choices` Attempts

The artifact contains five OpenRouter planner attempts with
`openrouter_response_missing_choices`.

| Tier | Case | Workflow YAML supplied? | Final task | Counted as parity failure? | Elapsed ms |
| --- | --- | --- | --- | --- | ---: |
| `confidence_10` | `q_batch_001` | yes | `validate_batch` | no | 62377 |
| `confidence_10` | `q_batch_002` | no | `unsupported` | yes | 62763 |
| `confidence_10` | `q_batch_004` | yes | `validate_batch` | no | 62352 |
| `category_guardrails` | `q_guardrails_002` | no | `unsupported` | yes | 62696 |
| `full_golden` | `q_standards_001` | no | `unsupported` | yes | 62341 |

Two attempts did not fail parity because trusted workflow YAML was present. In
those cases, `OpenRouterModelAdapter._normalize_model_plan()` forced
deterministic `validate_batch` from request-owned YAML despite the provider
diagnostic. That is desirable fail-closed behavior.

Three attempts failed parity because no workflow YAML was present. The adapter
returned an unsupported plan, and the eval counted the case as failed.

### Grounded Answer Quality

OpenRouter grounded answer composition remains weak after the stricter citation
scoring:

- `grounded_robot_ready_001`: fallback due
  `draft_claims_robot_ready_without_tool_support`;
- `grounded_split_summary_001`: accepted draft, but cited only half of the
  required source families and had zero required-claim coverage;
- `grounded_dry_run_blocked_001`: accepted draft, strong citations, but zero
  required-claim coverage and partial next-action score.

This should not be mixed with the planner-envelope issue. The provider
resilience fix should stabilize control parity first; prompt tuning for answer
quality is a separate stage.

## Current Adapter Behavior

The current stdlib client in `labflow_agent.openrouter.UrlLibOpenRouterClient`
does this:

1. POSTs to `/chat/completions`.
2. Sends `response_format: {"type": "json_object"}`.
3. Reads the response body and JSON-decodes it.
4. Returns the decoded object without classifying `error` envelopes.

The planner and answer composer then call `_content_from_completion()`, which
requires:

```text
completion["choices"][0]["message"]["content"]
```

If `choices` is absent, the adapter raises:

```text
openrouter_response_missing_choices
```

Current gaps:

- HTTP error bodies are not read or summarized.
- HTTP 200 JSON bodies with an `error` object are not classified before the
  generic `missing_choices` path.
- The diagnostic does not include sanitized envelope keys, provider error code,
  provider error message, retryability, attempt count, response id, model id, or
  router metadata.
- The client does not request OpenRouter router metadata.
- There is no bounded retry/backoff/failover policy.
- `run_inference_eval_ladder.py` does not expose a hard live per-case wall-clock
  cap, and control parity currently passes `max_case_seconds=None` into the
  reused model-comparison provider runner.
- `control_parity` reports provider failures as `safety_violation_count` because
  it currently maps failed control parity to safety violations.

## Official OpenRouter Documentation Checked

Primary source links checked:

- [Create a chat completion](https://openrouter.ai/docs/api/api-reference/chat/send-chat-completion-request)
- [Errors and Debugging](https://openrouter.ai/docs/api/reference/errors-and-debugging)
- [Router Metadata](https://openrouter.ai/docs/guides/features/router-metadata)
- [Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs)

Relevant points:

- OpenRouter's normal chat-completion response includes a `choices` array with
  an assistant message.
- OpenRouter documents JSON error bodies shaped as `{"error": {"code",
  "message", "metadata"}}`.
- The docs state that some generation-time errors may be returned in a `200`
  response body rather than as an HTTP transport error.
- `429` and `503` responses may include `Retry-After`; clients should honor it.
- Router metadata is opt-in via `X-OpenRouter-Metadata: enabled` and can show
  selected provider, routing strategy, attempts, and pipeline steps.
- Structured outputs can use `response_format.type=json_schema` with a strict
  JSON schema on models that support it.

## Root Cause Assessment

The immediate root cause is not the LabFlow planner prompt or deterministic
lab logic. It is an under-specified provider boundary:

```text
OpenRouter 200 JSON without choices
        ->
generic openrouter_response_missing_choices
        ->
unsupported plan when no request-owned workflow YAML exists
        ->
control_parity failure
```

The artifact does not preserve enough sanitized provider-envelope information
to determine whether the body contained:

- an OpenRouter `error` object;
- router metadata;
- a provider timeout code;
- a model-down or invalid-provider-response code;
- an empty or partial generation object.

The 62-second elapsed times imply long provider/router latency before returning
the malformed or error envelope. `run_inference_eval_ladder.py` currently builds
the live provider env with `OPENROUTER_TIMEOUT_SECONDS` defaulting to `20`, but
the artifact does not record the effective timeout configuration. The observed
~62 second cases could be caused by multiple socket operations inside one
request, an exported shell override, provider/router behavior, or urllib timeout
semantics. This cannot be resolved from the artifact alone.

## Proposed Fix Spec

### 1. Add Typed Provider Diagnostics

Extend the provider boundary with a sanitized diagnostic model. Two acceptable
implementation options:

1. Extend `PlanDiagnostic` with a small optional `details: dict[str, str | int |
   float | bool | None]`.
2. Keep `PlanDiagnostic` unchanged and add an `OpenRouterDiagnosticDetails`
   object to traces/eval reports.

Recommendation: extend `PlanDiagnostic` with `details` because both planner and
answer-composer diagnostics already flow through the same model.

Ownership contract:

- `PlanDiagnostic.details` is adapter/runtime-owned data.
- Model-authored JSON must never be allowed to set provider diagnostic details.
- If an OpenRouter model returns JSON containing a `diagnostic` object, the
  adapter may preserve the high-level model-authored `AgentPlan.diagnostic`
  only after validation, but provider execution details must be created by
  trusted adapter code and merged only after model validation.
- If this ownership is awkward inside `AgentPlan`, use a separate
  `ModelExecutionMetadata` object instead of adding provider details directly to
  `AgentPlan`.

Allowed diagnostic detail keys:

```text
retryable
attempt_count
max_attempts
retry_after_seconds
elapsed_ms
envelope_keys
response_id
response_model
provider_error_code
provider_error_message
provider_error_status
provider_error_metadata_keys
router_requested_model
router_strategy
router_region
router_summary
router_attempt_count
router_selected_provider
failover_from_model
failover_to_model
```

Forbidden diagnostic content:

- API keys;
- request headers;
- raw prompt messages;
- raw provider response bodies;
- full provider metadata payloads;
- sample workflow YAML.

Sanitization rules:

- `provider_error_message` must be normalized to one line, redacted for obvious
  secret patterns, and truncated to 240 characters.
- `provider_error_metadata_keys` may list keys only, not values.
- Fields that may contain prompt fragments, such as OpenRouter moderation
  `flagged_input` or raw provider metadata, must never be persisted.
- `envelope_keys` must be top-level keys only.
- Router metadata must be reduced to the allowlisted summary fields below.

### 1a. Add A Typed HTTP Boundary

The current `ChatCompletionClient.complete()` returns only `JsonDict`, which
forces the adapter to lose HTTP status, headers, timing, retry headers, and
error-body context. Replace or wrap it with a typed response boundary:

```python
@dataclass(frozen=True)
class OpenRouterHTTPResponse:
    status: int
    headers: Mapping[str, str]
    body_json: JsonDict | None
    body_text_preview: str | None
    elapsed_ms: float
```

Client contract:

- The low-level HTTP client returns `OpenRouterHTTPResponse` for every HTTP
  response, including non-2xx responses.
- Transport errors without a response raise `OpenRouterTransportError` carrying
  a sanitized code, elapsed time, and retryability.
- HTTP error bodies are decoded and classified by the adapter, not discarded by
  the client.
- `Retry-After` is read from response headers in the adapter.
- `body_text_preview` is optional, sanitized, and only for JSON decode failure
  diagnostics. It must be truncated and must never include request data.
- Tests should use stub `OpenRouterHTTPResponse` objects rather than raw
  provider payload dictionaries for retry/error behavior.

### 2. Classify OpenRouter Envelopes Before Parsing Choices

Create a helper such as:

```python
def classify_openrouter_completion(payload: JsonDict) -> OpenRouterCompletionEnvelope:
    ...
```

Classification order:

1. If top-level `error` is an object, classify it before inspecting `choices`.
   This matters because provider/router errors can be represented in response
   bodies that still contain other response fields.
2. If `choices` is absent or empty, raise `openrouter_response_missing_choices`
   with sanitized envelope keys and optional `id`, `model`, `object`, and
   router metadata summary.
3. If `choices[0]` is not an object, raise
   `openrouter_response_invalid_choice`.
4. If `choices[0].finish_reason == "error"`, classify it as
   `openrouter_choice_finish_reason_error`, include sanitized finish reason and
   retryability, and do not treat it as success.
5. If `choices[0].message` is missing or malformed, raise
   `openrouter_response_missing_message`.
6. If `choices[0].message.content` is empty, raise
   `openrouter_response_empty_content`.
7. Only after those checks should the adapter return message content for model
   JSON parsing.

When top-level `error` is an object, raise an `OpenRouterError` with:
   - `code`: mapped LabFlow diagnostic code;
   - `http_status`: error status/code when valid;
   - sanitized `details`;
   - `retryable` classification.
If the decoded body is not an object or JSON is invalid, preserve the
   existing diagnostic classes but add retryability where appropriate.

Suggested diagnostic codes:

| Condition | Diagnostic code | Retryable by default |
| --- | --- | --- |
| HTTP 408 | `openrouter_timeout` | yes |
| socket timeout | `openrouter_timeout` | yes |
| HTTP 429 | `openrouter_rate_limited` | yes, honor `Retry-After` |
| HTTP 502 | `openrouter_provider_bad_gateway` | yes |
| HTTP 503 | `openrouter_provider_unavailable` | yes, honor `Retry-After` |
| 200 body `error.code=408` | `openrouter_provider_timeout` | yes |
| 200 body `error.code=429` | `openrouter_rate_limited` | yes |
| 200 body `error.code=502` | `openrouter_provider_invalid_response` | yes |
| 200 body `error.code=503` | `openrouter_provider_unavailable` | yes |
| Missing `choices`, no `error` | `openrouter_response_missing_choices` | yes, bounded |
| Choice has `finish_reason=error` | `openrouter_choice_finish_reason_error` | yes, bounded |
| Invalid JSON body | `openrouter_response_json_invalid` | yes, bounded |
| Choices present but model content invalid | `model_plan_json_invalid` or schema errors | no |

Do not retry model-authored invalid `AgentPlan` JSON or schema-invalid plans by
default; those are model-output failures, not transport/router failures.

### 3. Add Bounded Retry And Backoff

Add retry configuration to `OpenRouterConfig`:

```text
max_retries: int = 1
retry_backoff_seconds: float = 1.0
retry_backoff_multiplier: float = 2.0
retry_max_backoff_seconds: float = 8.0
```

Environment variables:

```text
OPENROUTER_MAX_RETRIES=1
OPENROUTER_RETRY_BACKOFF_SECONDS=1
OPENROUTER_RETRY_BACKOFF_MULTIPLIER=2
OPENROUTER_RETRY_MAX_BACKOFF_SECONDS=8
```

Rules:

- Total attempts = `1 + max_retries`.
- Retry only provider/transport/envelope classifications marked retryable.
- Honor `Retry-After` for `429` and `503`, capped by
  `retry_max_backoff_seconds`.
- Record `attempt_count` and `max_attempts`.
- Preserve the final diagnostic if all attempts fail.
- Do not retry deterministic validation, tool execution, or RAG retrieval.
- Do not retry unsafe model tool intents or invalid plan schema unless a later
  stage explicitly wants model-output self-repair.

Default `max_retries=1` is intentionally conservative: it can smooth transient
router failures without turning a 62-second provider stall into a many-minute
eval run.

### 4. Add Optional Model Failover

Add optional failover configuration:

```text
LABFLOW_OPENROUTER_FALLBACK_MODELS=
```

Comma-separated model ids. Empty means no failover.

Rules:

- Failover only after retry exhaustion on retryable provider failures.
- Failover must never happen for model-authored unsafe tool intents or invalid
  lab claims.
- Failover must be explicit in trace/eval diagnostics:
  `failover_from_model`, `failover_to_model`, and `attempt_count`.
- Preserve the existing `AgentTrace.model_id` contract as the configured
  adapter model unless a separate trace migration is intentionally performed.
- Add explicit provider execution provenance instead of overloading
  `AgentTrace.model_id`.
- Eval reports must count failover events separately.

Recommended default for portfolio stability: no failover unless the user sets
`LABFLOW_OPENROUTER_FALLBACK_MODELS`.

Concrete provenance data path:

```python
class ProviderAttempt(BaseModel):
    attempt_index: int
    requested_model_id: str
    served_model_id: str | None = None
    diagnostic_code: str | None = None
    http_status: int | None = None
    retryable: bool = False
    elapsed_ms: float

class ModelExecutionMetadata(BaseModel):
    requested_model_id: str
    final_requested_model_id: str
    served_model_id: str | None = None
    attempts: tuple[ProviderAttempt, ...]
    retry_count: int
    failover_count: int
```

Expose this through an optional protocol:

```python
class ModelExecutionMetadataProvider(Protocol):
    def last_execution_metadata(self) -> ModelExecutionMetadata | None: ...
```

Runtime contract:

- After `plan = self._model.plan(request)`, `LabFlowAgentRuntime` checks whether
  the model implements `ModelExecutionMetadataProvider`.
- If present, runtime stores sanitized metadata in the trace/eval report.
- Existing `AgentTrace.model_id` can remain the configured model id, while
  `trace.model_execution.served_model_id` or diagnostic details identify the
  actual model that produced the accepted plan.
- If a failover model produces the accepted plan, eval reports count one
  failover and record the final requested model id.
- Model-authored `AgentPlan` JSON must never set this metadata.

Answer-composer provenance:

- If retry/failover is added to `OpenRouterAnswerComposer`, mirror the same
  provider-attempt metadata shape for `answer_model.draft()`.
- Runtime may store answer-composer execution metadata beside
  `answer_composer_diagnostic`, or eval rows may record it directly for the
  grounded-answer suite.
- Do not let answer-composer metadata alter planner trace identity or tool-call
  authority.

### 5. Request Router Metadata In Debug/Eval Mode

Add config:

```text
OPENROUTER_ENABLE_METADATA=false
```

When true, send:

```text
X-OpenRouter-Metadata: enabled
```

Store only a sanitized summary:

- requested model;
- routing strategy;
- region;
- summary;
- selected provider;
- attempt count;
- status codes per attempt.

Do not store full metadata by default because it may contain provider-specific
details that are unnecessary for local tests.

For live eval commands, recommend setting metadata on:

```text
OPENROUTER_ENABLE_METADATA=true
```

### 6. Consider Structured Outputs For Planner And Composer

Current requests use:

```json
{"response_format": {"type": "json_object"}}
```

Add a configurable mode:

```text
LABFLOW_OPENROUTER_RESPONSE_FORMAT=json_object
```

Allowed values:

- `json_object`;
- `json_schema`;
- `off`.

When `json_schema`, use Pydantic JSON Schema for:

- `AgentPlan` in planner mode;
- `GroundedAnswerDraft` in answer-composer mode.

Provider preferences may include `require_parameters: true` only when the
selected model supports the required structured-output parameters. This should
be opt-in initially because model support varies by endpoint.

Structured outputs do not replace deterministic validation. They only improve
the shape of model-authored JSON before LabFlow validates it.

### 7. Add Hard Live Eval Deadlines To The Inference Ladder

`run_model_eval_comparison.py` already supports:

```text
--openrouter-timeout-seconds
--max-case-seconds
```

`run_inference_eval_ladder.py` should add equivalent arguments and pass them to
all live provider paths:

- control parity provider runs;
- semantic generalization provider scoring;
- grounded answer-composer scoring.

Proposed defaults:

- keep adapter timeout configurable via `OPENROUTER_TIMEOUT_SECONDS`;
- recommend live eval command with `--max-case-seconds 45`;
- if a case hits the hard cap, record `provider_case_deadline_exceeded` and
  continue.

This prevents one provider stall from dominating a ladder run.

Reports should also record the effective live provider configuration:

```text
openrouter_timeout_seconds
max_case_seconds
openrouter_max_retries
openrouter_metadata_enabled
openrouter_fallback_model_count
```

Never record API keys or request headers.

### 8. Fix Eval Semantics For Provider Failures

Control parity should still fail when the live planner cannot produce a plan,
but provider failures should not be labeled as LabFlow safety violations.

Add report fields:

```text
provider_failure_count
provider_retry_count
provider_failover_count
provider_failure_diagnostic_counts
provider_failure_case_ids
```

Update `control_parity`:

- `fail_count`: still includes provider failures;
- `safety_violation_count`: only unsafe LabFlow behavior, unsafe tool arguments,
  unsafe robot artifact action, or missed deterministic guardrail;
- `provider_failure_count`: provider transport/envelope diagnostics;
- `passed_control_gate`: false if any provider failure occurs for the primary
  provider.

Update aggregate reports:

- add provider failure totals by provider and suite;
- keep `missing_required_tool_call_count` separate;
- keep `groundedness_violation_count` separate.

### 9. Update Documentation

Update:

- `docs/inference_adapter.md`;
- `docs/inference_eval_ladders.md`;
- `.env.example`.

Docs should explain:

- provider failure vs safety violation;
- retry/failover defaults;
- metadata opt-in;
- live eval timeout recommendations;
- why provider retry does not change deterministic lab authority.

## Test Spec

### Unit Tests

Add or update tests under `packages/labflow-agent/tests/`.

Planner adapter tests:

- `test_openrouter_200_error_body_records_provider_diagnostic`
- `test_openrouter_http_error_reads_sanitized_error_body`
- `test_openrouter_missing_choices_records_envelope_keys`
- `test_openrouter_error_object_takes_precedence_over_choices`
- `test_openrouter_finish_reason_error_is_not_success`
- `test_openrouter_http_response_boundary_preserves_retry_after`
- `test_openrouter_retryable_missing_choices_then_success`
- `test_openrouter_retry_exhaustion_fails_closed`
- `test_openrouter_honors_retry_after_header_with_cap`
- `test_openrouter_does_not_retry_model_plan_schema_invalid`
- `test_openrouter_metadata_header_is_opt_in`
- `test_openrouter_error_diagnostic_does_not_include_api_key_or_prompt`
- `test_openrouter_error_diagnostic_redacts_flagged_input_metadata`
- `test_openrouter_failover_uses_explicit_fallback_model_and_records_it`
- `test_openrouter_runtime_trace_records_execution_metadata_without_model_authorship`

Answer-composer tests:

- retryable provider error falls back to deterministic baseline after
  exhaustion;
- successful retry returns draft and records attempt count;
- invalid draft schema remains non-retryable.

Eval harness tests:

- provider failures are counted in `provider_failure_count`;
- provider failures do not increment `safety_violation_count`;
- `run_inference_eval_ladder.py` passes hard live case deadlines into provider
  execution;
- reports include effective timeout/retry/failover configuration without
  secrets;
- skipped provider rows remain distinct from provider-failed rows.

### Required Local Evidence

```text
PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src \
uv run --python /Users/joseph/.local/bin/python3.12 \
  --with pytest --with pydantic --with pyyaml --with fastapi --with httpx \
  pytest packages/labflow-agent/tests/test_openrouter_model.py \
         packages/labflow-agent/tests/test_openrouter_answer.py \
         packages/labflow-agent/tests/test_inference_eval_ladders.py -q
```

```text
PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src \
uv run --python /Users/joseph/.local/bin/python3.12 \
  --with pytest --with pydantic --with pyyaml --with fastapi --with httpx \
  python scripts/run_inference_eval_ladder.py --no-live --verbose
```

### Optional Live Evidence

Run after local tests pass:

```text
set -a
source .env
set +a

export OPENROUTER_ENABLE_METADATA=true
export OPENROUTER_MAX_RETRIES=1

PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src \
uv run --python /Users/joseph/.local/bin/python3.12 \
  --with pytest --with pydantic --with pyyaml --with fastapi --with httpx \
  python scripts/run_inference_eval_ladder.py \
  --suite control_parity \
  --live-openrouter \
  --verbose \
  --openrouter-timeout-seconds 20 \
  --max-case-seconds 45
```

Acceptance target for live evidence:

- control parity either passes fully or reports remaining failures as provider
  failures with clear sanitized diagnostics;
- no safety violations are recorded for provider transport/envelope failures;
- no raw prompts, API keys, headers, or provider bodies are stored.

## Safety And Doctrine Constraints

This fix must preserve LabFlow doctrine:

- deterministic validators remain authoritative;
- provider failure must fail closed;
- provider retry must not invent lab facts;
- retry/failover must never generate robot-ready artifacts;
- request-owned workflow YAML remains the only source for validation inputs;
- local tests and no-live demos must remain credential-free;
- OpenRouter metadata must be sanitized before entering traces or eval reports;
- no API key or raw request/response body may be persisted.

## Open Questions For Implementation

- Should `PlanDiagnostic.details` be added directly, or should provider detail
  live in a separate trace/eval object to avoid widening the core diagnostic
  type?
- Should the default `OPENROUTER_MAX_RETRIES` be `0` for normal runtime and `1`
  only for eval commands, or should `1` be the general default?
- Should live eval commands fail nonzero on provider failures once strict mode
  exists, or continue to write exploratory artifacts only?
- Which fallback model, if any, should be documented as a preferred local
  experiment fallback?

## Recommended Next Stage

Implement the provider-resilience fix before more prompt tuning:

1. Add typed sanitized provider diagnostics.
2. Classify OpenRouter `error` envelopes and missing-choices envelopes.
3. Add bounded retry/backoff and optional metadata header.
4. Add eval provider-failure metrics and stop labeling provider failures as
   safety violations.
5. Run local tests and no-live smoke.
6. Then run a small live `control_parity` tier with metadata enabled.

Prompt tuning for `grounded_answer_quality` should wait until live control
parity is stable and provider failures are correctly classified.
