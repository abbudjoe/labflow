# Stage 18.1 OpenRouter Adapter Implementation Assembly Review

Review date: 2026-06-10

Stage: `18.1_optional_openrouter_inference_adapter`

Authoritative plan: `.codex_build/stage18_1_openrouter_adapter_plan.md`

Status: `successful`

## Target Contract

Implement an optional OpenRouter model adapter for `labflow-agent` without changing LabFlow's deterministic safety model. The deterministic fake planner remains the default, normal tests require no network or credentials, model output is treated as untrusted intent, and deterministic validators remain authoritative for workflow truth and JANUS safety.

## Extracted DoD Checklist

| DoD item | Status | Evidence |
| --- | --- | --- |
| D1: Use assembly for implementation review | met | This implementation ledger was created before code edits. |
| D2: Preserve deterministic default | met | `model_from_env({})` and runtime default tests pass; `make test` passed. |
| D3: Keep `labflow-core` LLM/API-free | met | No `packages/labflow-core` implementation files changed. |
| D4: Add explicit OpenRouter env/config surface | met | `model_factory.py`, `OpenRouterConfig`, `.env.example`, and docs define provider/model/base URL/app metadata env vars. |
| D5: Add `OpenRouterModelAdapter` behind `ModelAdapter` | met | `openrouter.py` implements `plan(request) -> AgentPlan` and metadata. |
| D6: Use env-selected runtime construction when `model=None` | met | `runtime.py` now uses `model_from_env()` when no model is injected; factory/runtime tests pass. |
| D7: Validate model JSON into `AgentPlan` with safe fallback | met | `OpenRouterModelAdapter.plan` validates JSON/Pydantic and malformed JSON test passes. |
| D8: Enforce workflow-YAML validation invariant after model output | met | Normalizer forces request-owned `validate_batch`; omission/override tests pass. |
| D9: Bind tool intents from trusted request/context only | met | Binder now requires model intent arguments to be exactly `{}` and copies diagnostic/workflow arguments from `AgentRequest`; tests pass. |
| D10: Reject unsafe modes, file-path tools, JANUS/state-changing intents, and invented arguments | met | Unsafe mode, file-path tool, mixed unsafe intent, arbitrary argument, nested argument, and model-supplied exception-code tests pass. |
| D11: Do not log or expose API keys/secrets | met | Config errors avoid echoing values; `OpenRouterConfig(api_key=...)` repr and metadata repr tests verify key is not exposed. |
| D12: Add optional eval comparison script that skips live OpenRouter without credentials | met | `uv run ... python scripts/run_model_eval_comparison.py --limit 2` wrote a report with OpenRouter skipped. |
| D13: Document inference adapter setup and safety boundaries | met | `docs/inference_adapter.md` added. |
| D14: Update `.env.example` with empty placeholders only | met | OpenRouter and API env placeholders are empty; defaults are comments only. |
| D15: Run relevant offline tests/lint/type gates | met | `make test`, `make lint`, `make type-python`, script smoke, and script ruff passed. |
| D16: Subagent spec-conformance review clean and closed | met | Third subagent review found no remaining blockers; clean reviewer closed. |

## Evidence Commands

```text
make test
make lint
make type-python
uv run --python /Users/joseph/.local/bin/python3.12 --with pydantic --with pyyaml --with fastapi --with httpx python scripts/run_model_eval_comparison.py --limit 2
uv run --python /Users/joseph/.local/bin/python3.12 --with ruff python -m ruff check scripts/run_model_eval_comparison.py
```

## Changed Files

- `.env.example`
- `docs/inference_adapter.md`
- `docs/stage18_1_openrouter_implementation_assembly_review.md`
- `packages/labflow-agent/src/labflow_agent/__init__.py`
- `packages/labflow-agent/src/labflow_agent/model_factory.py`
- `packages/labflow-agent/src/labflow_agent/openrouter.py`
- `packages/labflow-agent/src/labflow_agent/runtime.py`
- `packages/labflow-agent/tests/test_model_factory.py`
- `packages/labflow-agent/tests/test_openrouter_model.py`
- `scripts/run_model_eval_comparison.py`

## Evidence

```text
make test
# 135 passed, 1 warning

make lint
# All checks passed

make type-python
# Success: no issues found in 80 source files

uv run --python /Users/joseph/.local/bin/python3.12 --with pydantic --with pyyaml --with fastapi --with httpx python scripts/run_model_eval_comparison.py --limit 2
# Wrote /Users/joseph/labflow/artifacts/model_eval_comparisons/model_eval_comparison_20260610T022627Z.json

uv run --python /Users/joseph/.local/bin/python3.12 --with ruff python -m ruff check scripts/run_model_eval_comparison.py
# All checks passed
```

## Review Findings

First subagent reviewer: `019eaf53-67e8-75d2-9dcb-0f9549cfe624`

Valid findings addressed:

1. Model-supplied arguments were being dropped instead of rejected. Fixed by requiring `ToolCallPlan.arguments == {}` for all Stage 18.1 model-suggested tool intents before trusted argument binding. Added regression tests for model-supplied `exception_code`, arbitrary keys, nested arguments, and mixed safe/unsafe intents.
2. `OpenRouterConfig` repr exposed `api_key`. Fixed with `field(repr=False)` and a direct regression test.
3. `.env.example` had non-empty defaults despite the empty-placeholder requirement. Fixed by making env values empty and moving defaults into comments.
4. Comparison script success semantics were ambiguous when `fail_count` was nonzero. Fixed by adding report metadata that the command is an exploratory report smoke and documenting that nonzero `fail_count` is report evidence, not shell failure.

Second subagent reviewer: `019eaf56-7b3a-7cf2-9968-d1093b6daa66`

Valid second-pass finding addressed:

1. The workflow-YAML branch forced request-owned validation before explicitly checking invalid model tool intents. Fixed by checking model tool-call shape before the forced validation return. Invalid model tool arguments, unsafe modes, or disallowed tools now produce an explicit rejection rationale while the final plan still satisfies the required `VALIDATE_BATCH` invariant. The workflow override regression was updated to verify the rejection is explicit.

Third subagent reviewer: `019eaf58-bc0d-7aa3-b1c6-98ab172a4564`

Final review outcome:

- No remaining blockers.
- D1-D16 classified as met.
- Reviewer independently confirmed empty model arguments, request-owned workflow validation, secret-safe config repr, and empty `.env.example` placeholders.

Post-review smoke:

```text
make test
# 135 passed, 1 warning

make lint
# All checks passed

make type-python
# Success: no issues found in 80 source files

uv run --python /Users/joseph/.local/bin/python3.12 --with pydantic --with pyyaml --with fastapi --with httpx python scripts/run_model_eval_comparison.py --limit 2
# Wrote /Users/joseph/labflow/artifacts/model_eval_comparisons/model_eval_comparison_20260610T022627Z.json
```

Outcome: successful.
