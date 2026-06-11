# Stage 18.7 Eval Infrastructure Cleanup Assembly Review

Status: successful

Authoritative scope:

- `.codex_build/stage18_7_eval_infrastructure_cleanup_scope.md`

## Extracted DoD Checklist

| ID | DoD Item | Status | Evidence |
| --- | --- | --- | --- |
| D1 | Assembly ledger exists before code edits and records scope, evidence, review, and final status. | met | This ledger was created before code edits. |
| D2 | `control_parity` evaluates provider runs by provider and no longer reports live provider metadata without provider scores. | met | `scripts/run_inference_eval_ladder.py`; `test_control_parity_scores_non_skipped_provider`; no-live artifact `inference_eval_ladder_20260611T002744335564Z.json`. |
| D3 | Inference ladder reports include provider-aware aggregate metrics and a primary provider under test. | met | Report now includes `planner_primary_provider_under_test`, suite-level `primary_provider_under_test`, and `aggregate_by_provider`; covered by tests and no-live artifact. |
| D4 | Suite-level pass/fail summaries no longer hide live provider failures behind baseline-only counts. | met | `test_suite_summary_uses_live_provider_as_primary`; semantic/grounded summaries use the suite primary provider. |
| D5 | Grounded-answer citation alignment uses composer-cited source ids/tool ids where available and penalizes wrong accepted citations. | met | `test_grounded_answer_quality_penalizes_wrong_accepted_source_citation`; `test_tool_evidence_recall_requires_cited_fact_terms`. |
| D6 | Documentation explains provider-aware control parity and aggregate interpretation. | met | `docs/inference_eval_ladders.md` updated with planner-level vs suite-level primary provider and provider aggregate interpretation. |
| D7 | Relevant tests and no-live smoke pass without OpenRouter credentials or cloud resources. | met | `pytest packages/labflow-agent/tests/test_inference_eval_ladders.py -q` passed 12 tests; no-live runner wrote `artifacts/inference_eval_ladders/inference_eval_ladder_20260611T002744335564Z.json`. |
| D8 | Subagent spec-conformance review is clean or valid findings are addressed. | met | Subagent `019eb410-b99a-7341-8b3e-32fdc48b8d31` reviewed twice; implementation findings were addressed; final re-review found only this ledger update pending. |

## Target Contract

Stage 18.7 must make the inference eval report honest about which provider was
evaluated. Control parity must score the provider under test when available,
aggregate metrics must be provider-aware, and grounded citation scoring must
measure cited evidence rather than only available context.

## Planned Evidence

- Unit tests in `packages/labflow-agent/tests/test_inference_eval_ladders.py`.
- No-live runner smoke:
  `python scripts/run_inference_eval_ladder.py --no-live --verbose`.
- Subagent spec-conformance review.

No live OpenRouter, cloud, or paid compute run is authorized or required.

## Implementation Summary

- `control_parity` now scores each non-skipped provider through the existing
  model eval provider path and reports provider-specific parity metrics.
- The root report uses `planner_primary_provider_under_test`; each suite records
  its own `primary_provider_under_test`.
- Reports include `aggregate_by_provider` and Markdown provider aggregate rows.
- Grounded answer citation scoring now uses composer-cited source ids and
  fact-specific cited tool evidence.
- Skipped OpenRouter diagnostics now show OpenRouter/configured model metadata
  instead of deterministic fallback model metadata.

## Evidence Artifacts

Commands:

```text
PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src uv run --python /Users/joseph/.local/bin/python3.12 --with pytest --with pydantic --with pyyaml --with fastapi --with httpx pytest packages/labflow-agent/tests/test_inference_eval_ladders.py -q
```

Result: `12 passed in 0.43s`.

```text
PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src uv run --python /Users/joseph/.local/bin/python3.12 --with pytest --with pydantic --with pyyaml --with fastapi --with httpx python scripts/run_inference_eval_ladder.py --no-live --verbose
```

Result:

- `artifacts/inference_eval_ladders/inference_eval_ladder_20260611T002744335564Z.json`
- `artifacts/inference_eval_ladders/inference_eval_ladder_20260611T002744335564Z.md`

Artifact highlights:

- root `planner_primary_provider_under_test`: `deterministic`;
- suite primaries: `control_parity=deterministic`,
  `semantic_generalization=deterministic`,
  `grounded_answer_quality=offline_fixture_composer`,
  `repair_planning=repair_fixture`;
- skipped OpenRouter rows show `provider=openrouter` and configured model id;
- `aggregate_by_provider` separates deterministic, OpenRouter,
  `offline_fixture_composer`, and `repair_fixture`.

## Subagent Review

Reviewer: `019eb410-b99a-7341-8b3e-32fdc48b8d31`

Initial findings:

- Final ledger status was pending.
- Root primary provider was ambiguous across planner/composer/fixture suites.
- Tool citation scoring was not fact-specific.
- Skipped OpenRouter diagnostics carried deterministic model metadata.

Fixes:

- Renamed root field to `planner_primary_provider_under_test` and documented
  suite-level primary providers separately.
- Made skipped OpenRouter diagnostics use OpenRouter/configured model metadata.
- Made tool citation scoring check required fact terms inside cited evidence.
- Added regression tests for provider scoring, live-provider summary selection,
  wrong source citation, and wrong tool evidence.

Final re-review outcome: implementation and scoring contract clean; only ledger
finalization remained, addressed by this update.

## Final Notes

- No live OpenRouter call was made.
- No cloud or paid compute resources were launched, stopped, deleted, resized,
  restarted, or otherwise mutated.
- Live repair-proposal generation, broad case expansion, baseline rotation, and
  strict CI gate mode remain out of scope for this stage.
