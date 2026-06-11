# Stage 13 Assembly Review

Review date: 2026-06-09

Stage: `13_vscode_extension_diagnostics_ai`

Authoritative spec: `.codex_build/prompts/13_vscode_extension_diagnostics_ai.md`

Status: `successful`

## Target Contract

Make the VS Code extension useful for the demo by adding API-backed diagnostics for LabFlow YAML files, hover docs for known DSL keys, AI explanation of selected diagnostics, and JANUS dry-run output that clearly shows blocked reasons or artifact previews. The extension must continue to delegate domain validation and tool execution to the local API and avoid complex webviews.

## Extracted DoD Checklist

| DoD item | Status | Evidence |
| --- | --- | --- |
| D1: Read project doctrine/specs before implementation | met | Read Stage 13 prompt, `specs/09_vscode_extension_spec.md`, and current extension/API files. |
| D2: Diagnostics provider for LabFlow YAML files | met | Added `LabFlowDiagnosticsProvider` and diagnostic collection registration. |
| D3: Calls `/workflows/validate` on save or command | met | Save listener and `LabFlow: Validate Workflow` both call API-backed validation. |
| D4: Converts API diagnostics to VS Code diagnostics | met | Added `diagnosticMapping.ts` and `diagnostics.ts`. |
| D5: Hover provider for known DSL keys | met | Added `LabFlowHoverProvider` with static DSL docs. |
| D6: Command explains selected diagnostic using `/agent/explain-diagnostic` | met | `labflow.askAiAboutDiagnostic` now uses selected LabFlow diagnostic code when available. |
| D7: Dry-run JANUS command uses `/tools/execute` | met | Existing `generateJanusDryRun` API client method calls `/tools/execute`; Stage 13 preserves and renders result. |
| D8: Diagnostics show code and suggested action | met | VS Code diagnostics set `code` and append suggested action to the message. |
| D9: AI output displays answer, sources, and tool calls | met | Added `formatAgentData` output rendering. |
| D10: Dry-run output displays blocked reason or artifact preview | met | Added `formatToolExecutionData` output rendering for errors and artifacts. |
| D11: Unit test diagnostic mapping if feasible | met | Added `test/diagnosticMapping.js`. |
| D12: Manual test instructions in extension README | met | Updated `apps/vscode-extension/test/README.md`. |
| D13: Opening invalid example shows diagnostics | met | Provider validates LabFlow YAML on open, save, active-editor change, and initial activation; manual instructions cover opening `invalid_missing_blank.workflow.yaml`; smoke test checks listener wiring. |
| D14: Explain command returns grounded response | met | Command calls `/agent/explain-diagnostic` with selected diagnostic code; manual instructions cover the grounded response check. |
| D15: Extension compiles and tests pass | met | `npm --prefix apps/vscode-extension test` passed; `make type` compiled extension. |
| D16: Reference repo not modified and no cloud mutation | met | Reference repo status remains `?? .DS_Store`; no cloud commands run. |
| D17: Assembly subagent review clean | met | Reviewer Epicurus found one valid D13 trigger gap; it was fixed and re-review was clean. |

## Planned Evidence Commands

```text
npm --prefix apps/vscode-extension test
make test
make lint
make type
git -C /Users/joseph/ngs_lab_automation status --short
```

## Changed Files

- `apps/vscode-extension/package.json`
- `apps/vscode-extension/src/apiClient.ts`
- `apps/vscode-extension/src/diagnosticMapping.ts`
- `apps/vscode-extension/src/diagnostics.ts`
- `apps/vscode-extension/src/extension.ts`
- `apps/vscode-extension/src/hoverDocs.ts`
- `apps/vscode-extension/test/README.md`
- `apps/vscode-extension/test/diagnosticMapping.js`

## Implementation Summary

- Added API-backed diagnostics provider for LabFlow YAML files.
- Added pure diagnostic mapping from API diagnostics to editor ranges/messages.
- Added save-time validation plus command-triggered validation.
- Added hover docs for known LabFlow DSL keys.
- Updated diagnostic explanation command to use the selected LabFlow diagnostic code.
- Added readable output formatting for agent answers, sources, tool calls, JANUS blocked reasons, and artifact previews.
- Added unit smoke coverage for diagnostic mapping and expanded manual extension test instructions.

## Evidence

```text
npm --prefix apps/vscode-extension test
# compile passed; smoke.js and diagnosticMapping.js passed

make test
# 108 passed, 1 warning

make lint
# All checks passed

make type
# mypy success in 75 source files; VS Code extension compile succeeded

git -C /Users/joseph/ngs_lab_automation status --short
# ?? .DS_Store
```

## Review Findings

Reviewer: Epicurus (`019eae72-820b-7f23-9f5c-0dbbafb7e043`)

Initial classification: `review-failed`

Finding addressed:

- P1: Opening an invalid workflow after extension activation might not show diagnostics until save or command. Fixed by adding `onDidOpenTextDocument` and `onDidChangeActiveTextEditor` validation triggers, with smoke-test assertions for the compiled listener hooks.

Re-review classification: `clean`

Reviewer conclusion: D13 and D17 are met; no remaining Stage 13 spec-conformance blockers.

## Residual Risks

- Manual VS Code extension-host verification was documented but not run interactively in this thread.
- Diagnostics use API diagnostic paths to approximate YAML ranges; richer line/column precision would require API-side source locations.
- Hover docs are static and intentionally small; richer corpus-backed hover content can be added later.

## Final Classification

`successful`
