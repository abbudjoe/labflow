# Optional OpenRouter Inference Adapter

LabFlow AI Studio can run with an optional OpenRouter-backed model planner for local experiments. This does not change the project doctrine: deterministic validators own laboratory truth, and the default runtime remains deterministic.

## Default Behavior

Without configuration, `LabFlowAgentRuntime(model=None)` uses the local `DeterministicFakeModel`. Tests, demos, and CI must continue to pass without network access or model credentials.

Use this default for portfolio demos where reproducibility matters:

```text
LABFLOW_MODEL_PROVIDER=deterministic
```

## OpenRouter Opt-In

Set these variables only for local model experiments:

```text
LABFLOW_MODEL_PROVIDER=openrouter
LABFLOW_OPENROUTER_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_HTTP_REFERER=
OPENROUTER_APP_TITLE=LabFlow AI Studio
OPENROUTER_TIMEOUT_SECONDS=30
OPENROUTER_MAX_RETRIES=1
OPENROUTER_RETRY_BACKOFF_SECONDS=1
OPENROUTER_RETRY_BACKOFF_MULTIPLIER=2
OPENROUTER_RETRY_MAX_BACKOFF_SECONDS=8
OPENROUTER_ENABLE_METADATA=false
LABFLOW_OPENROUTER_FALLBACK_MODELS=
LABFLOW_OPENROUTER_RESPONSE_FORMAT=json_object
LABFLOW_MODEL_EVAL_MAX_CASE_SECONDS=
```

As of June 10, 2026, OpenRouter lists `nvidia/nemotron-3-ultra-550b-a55b:free` as a free NVIDIA Nemotron 3 Ultra endpoint. That provider status is time-sensitive: availability, rate limits, routing behavior, and pricing can change outside this repository.

Do not commit secrets. Keep `OPENROUTER_API_KEY` in your local environment or untracked local env files only.

The eval comparison and ladder scripts load simple `KEY=VALUE` defaults from the repository `.env` file. Already-exported shell variables still win, so unset or override `LABFLOW_OPENROUTER_MODEL` in the shell if a previous run keeps using an older model.

## Safety Contract

The OpenRouter adapter is a planner, not a lab engine.

- `labflow-core` has no LLM or API dependency.
- Model output is parsed as untrusted JSON.
- Invalid JSON or invalid schema falls back to an unsupported/read-only plan.
- If workflow YAML is supplied, the final plan always runs deterministic `validate_batch`.
- `workflow_yaml` and `batch_id` are copied from `AgentRequest`, never from model output.
- The model cannot supply sample IDs, concentrations, wells, standards, blanks, JANUS payloads, or file paths.
- Stage 18.1 allows only the `validate_batch` and `explain_exception_code` tool intents.
- JANUS generation remains governed by deterministic validation, dry-run, approval, and audit policies.
- RAG answers must still cite sources or say the answer is unsupported.

## Provider Diagnostics

OpenRouter failures are recorded as sanitized provider diagnostics, not raw provider payloads. Eval reports include a per-case `plan_diagnostic` object and provider-level `plan_diagnostic_counts`; traces include the same diagnostic under `trace.model_diagnostic`.

Typical diagnostic codes include:

- `openrouter_timeout` for socket/provider timeouts;
- `openrouter_http_error` for HTTP status failures;
- `openrouter_response_missing_choices` and related `openrouter_response_*` codes for malformed completion envelopes;
- `model_plan_json_invalid` for non-JSON model message content;
- `model_plan_schema_invalid` for JSON that does not validate as an `AgentPlan`;
- `model_tool_intent_unsafe` when model-selected tools, modes, or arguments are rejected by the Stage 18.1 safe intent surface.

Diagnostics are intentionally compact. They explain the failure class without storing API keys, request headers, raw prompts, raw model output, or raw provider response bodies. The adapter may store a short redacted body preview, top-level envelope keys, retry count, failover count, elapsed time, HTTP status, and provider error metadata keys. Provider error metadata values are not persisted.

Provider failures are not safety violations. A timeout, HTTP 5xx, missing `choices`, or provider error object can fail a live eval case, but it is reported separately from unsafe LabFlow behavior such as trying to generate a robot artifact for an invalid batch.

## Retry and Failover

The adapter retries only retryable provider or transport failures. It does not retry invalid model-authored `AgentPlan` JSON, schema-invalid output, or unsafe tool intents. Defaults are intentionally bounded:

```text
OPENROUTER_MAX_RETRIES=1
OPENROUTER_RETRY_BACKOFF_SECONDS=1
OPENROUTER_RETRY_BACKOFF_MULTIPLIER=2
OPENROUTER_RETRY_MAX_BACKOFF_SECONDS=8
```

`Retry-After` is honored when present and capped by `OPENROUTER_RETRY_MAX_BACKOFF_SECONDS`.

Failover is off by default. Set `LABFLOW_OPENROUTER_FALLBACK_MODELS` to a comma-separated list of model ids to try only after retry exhaustion on retryable provider failures. Failover is never used to rescue unsafe tool intent, invalid schema, or other model-output contract failures.

`OPENROUTER_ENABLE_METADATA=true` opts into OpenRouter metadata headers. LabFlow stores only sanitized execution metadata such as requested model, final requested model, served model id, attempt count, retry count, failover count, and status codes.

`LABFLOW_OPENROUTER_RESPONSE_FORMAT` supports `json_object`, `json_schema`, and `off`. The default remains `json_object` because it is widely supported across OpenRouter providers.

## Offline Evaluation

Run the deterministic comparison script without credentials from an environment with the LabFlow Python dependencies installed:

```text
python scripts/run_model_eval_comparison.py --limit 3
```

This writes a JSON report under `artifacts/model_eval_comparisons/` and records that the live OpenRouter run was skipped.
The command is an exploratory report smoke: a nonzero `fail_count` is recorded in JSON for review, but does not by itself make the shell command fail.

From a bare system Python, use the same dependency style as the repository Makefile:

```text
uv run --python python3.12 --with pydantic --with pyyaml --with fastapi --with httpx python scripts/run_model_eval_comparison.py --limit 3
```

With credentials, a small live smoke can be run explicitly:

```text
LABFLOW_OPENROUTER_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free \
OPENROUTER_API_KEY=... \
python scripts/run_model_eval_comparison.py --live-openrouter --limit 3 --verbose --openrouter-timeout-seconds 20 --max-case-seconds 45
```

Live model behavior is not a deterministic gate. Treat it as exploratory evidence, not as a replacement for local tests or deterministic evals.

If a provider stalls, the comparison script records that case as an error and continues to the next case. Lower `--openrouter-timeout-seconds` for quicker socket-inactivity feedback. Use `--max-case-seconds` for a hard per-case wall-clock cap on Unix-like systems.

Golden cases that require `validate_batch` are only treated as missing that tool when the harness supplies trusted synthetic workflow YAML. If no fixture is available, the report records the tool requirement as not applicable instead of asking the model to invent validation inputs.

## Laddered Evals

Use the ladder harness to run progressively broader comparison tiers and write one JSON plus Markdown summary:

```text
python scripts/run_model_eval_ladder.py --verbose --max-case-seconds 45
```

Default tiers are:

- `smoke_3`
- `confidence_10`
- `category_batch_readiness`
- `category_guardrails`
- `full_golden`

Run selected tiers with repeated `--tier` flags:

```text
python scripts/run_model_eval_ladder.py --tier smoke_3 --tier category_batch_readiness --verbose
```

Add `--live-openrouter` only for explicit live inference smoke runs.
