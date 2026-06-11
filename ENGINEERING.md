# Engineering Guide

## Repository strategy

Use a monorepo with clear package boundaries.

```text
packages/labflow-core   deterministic lab/LIMS workflow engine
packages/labflow-rag    knowledge ingestion, retrieval, citations, evals
packages/labflow-agent  controlled tool-using agent runtime
apps/api                FastAPI boundary
apps/vscode-extension   VS Code developer tooling
infra                   AWS-shaped infrastructure skeleton
knowledge               RAG corpus
evals                   golden cases and eval configs
examples                synthetic workflow/instrument/worklist files
```

## Language and tooling

### Python

- Python 3.12.
- Pydantic v2 for typed models.
- pytest for tests.
- ruff for lint/format.
- mypy where practical.
- FastAPI for local API.

### TypeScript

- TypeScript for VS Code extension.
- Jest or Vitest for tests.
- ESLint where practical.

### Infrastructure

- Terraform skeleton preferred.
- No real secrets.
- No required cloud deployment for v0.1.

## Boundaries

### labflow-core

Contains no LLM dependency. Responsible for:

- units;
- wells;
- containers;
- samples;
- statuses;
- exceptions;
- ancestry;
- quantification processing;
- normalization planning;
- JANUS export;
- batch readiness;
- throughput simulation.

### labflow-rag

Responsible for:

- loading `knowledge/*.md`;
- chunking;
- metadata;
- retrieval;
- citations;
- no-answer behavior;
- eval support.

May use a deterministic local embedding fallback for tests. Do not require a paid API key to run core tests.

### labflow-agent

Responsible for:

- tool registry;
- controlled tool execution;
- dry-run/approval policy;
- audit events;
- grounded answer composition;
- prompt registry integration.

The agent must call `labflow-core` tools rather than duplicating lab logic.

### apps/api

Responsible for exposing:

- workflow validation;
- tool execution;
- RAG query;
- eval run;
- audit event retrieval;
- artifact generation/retrieval.

### apps/vscode-extension

Responsible for:

- opening LabFlow YAML workflows;
- diagnostics;
- hover docs;
- calling local API;
- AI explain command;
- dry-run JANUS generation command;
- eval suite command.

## Testing standards

Every deterministic rule must have tests.

Required core tests:

- well parsing A1-H12;
- standard wells A1-H1;
- blank well handling;
- standard curve fitting;
- dilution factor application;
- DNA normalization formula;
- low-concentration block;
- insufficient source volume block;
- destination overflow block;
- in-place normalization;
- split workflow;
- RNA re-quant downstream update;
- JANUS export excludes invalid rows;
- duplicate sample/source/destination blocking;
- batch readiness gates;
- throughput comparison baseline vs optimized.

Required RAG/eval tests:

- required sources retrieved for golden questions;
- answer says not supported when corpus does not support a claim;
- citation metadata is preserved;
- exception questions retrieve exception manual;
- split workflow questions retrieve split doctrine.

Required agent tests:

- invalid batch cannot generate JANUS worklist;
- dry-run is required before commit;
- approval token required for commit;
- audit event created for every tool call;
- agent does not invent missing concentration.

## Done criteria per stage

A stage is done when:

- files are scoped to the stage;
- tests are added or updated;
- tests pass or failures are explicitly documented;
- README/docs are updated if behavior changed;
- Codex summarizes risks and assumptions.

## Do not do

- Do not create a generic chatbot.
- Do not make LLM output authoritative over deterministic validation.
- Do not add molarity.
- Do not claim production or clinical readiness.
- Do not hard-code proprietary or confidential details.
- Do not silently generate robot worklists for invalid data.
- Do not make cloud credentials required for local tests.
