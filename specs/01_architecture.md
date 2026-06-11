# Architecture Specification

## Overview

LabFlow AI Studio is a monorepo with deterministic lab workflow logic at the center and AI capabilities layered around it.

```mermaid
flowchart TD
  DSL[LabFlow YAML DSL] --> Validator[DSL + Domain Validator]
  Validator --> Core[labflow-core]
  Core --> Artifacts[JANUS CSV / Reports / Audit / Manifests]

  Knowledge[Knowledge Corpus] --> RAG[labflow-rag]
  Evals[Golden Eval Cases] --> RAG
  RAG --> Agent[labflow-agent]
  CoreTools[Core Tool Wrappers] --> Agent
  Agent --> API[FastAPI]
  API --> VSCode[VS Code Extension]
  API --> Audit[Audit Store]
  API --> EvalReports[Eval Reports]

  API -. deploy shape .-> AWS[AWS Lambda/API Gateway/DynamoDB/S3]
```

## Local-first architecture

The project must run locally without cloud credentials:

- SQLite or JSONL local store.
- Local document index.
- Mock model adapter or test model stub for evals.
- Optional environment variables for real LLM/embedding calls.

## Package responsibilities

### labflow-core

No LLM dependency. Owns deterministic lab workflow rules.

### labflow-rag

Owns retrieval over knowledge corpus and eval support.

### labflow-agent

Owns controlled tool orchestration, policy checks, audit, and grounded answer composition.

### API

Provides unified boundary for VS Code extension and demos.

### VS Code extension

Primary developer UX. Must be thin and call API for heavy logic.

## Data flow: explain failed batch

```mermaid
sequenceDiagram
  participant Dev as Developer
  participant VS as VS Code Extension
  participant API as FastAPI
  participant Agent as labflow-agent
  participant RAG as labflow-rag
  participant Core as labflow-core

  Dev->>VS: Ask why batch is not robot-ready
  VS->>API: POST /agent/explain-diagnostic
  API->>Agent: explain(diagnostic, workflow)
  Agent->>RAG: retrieve relevant doctrine
  Agent->>Core: validate_batch(workflow)
  Core-->>Agent: structured errors
  RAG-->>Agent: cited chunks
  Agent-->>API: grounded explanation + errors + sources
  API-->>VS: response
  VS-->>Dev: explanation panel
```

## Data flow: generate JANUS CSV

```mermaid
sequenceDiagram
  participant Dev as Developer
  participant VS as VS Code Extension
  participant API as FastAPI
  participant Agent as labflow-agent
  participant Core as labflow-core
  participant Audit as Audit Store

  Dev->>VS: Generate JANUS CSV dry run
  VS->>API: POST /tools/generate_janus_csv dry_run=true
  API->>Agent: execute tool
  Agent->>Core: validate_batch
  Core-->>Agent: valid/invalid
  alt invalid
    Agent-->>API: blocked + errors
  else valid
    Agent->>Core: generate_janus_csv(dry_run=true)
    Agent->>Audit: log dry-run event
    Agent-->>API: preview artifact
  end
```
