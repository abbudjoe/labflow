# Stage 14 Assembly Review

Review date: 2026-06-09

Stage: `14_observability_prompt_registry`

Authoritative spec: `.codex_build/prompts/14_observability_prompt_registry.md`

Status: `successful`

## Target Contract

Add production-shaped observability and prompt/model versioning: prompt files with stable hashes, a prompt registry, a model adapter abstraction with deterministic fake model metadata, agent/tool traces with prompt/model/retrieval/tool/latency fields, and eval reports that include prompt/model metadata.

## Extracted DoD Checklist

| DoD item | Status | Evidence |
| --- | --- | --- |
| D1: Read project doctrine/specs before implementation | met | Read Stage 14 prompt and `specs/11_observability_prompt_registry_spec.md`. |
| D2: Add `prompts.py` | met | Added `packages/labflow-agent/src/labflow_agent/prompts.py`. |
| D3: Update `models.py` with model adapter/observability types | met | Added `ModelMetadata`, `ModelAdapter`, and `AgentTrace`; `AgentResponse` now includes `trace`. |
| D4: Add `tracing.py` | met | Added trace ID/request ID/timer helpers. |
| D5: Add `observability.py` | met | Added agent/tool observability payload helpers. |
| D6: Add runtime prompt files | met | Added `rag_answer.md`, `agent_planner.md`, `diagnostic_explainer.md`, and `patch_proposer.md`. |
| D7: Prompt registry computes hashes | met | `PromptRegistry` computes `sha256:` content hashes. |
| D8: Model adapter abstraction includes fake model for tests | met | Added `ModelAdapter` protocol and fake model metadata on `DeterministicFakeModel`. |
| D9: Trace IDs track prompt ID/version, model ID, retrieved chunks, tool calls, latency | met | `AgentTrace` includes required prompt/model/retrieval/tool/latency fields and token/cost placeholders. |
| D10: Eval report includes prompt/model versions | met | `EvalRunReport` now includes `prompt_model`. |
| D11: Test prompt hash stability | met | `test_prompt_hash_is_stable`. |
| D12: Test trace created for agent response | met | `test_agent_response_includes_trace_metadata`. |
| D13: Test eval report includes prompt metadata | met | Updated RAG eval harness tests for `prompt_model`. |
| D14: Observability fields visible in eval/tool/agent outputs | met | Agent responses include `trace`; tool results include `observability`; eval reports include `prompt_model`. |
| D15: Tests/lint/type pass | met | Focused tests passed; full `make test`, `make lint`, and `make type` passed. |
| D16: Reference repo not modified and no cloud mutation | met | Reference repo status remains `?? .DS_Store`; no cloud commands run. |
| D17: Assembly subagent review clean | met | Reviewer Godel found three valid issues; all were fixed and re-review was clean. |

## Planned Evidence Commands

```text
uv run --python python3 --with pytest --with pydantic --with pyyaml env PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src python -m pytest packages/labflow-agent/tests packages/labflow-rag/tests/test_rag_eval_harness.py -q
make test
make lint
make type
git -C /Users/joseph/ngs_lab_automation status --short
```

## Changed Files

- `packages/labflow-agent/src/labflow_agent/__init__.py`
- `packages/labflow-agent/src/labflow_agent/models.py`
- `packages/labflow-agent/src/labflow_agent/observability.py`
- `packages/labflow-agent/src/labflow_agent/planner.py`
- `packages/labflow-agent/src/labflow_agent/prompts.py`
- `packages/labflow-agent/src/labflow_agent/runtime.py`
- `packages/labflow-agent/src/labflow_agent/tool_runtime.py`
- `packages/labflow-agent/src/labflow_agent/tracing.py`
- `packages/labflow-agent/tests/test_observability.py`
- `packages/labflow-rag/src/labflow_rag/evals/__init__.py`
- `packages/labflow-rag/src/labflow_rag/evals/runner.py`
- `packages/labflow-rag/tests/test_rag_eval_harness.py`
- `prompts/runtime/agent_planner.md`
- `prompts/runtime/diagnostic_explainer.md`
- `prompts/runtime/patch_proposer.md`
- `prompts/runtime/rag_answer.md`

## Implementation Summary

- Added versioned runtime prompt files with frontmatter metadata.
- Added prompt registry that computes stable `sha256:` content hashes.
- Added model adapter metadata and deterministic fake model identity.
- Added agent traces with prompt/model/retrieval/tool/latency/outcome/token/cost fields.
- Added tool-result observability payloads.
- Added eval report prompt/model metadata.
- Added tests for prompt hash stability, agent trace creation, tool observability, and eval prompt metadata.

## Evidence

```text
uv run --python python3 --with pytest --with pydantic --with pyyaml env PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src python -m pytest packages/labflow-agent/tests/test_observability.py packages/labflow-rag/tests/test_rag_eval_harness.py -q
# 16 passed

make test
# 114 passed, 1 warning

make lint
# All checks passed

make type
# mypy success in 78 source files; VS Code extension compile succeeded

git -C /Users/joseph/ngs_lab_automation status --short
# ?? .DS_Store
```

## Review Findings

Reviewer: Godel (`019eae80-1cb7-7e33-b49d-8fe76c7c7237`)

Initial classification: `review-failed`

Findings addressed:

- P1: Prompt registry was cwd-dependent and could silently load zero prompts outside the repo root. Fixed default prompt directory resolution to walk from the package file to the repo root and fail fast when required runtime prompts are missing. Added `test_prompt_registry_loads_from_non_repo_cwd`.
- P2: Eval reports lacked baseline comparison. Added optional `baseline_report_path`, `baseline_comparison`, baseline metrics, and metric deltas. Added `test_eval_report_includes_baseline_comparison`.
- P3: Agent traces attributed workflow-question responses to `agent_planner` instead of `rag_answer`. Fixed prompt selection for `ANSWER_WORKFLOW_QUESTION` and added `test_rag_answer_response_uses_rag_prompt_metadata`.

Re-review classification: `clean`

Reviewer conclusion: D7, D9, D10, D14, and D17 are met; no further findings.

## Residual Risks

- Prompt/model metadata is local and deterministic; no external model provider telemetry is integrated yet.
- Token and cost fields are placeholders until a real model adapter is introduced.
- Baseline comparison is JSON-file based and local-first; richer baseline management belongs in later hardening work.

## Final Classification

`successful`
