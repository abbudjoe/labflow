# Stage 18.1 Model Eval Ladder Assembly Review

Review date: 2026-06-10

Stage: `18.1_model_eval_ladder_harness`

Authoritative plan: `.codex_build/stage18_1_model_eval_ladder_plan.md`

Status: `successful`

## Target Contract

Add `scripts/run_model_eval_ladder.py` to run progressively broader model-comparison tiers, reuse the existing comparison harness semantics, and write JSON plus Markdown ladder summaries. Live OpenRouter remains optional, local tests must not require credentials, and secrets must not be printed or persisted.

## Extracted DoD Checklist

| DoD item | Status | Evidence |
| --- | --- | --- |
| D1: Document ladder plan | met | `.codex_build/stage18_1_model_eval_ladder_plan.md` created. |
| D2: Add ladder runner script | met | `scripts/run_model_eval_ladder.py` added. |
| D3: Include default tiers smoke_3, confidence_10, batch_readiness, guardrails, full_golden | met | `DEFAULT_TIERS` defines all required tiers. |
| D4: Support repeated `--tier` and `--skip-full` | met | CLI supports `--tier` append and `--skip-full`. |
| D5: Pass through live/verbose/timeout/case cap options | met | CLI passes `--live-openrouter`, `--verbose`, `--openrouter-timeout-seconds`, and `--max-case-seconds`. |
| D6: Reuse comparison harness semantics | met | Runner imports `run_model_eval_comparison` and calls `_run_provider`. |
| D7: Write JSON and Markdown ladder reports | met | Smoke wrote JSON and Markdown under `artifacts/model_eval_ladders`. |
| D8: Do not expose API keys | met | Live key is only passed in env dict when requested; reports contain no key values. |
| D9: Offline ladder smoke passes | met | Two-tier offline ladder smoke passed. |
| D10: Static/test gates pass | met | `make test`, `make lint`, `make type-python`, and script ruff passed. |
| D11: Subagent spec-conformance review clean and closed | met | Reviewer found no blocking findings; reviewer closed. |

## Planned Evidence Commands

```text
uv run --python /Users/joseph/.local/bin/python3.12 --with pydantic --with pyyaml --with fastapi --with httpx python scripts/run_model_eval_ladder.py --tier smoke_3 --tier category_batch_readiness --verbose --max-case-seconds 5
uv run --python /Users/joseph/.local/bin/python3.12 --with ruff python -m ruff check scripts/run_model_eval_ladder.py
make test
make lint
make type-python
```

## Changed Files

- `.codex_build/stage18_1_model_eval_ladder_plan.md`
- `docs/stage18_1_model_eval_ladder_assembly_review.md`
- `docs/inference_adapter.md`
- `scripts/run_model_eval_ladder.py`

## Evidence

```text
uv run --python /Users/joseph/.local/bin/python3.12 --with pydantic --with pyyaml --with fastapi --with httpx python scripts/run_model_eval_ladder.py --tier smoke_3 --tier category_batch_readiness --verbose --max-case-seconds 5
# deterministic aggregate: 7 pass, 0 fail
# wrote artifacts/model_eval_ladders/model_eval_ladder_20260610T155919865466Z.json
# wrote artifacts/model_eval_ladders/model_eval_ladder_20260610T155919865466Z.md

uv run --python /Users/joseph/.local/bin/python3.12 --with ruff python -m ruff check scripts/run_model_eval_ladder.py
# All checks passed

uv run --python /Users/joseph/.local/bin/python3.12 --with pydantic --with pyyaml --with fastapi --with httpx python scripts/run_model_eval_ladder.py --tier smoke_3 --max-case-seconds 5 && uv run --python /Users/joseph/.local/bin/python3.12 --with pydantic --with pyyaml --with fastapi --with httpx python scripts/run_model_eval_ladder.py --tier smoke_3 --max-case-seconds 5
# Wrote distinct microsecond-stamped ladder reports without filename collision.

make test
# 139 passed, 1 warning

make lint
# All checks passed

make type-python
# Success: no issues found in 80 source files
```

## Review Findings

Reviewer: `019eb240-dce4-7592-bbf1-118a382da750`

Final review outcome:

- No blocking spec-conformance findings.
- D1-D10 classified as met.
- D11 was partial only because this ledger still said pending; fixed after review and reviewer closed.

Non-blocking risks recorded:

- Ladder runner currently reuses private helpers from `run_model_eval_comparison.py`; future cleanup should expose a public comparison helper.
- Live OpenRouter env wiring is duplicated between the comparison and ladder scripts; future cleanup should centralize it.
- Dedicated unit tests for tier selection/report shape would make regressions cheaper to catch.
- Aggregate counts are tier executions and may double-count overlapping golden cases; report now states this explicitly.

Post-review smoke:

```text
uv run --python /Users/joseph/.local/bin/python3.12 --with pydantic --with pyyaml --with fastapi --with httpx python scripts/run_model_eval_ladder.py --tier smoke_3 --tier category_batch_readiness --verbose --max-case-seconds 5
# deterministic aggregate: 7 pass, 0 fail
# wrote artifacts/model_eval_ladders/model_eval_ladder_20260610T155919865466Z.json
# wrote artifacts/model_eval_ladders/model_eval_ladder_20260610T155919865466Z.md

uv run --python /Users/joseph/.local/bin/python3.12 --with ruff python -m ruff check scripts/run_model_eval_ladder.py
# All checks passed

make test
# 139 passed, 1 warning

make lint
# All checks passed

make type-python
# Success: no issues found in 80 source files
```

Outcome: successful.
