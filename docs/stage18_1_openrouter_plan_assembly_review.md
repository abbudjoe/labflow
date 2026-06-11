# Stage 18.1 OpenRouter Adapter Plan Assembly Review

Review date: 2026-06-10

Stage: `18.1_optional_openrouter_inference_adapter_plan`

Authoritative plan: `.codex_build/stage18_1_openrouter_adapter_plan.md`

Status: `successful`

## Target Contract

Document and review a plan for adding an optional OpenRouter inference adapter after v0.1 hardening. This is planning only: no implementation code, no live API call, no cloud mutation, and no secret handling beyond documenting environment-variable placeholders.

## Extracted DoD Checklist

| DoD item | Status | Evidence |
| --- | --- | --- |
| D1: Use assembly for plan review | met | Assembly skill invoked by user; this ledger created. |
| D2: Verify current OpenRouter/Nemotron assumption | met | Web check found current OpenRouter slug `nvidia/nemotron-3-ultra-550b-a55b:free`; plan marks it time-sensitive. |
| D3: Document Stage 18.1 scope | met | Plan defines goal and placement after v0.1 hardening. |
| D4: Preserve deterministic default | met | Plan requires `DeterministicFakeModel` remains default for tests/demo/CI. |
| D5: Preserve lab safety boundaries | met | Plan lists deterministic validator ownership, no invented lab data, JANUS gating, RAG citation/no-answer rules. |
| D6: Keep `labflow-core` free of LLM dependencies | met | Plan states core remains LLM/API-free. |
| D7: Define OpenRouter env/config surface | met | Plan lists provider/model/API key/base URL/app metadata variables. |
| D8: Define proposed files and seams | met | Plan maps implementation files, tests, docs, and script. |
| D9: Define structured output and fallback behavior | met | Plan requires JSON-to-`AgentPlan` validation and safe fallback for malformed/unsafe output. |
| D10: Define offline test plan | met | Plan lists mocked tests and no-network requirement. |
| D11: Define optional live smoke only when credentials exist | met | Plan includes skipped live smoke command gated by `OPENROUTER_API_KEY`. |
| D12: Define eval comparison plan | met | Plan proposes deterministic vs optional OpenRouter comparison JSON output. |
| D13: Define docs and `.env.example` updates | met | Plan includes docs and empty env placeholders. |
| D14: Define acceptance criteria | met | Plan includes clear acceptance criteria. |
| D15: Define risks | met | Plan includes provider availability, JSON reliability, tool over-recommendation, nondeterminism, free-tier changes. |
| D16: No implementation or live mutation performed | met | Only plan and ledger files were added. |
| D17: Assembly subagent review completed | met | Reviewer found two blocking plan gaps; both were incorporated into the plan. |
| D18: Preserve workflow-YAML validation invariant | met | Plan now requires a post-model normalizer that forces `validate_batch` with request-owned `workflow_yaml` and `batch_id` whenever workflow YAML is present. |
| D19: Constrain model-supplied tool arguments | met | Plan now restricts Stage 18.1 to tool intents, allows only `validate_batch` and `explain_exception_code`, and rejects file-path tools or invented arguments before execution. |

## Planned Evidence Commands

```text
sed -n '1,260p' .codex_build/stage18_1_openrouter_adapter_plan.md
sed -n '1,220p' docs/stage18_1_openrouter_plan_assembly_review.md
git -C /Users/joseph/ngs_lab_automation status --short
```

## Changed Files

- `.codex_build/stage18_1_openrouter_adapter_plan.md`
- `docs/stage18_1_openrouter_plan_assembly_review.md`

## Review Findings

Subagent reviewer: `019eaf49-7401-7db1-bce9-5ce55855ad67`

Blocking findings addressed:

1. The original plan did not explicitly preserve the current contract that supplied workflow YAML always triggers deterministic validation. The plan now requires a post-model invariant normalizer that forces exactly one `validate_batch` call with `workflow_yaml` and `batch_id` copied from `AgentRequest`.
2. The original plan rejected unknown tools and unsafe modes, but did not sufficiently constrain model-supplied arguments for read-only tools. The plan now restricts Stage 18.1 to tool intents only, limits allowed intents to `validate_batch` and `explain_exception_code`, rejects file-path tools, and requires arguments to be bound from trusted request/context data.

Non-blocking notes incorporated:

- Runtime construction should call `model_factory` when `LabFlowAgentRuntime(model=None)` is used, so env opt-in is not inert.
- Trace-provider wording was clarified because current `AgentTrace` records model ID and version, not a provider field.
- The OpenRouter slug remains time-sensitive even though the reviewer also confirmed it is currently listed as free.

Outcome: plan is approved for implementation after the above corrections. No implementation, live API call, or cloud mutation was performed during this planning review.
