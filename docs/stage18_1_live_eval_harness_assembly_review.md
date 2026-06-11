# Stage 18.1 Live Eval Harness Assembly Review

Review date: 2026-06-10

Stage: `18.1_live_eval_harness_cleanup`

Authoritative plan: `.codex_build/stage18_1_live_eval_harness_plan.md`

Status: `successful`

## Target Contract

Improve the optional live model comparison harness so it fairly evaluates required tool calls only when deterministic inputs are supplied, normalizes OpenRouter retrieval queries to the original user question, and supports a hard per-case wall-clock cap for live smoke runs. This must preserve deterministic defaults, keep model output untrusted, avoid required live API calls, and avoid exposing secrets.

## Extracted DoD Checklist

| DoD item | Status | Evidence |
| --- | --- | --- |
| D1: Document plan before implementation | met | `.codex_build/stage18_1_live_eval_harness_plan.md` created. |
| D2: Assembly plan review completed | met | Plan reviewer found two blockers; both were fixed before implementation. |
| D3: Fair required-tool evaluation | met | Offline comparison fixture-backs available validation cases and `--limit 10` reports 10 pass, 0 fail. |
| D4: Use existing workflow fixtures only | met | Fixture map uses existing files in `examples/workflows`. |
| D5: Record not-applicable required tools when fixture input is unavailable | met | Report includes `not_applicable_required_tool_calls`; non-request-backed tools are not applicable unless a safe fixture is added. |
| D6: Normalize OpenRouter retrieval query to original question | met | `OpenRouterModelAdapter` normalizes retrieval query; unit test added. |
| D7: Add hard per-case wall-clock cap | met | `--max-case-seconds` added with SIGALRM guard and offline smoke passed. |
| D8: Preserve deterministic defaults and lab safety boundaries | met | No `labflow-core` changes; deterministic default tests pass. |
| D9: Do not print, log, report, or persist API key | met | Script passes key only through env dict and reports no secret values. |
| D10: Update docs/env placeholders | met | `docs/inference_adapter.md` and `.env.example` updated. |
| D11: Offline tests/static gates pass | met | `make test`, `make lint`, `make type-python`, script smoke, and script ruff passed. |
| D12: Implementation subagent review clean and closed | met | Second implementation review found no remaining blockers; reviewer closed. |

## Planned Evidence Commands

```text
make test
make lint
make type-python
uv run --python /Users/joseph/.local/bin/python3.12 --with pydantic --with pyyaml --with fastapi --with httpx python scripts/run_model_eval_comparison.py --limit 3 --verbose --max-case-seconds 5
uv run --python /Users/joseph/.local/bin/python3.12 --with ruff python -m ruff check scripts/run_model_eval_comparison.py
```

## Changed Files

- `.codex_build/stage18_1_live_eval_harness_plan.md`
- `docs/stage18_1_live_eval_harness_assembly_review.md`
- `.env.example`
- `docs/inference_adapter.md`
- `packages/labflow-agent/src/labflow_agent/openrouter.py`
- `packages/labflow-agent/tests/test_openrouter_model.py`
- `scripts/run_model_eval_comparison.py`

## Evidence

```text
make test
# 139 passed, 1 warning

make lint
# All checks passed

make type-python
# Success: no issues found in 80 source files

uv run --python /Users/joseph/.local/bin/python3.12 --with pydantic --with pyyaml --with fastapi --with httpx python scripts/run_model_eval_comparison.py --limit 3 --verbose --max-case-seconds 5
# deterministic: pass=3, fail=0; wrote artifacts/model_eval_comparisons/model_eval_comparison_20260610T151048Z.json

uv run --python /Users/joseph/.local/bin/python3.12 --with ruff python -m ruff check scripts/run_model_eval_comparison.py
# All checks passed

uv run --python /Users/joseph/.local/bin/python3.12 --with pydantic --with pyyaml --with fastapi --with httpx python scripts/run_model_eval_comparison.py --limit 10 --verbose --max-case-seconds 5
# deterministic: pass=10, fail=0; non-fixtured required tools recorded as not applicable; wrote artifacts/model_eval_comparisons/model_eval_comparison_20260610T151522Z.json

uv run --python /Users/joseph/.local/bin/python3.12 --with pydantic --with pyyaml --with fastapi --with httpx python - <<'PY'
# Imported script and verified _case_deadline(0.1) raises TimeoutError.
PY
# TimeoutError Case exceeded --max-case-seconds=0.1.
```

## Plan Review Findings

Plan reviewer: `019eb213-cb34-7032-8db2-38cad3dfe729`

Valid findings fixed before implementation:

1. Corrected `q_batch_003` fixture mapping to `examples/workflows/valid_dna_normalization.workflow.yaml` with batch ID `DNA_NORM_BATCH_001`.
2. Reworded the API-key boundary from "do not read" to "do not print, log, report, or persist" so optional live smoke remains possible without exposing the key.

## Implementation Review Findings

Implementation reviewer: `019eb216-b1bd-7a60-a079-efa8e568df44`

Valid findings fixed:

1. Required-tool applicability only treated `validate_batch` without workflow YAML as not applicable, so broader required tools such as `process_quantification` and `generate_normalization_plan` were unfairly counted as missing without safe deterministic inputs. Fixed by making only explicitly request-backed tools applicable; other required tools are reported as not applicable until safe fixtures are added. Verified with `--limit 10`: 10 pass, 0 fail.
2. Nested SIGALRM restoration could extend a previous timer. Fixed by subtracting elapsed time before restoring the previous timer.

Second implementation reviewer: `019eb219-1aab-7fa2-85dc-f5d26b27815a`

Final review outcome:

- No remaining blockers.
- D1-D12 classified as met.
- Reviewer independently verified `--limit 10` reports 10 pass, 0 fail, and the formerly unfair required tools are recorded as not applicable.

Post-review smoke:

```text
make test
# 139 passed, 1 warning

make lint
# All checks passed

make type-python
# Success: no issues found in 80 source files

uv run --python /Users/joseph/.local/bin/python3.12 --with pydantic --with pyyaml --with fastapi --with httpx python scripts/run_model_eval_comparison.py --limit 10 --verbose --max-case-seconds 5
# deterministic: pass=10, fail=0; wrote artifacts/model_eval_comparisons/model_eval_comparison_20260610T151522Z.json

uv run --python /Users/joseph/.local/bin/python3.12 --with ruff python -m ruff check scripts/run_model_eval_comparison.py
# All checks passed
```

Outcome: successful.
