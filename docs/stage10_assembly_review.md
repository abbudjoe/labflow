# Stage 10 Assembly Review

Review date: 2026-06-09

Stage: `10_guardrails_approvals_audit`

Authoritative spec: `.codex_build/prompts/10_guardrails_approvals_audit.md`

Status: `successful`

## Target Contract

Implement the first durable local guardrail control plane in `labflow-agent`: action classification, dry-run-before-commit enforcement, approval-token checks, audit events for every agent tool call, invalid-batch blocking for JANUS generation, and artifact records for approved commit actions.

## Extracted DoD Checklist

| DoD item | Status | Evidence |
| --- | --- | --- |
| D1: Read project doctrine/specs before implementation | met | Read `AGENTS.md`, `DOCTRINE.md`, `ENGINEERING.md`, `DECISIONS_LOCKED.md`, `.codex_build/prompts/10_guardrails_approvals_audit.md`, and `specs/07_guardrails_audit_spec.md`. |
| D2: Add `policies.py` | met | Added `packages/labflow-agent/src/labflow_agent/policies.py`. |
| D3: Add `approvals.py` | met | Added `packages/labflow-agent/src/labflow_agent/approvals.py`. |
| D4: Add `audit.py` | met | Added `packages/labflow-agent/src/labflow_agent/audit.py`. |
| D5: Add `artifacts.py` | met | Added `packages/labflow-agent/src/labflow_agent/artifacts.py`. |
| D6: Support action classes: read-only, dry-run artifact, commit | met | `ActionClass` and `ToolPolicy.classify` cover all three classes. |
| D7: Require dry-run before commit | met | `AgentToolRuntime._execute_commit` requires `dry_run_audit_event_id` and successful matching dry-run audit event. |
| D8: Require approval token for commit | met | `ApprovalStore.require_valid` gates commit execution. |
| D9: Create audit event for every tool call | met | `AuditStore` records successful, blocked, and policy-rejected agent tool calls. |
| D10: Invalid batch blocks JANUS CSV generation | met | Invalid dry-run preserves core `JANUS_BLOCKED_FOR_INVALID_BATCH` and records agent audit. |
| D11: Tool output includes audit_event_id | met | `AgentToolRuntime` enriches returned tool result with agent `audit_event_id`, `audit_event`, and `core_audit_event_id` when present. |
| D12: Test commit without dry-run fails | met | `test_commit_without_dry_run_fails_and_is_audited`. |
| D13: Test commit without approval fails | met | `test_commit_without_approval_fails_and_is_audited`. |
| D14: Test JANUS generation blocked for invalid batch | met | `test_janus_generation_blocked_for_invalid_batch_and_audited`. |
| D15: Test dry-run creates audit event | met | `test_dry_run_creates_audit_event`. |
| D16: Test commit creates audit event and artifact record | met | `test_commit_creates_audit_event_and_artifact_records`. |
| D17: Guardrail tests pass | met | Focused agent tests passed: `14 passed`; full `make test` passed: `98 passed`. |
| D18: Document changed policy in `knowledge/ai_guardrails_policy.md` | met | Updated policy to describe local commit artifact records, dry-run requirement, and approval requirement. |
| D19: Reference repo not modified and no cloud mutation | met | Reference repo status remains `?? .DS_Store`; no cloud commands run. |
| D20: Assembly subagent review clean | met | Reviewer Parfit found two valid implementation issues; both were fixed and re-review was clean. |

## Planned Evidence Commands

```text
uv run --python python3 --with pytest --with pydantic --with pyyaml env PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src python -m pytest packages/labflow-agent/tests -q
make test
make lint
make type
git -C /Users/joseph/ngs_lab_automation status --short
```

## Changed Files

- `knowledge/ai_guardrails_policy.md`
- `packages/labflow-agent/src/labflow_agent/__init__.py`
- `packages/labflow-agent/src/labflow_agent/approvals.py`
- `packages/labflow-agent/src/labflow_agent/artifacts.py`
- `packages/labflow-agent/src/labflow_agent/audit.py`
- `packages/labflow-agent/src/labflow_agent/models.py`
- `packages/labflow-agent/src/labflow_agent/policies.py`
- `packages/labflow-agent/src/labflow_agent/tool_runtime.py`
- `packages/labflow-agent/tests/test_agent_runtime.py`
- `packages/labflow-agent/tests/test_guardrails_approvals_audit.py`

## Implementation Summary

- Added policy classification for read-only, dry-run artifact, and commit actions.
- Added local approval-token records bound to action and dry-run audit event.
- Added local agent-level audit records for successful, blocked, and policy-rejected tool calls.
- Added local artifact records for approved commit actions.
- Wired `AgentToolRuntime` through the policy, approval, audit, and artifact stores.
- Preserved core deterministic validation: invalid JANUS requests remain blocked by `labflow-core`.
- Updated the knowledge guardrails policy to reflect Stage 10 local commit behavior.

## Evidence

```text
uv run --python python3 --with pytest --with pydantic --with pyyaml env PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src python -m pytest packages/labflow-agent/tests -q
# 16 passed

make test
# 100 passed

make lint
# All checks passed

make type
# mypy success in 63 source files; VS Code extension compile succeeded

git -C /Users/joseph/ngs_lab_automation status --short
# ?? .DS_Store
```

## Review Findings

Reviewer: Parfit (`019eae21-3a07-7aa1-9767-4a032f63e1a6`)

Initial classification: `review-failed`

Findings addressed:

- P1: Commit approval was bound only to planned arguments, not to the actual dry-run artifact payload. Fixed by storing deterministic tool results in `AuditStore` and creating commit artifact records from the audited dry-run result instead of re-running `generate_janus_csv`. Added `test_commit_records_audited_dry_run_artifacts_if_source_file_changes`.
- P2: Policy-rejected tool calls created audit events but raised before returning tool output with `audit_event_id`. Fixed classification failures to return structured blocked `ExecutedToolCall` results with `audit_event_id` and embedded `audit_event`.
- P3: Ledger status/evidence were incomplete before re-review. Updated after clean review and refreshed evidence counts.

Re-review classification: `clean`

Reviewer conclusion: D9 and D11 are now met, the provenance issue is fixed, and no code-level blockers remain.

## Residual Risks

- Stage 10 stores approvals, audit events, and artifact records in memory for local tests and demos. A durable store belongs in the API/cloud-shaped stages.
- Commit currently records approved artifact metadata from the audited dry-run payload; it does not write robot files to disk or a production artifact service.
- Approval tokens are local synthetic tokens, suitable for demonstrating the guardrail contract but not production authentication.

## Final Classification

`successful`
