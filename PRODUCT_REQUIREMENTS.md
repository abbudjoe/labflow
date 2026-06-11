# Product Requirements — LabFlow AI Studio v0.1

## Problem statement

Lab workflow developers and lab informatics analysts need to understand, configure, validate, and debug complex laboratory workflows across fragmented sources: SOPs, LIMS schemas, instrument files, container registries, worklist formats, exception manuals, and operational doctrine.

AI can help only if it is grounded, evaluated, and constrained by deterministic validation.

## Target user

Primary user: lab informatics developer, LIMS analyst, scientific automation engineer, or workflow developer.

Secondary user: hiring manager evaluating the builder's ability to design AI/LIMS systems.

## Core use cases

1. Validate a workflow DSL file before execution.
2. Explain why a batch is not robot-ready.
3. Retrieve the relevant SOP/doctrine/schema snippets with citations.
4. Call deterministic tools to validate a batch or generate outputs.
5. Propose a dry-run patch to a workflow file.
6. Generate a JANUS-style CSV only after deterministic validation passes.
7. Log and audit each AI/tool action.
8. Run evals that measure retrieval, citation, answer, and tool-call quality.
9. Use VS Code as the primary workflow-development environment.

## User stories

### Workflow validation

As a workflow developer, I want invalid LabFlow YAML files to show diagnostics in VS Code so I can fix errors before generating worklists.

### AI explanation

As a workflow developer, I want to ask why a batch failed readiness and receive a source-grounded explanation plus structured validation errors.

### Controlled artifact generation

As a lab automation analyst, I want the system to block JANUS CSV generation for invalid batches so robot artifacts are never produced from unsafe inputs.

### Eval visibility

As an AI platform engineer, I want retrieval and tool-call evals so I can detect regressions when prompts, chunking, docs, or models change.

## v0.1 acceptance demo

The demo must show:

- a VS Code workflow file;
- diagnostics for missing blank/missing concentration/split/in-place scenarios;
- AI explanation with citations;
- deterministic `validate_batch` tool output;
- dry-run patch proposal;
- approval-gated artifact generation;
- JANUS CSV preview;
- audit log;
- eval report.
