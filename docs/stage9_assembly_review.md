# Stage 9 Assembly Review

Review date: 2026-06-09

Stage: `09_agent_runtime`

Authoritative spec: `.codex_build/prompts/09_agent_runtime.md`

Status: `successful`

## Target Contract

Build `labflow-agent`, a controlled local tool-using runtime that combines LabFlow RAG retrieval, deterministic `labflow-core` tools, and grounded response composition. The runtime must use a deterministic fake model for tests, produce structured tool-call plans, cite retrieved source chunks, stay read-only by default, avoid mutation logic, and only use dry-run where applicable.

## Extracted DoD Checklist

| DoD item | Status | Evidence |
| --- | --- | --- |
| D1: Read project doctrine/specs before implementation | met | Read `AGENTS.md`, `DOCTRINE.md`, `ENGINEERING.md`, `DECISIONS_LOCKED.md`, `PROJECT_PLAN.md`, `specs/04_rag_spec.md`, `specs/06_agent_tools_spec.md`, and `specs/07_guardrails_audit_spec.md`. |
| D2: Implement Stage 9 files | met | Added `models.py`, `tool_runtime.py`, `planner.py`, `answer_composer.py`, and `runtime.py`. |
| D3: Build tool registry from `labflow-core` | met | `AgentToolRuntime` wraps `labflow_core.tools.registry.list_tools` and `call_tool`. |
| D4: Use RAG retrieval from `labflow-rag` | met | `LabFlowAgentRuntime` builds `RagIndex`, `HybridRetriever`, and calls `answer_query`. |
| D5: Provide deterministic fake model for tests | met | Added `DeterministicFakeModel` in `planner.py`; no external model dependency. |
| D6: Produce structured tool-call plans | met | Added `AgentPlan` and `ToolCallPlan` typed models; planner emits structured plans. |
| D7: Compose grounded answer responses with source chunks | met | `AnswerComposer` returns `AgentResponse` with `SourceChunk` citations and canonical refusal for unsupported plans. |
| D8: Avoid mutation logic; only dry-run where applicable | met | Tool runtime blocks non-read-only mutation by default and requires `dry_run=true` for the allowlisted `generate_janus_csv`; no commit/approval logic added. |
| D9: Support explain diagnostic, answer workflow question, validate batch and explain errors, recommend safe next action | met | Runtime validates any supplied workflow YAML before claims and supports answer/diagnostic/next-action planning. |
| D10: Tests cover missing blank with RAG + validate tool | met | `test_agent_explains_missing_blank_using_rag_and_validate_tool`. |
| D11: Tests cover split workflow with required sources | met | `test_agent_explains_split_workflow_with_required_sources`. |
| D12: Tests cover unsupported question refusal | met | `test_agent_refuses_unsupported_question` and mixed off-domain regression. |
| D13: Tests cover agent does not invent missing concentration | met | `test_agent_does_not_invent_missing_concentration`. |
| D14: Agent runtime tests pass locally without external model | met | Focused agent tests passed: `9 passed`; full `make test` passed: `93 passed`. |
| D15: No reference repo modification and no cloud mutation | met | Reference repo status remains only `?? .DS_Store`; no cloud commands run. |
| D16: Assembly subagent review clean | met | Hegel re-review classified D1-D16 as met and clean. |

## Changed Files

- `packages/labflow-agent/src/labflow_agent/__init__.py`
- `packages/labflow-agent/src/labflow_agent/models.py`
- `packages/labflow-agent/src/labflow_agent/tool_runtime.py`
- `packages/labflow-agent/src/labflow_agent/planner.py`
- `packages/labflow-agent/src/labflow_agent/answer_composer.py`
- `packages/labflow-agent/src/labflow_agent/runtime.py`
- `packages/labflow-agent/tests/test_agent_runtime.py`

## Implementation Summary

- Added typed request, plan, tool call, source chunk, and response models.
- Added controlled tool runtime around deterministic `labflow-core` tools.
- Added deterministic fake model/planner for supported Stage 9 tasks and off-domain refusal.
- Added grounded answer composer that combines RAG citations with deterministic tool output and blocked reasons.
- Added runtime orchestration over planner, RAG retrieval, tool execution, and response composition.
- Added tests for missing blank validation, split workflow sources, unsupported refusal, mixed off-domain refusal, workflow-YAML validation trigger, and missing concentration non-invention.
- Added a policy regression test proving `generate_janus_csv` cannot run outside dry-run mode in Stage 9.

## Planned Evidence Commands

```text
PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src python -m pytest packages/labflow-agent/tests -q
uv run --python python3 --with pytest --with pydantic --with pyyaml env PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src python -m pytest packages/labflow-agent/tests -q
# 9 passed

make test
# 93 passed

make lint
# All checks passed

make type
# mypy success in 59 source files; VS Code extension compile succeeded

rg -n "openai|langchain|llamaindex|api_key|OPENAI|requests|httpx|urllib|boto3|botocore" packages/labflow-agent || true
# no matches

git -C /Users/joseph/ngs_lab_automation status --short
# ?? .DS_Store
```

## Review Findings

Reviewer: Hegel (`019eaddc-e140-7f10-9461-0ba92ec74243`)

Initial classification: `review-failed`

Findings addressed:

- P1: Unsupported planner decisions could still return supported RAG answers if RAG found LabFlow chunks. Fixed `AnswerComposer` to return the canonical unsupported response with no sources for `AgentTask.UNSUPPORTED`, and added a mixed off-domain regression for `Can pizza fix the missing blank in this batch?`.
- P2: Supplied workflow YAML did not always trigger deterministic validation. Fixed `DeterministicFakeModel` so any request with `workflow_yaml` produces a `validate_batch` plan before claims, and added an `Is this ok?` invalid-workflow regression.
- P3: Non-read-only tools were not default-denied if future tools were added. Fixed `AgentToolRuntime` to allow only explicitly allowlisted dry-run tools and reject other non-read-only tools by default, with a regression test.

Re-review classification: `clean`

Reviewer conclusion: D1-D16 are met and assembly review is clean.

## Post-Review Smoke

```text
uv run --python python3 --with pytest --with pydantic --with pyyaml env PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src python -m pytest packages/labflow-agent/tests -q
# 9 passed

git -C /Users/joseph/ngs_lab_automation status --short
# ?? .DS_Store
```

## Residual Risks

- The Stage 9 planner is deterministic and intentionally simple. It is suitable for local tests and demo scaffolding, but later stages should replace or augment it with a policy-aware model router/prompt registry.
- Stage 9 does not implement durable approval storage, commit actions, or persisted audit retrieval. Tool wrappers return audit events, and Stage 10 owns guardrail/approval/audit hardening.
- `answer_query` remains an extractive local composer. Stage 9 composes around it, but richer answer quality belongs to later prompt/model and eval work.

## Final Classification

`successful`
