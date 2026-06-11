# VS Code Extension Specification

## Purpose

The VS Code extension demonstrates the STARLIMS-style developer-platform angle: a modern IDE workflow for a custom lab workflow framework/DSL.

## Extension name

`labflow-ai-studio`

## Activation

Activate on:

- `*.labflow.yaml`
- `*.workflow.yaml`
- command invocation.

## Commands

- `LabFlow: Validate Workflow`
- `LabFlow: Ask AI About Diagnostic`
- `LabFlow: Explain Workflow`
- `LabFlow: Generate JANUS Worklist Dry Run`
- `LabFlow: Run Eval Suite`
- `LabFlow: Show Audit Events`

## Diagnostics

Diagnostics should be displayed from API validation output.

Diagnostic fields:

- code;
- severity;
- message;
- YAML path or line/column if available;
- suggested action.

## Hover docs

Hover over known DSL keys should show short docs from `labflow_dsl_reference.md` or static metadata.

## AI panel/output

Use a VS Code output channel or webview for v0.1.

The AI explanation should display:

- answer;
- validation errors;
- cited sources;
- tool calls;
- next safe action.

## Do not overbuild

Do not build a rich React webview in v0.1 unless the basic commands and diagnostics already work.
