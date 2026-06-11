# LabFlow AI Studio Project Plan

## Project identity

**LabFlow AI Studio** is an AI-assisted developer platform for synthetic LIMS workflow configuration and validation. It uses NGS quantification/normalization workflows as the domain scenario because these workflows require strict sample identity, container tracking, concentration math, robot-ready worklists, batch readiness, re-quantification, and auditability.

## Strategic outcome

The project should prove that the builder can:

- translate real laboratory operations into deterministic software systems;
- build RAG over fragmented domain knowledge;
- evaluate retrieval and answer quality;
- implement guardrailed tool-using agents;
- build developer tooling for a custom workflow DSL;
- design production-shaped backend/AWS architecture;
- communicate engineering decisions clearly.

## Product layers

### Layer 1 — deterministic core

- Domain models: samples, containers, wells, batches, quant results, normalization plans, exceptions, ancestry, audit events.
- Workflows: DNA quantification, DNA normalization, RNA normalization/re-quantification.
- Export/import: Varioskan TSV input, JANUS-style CSV output.
- Validation: batch readiness, transfer validity, plate blank and standard curve requirements.
- Throughput: one-container baseline vs three-container optimized batching.

### Layer 2 — workflow DSL

- YAML-based LabFlow workflow files.
- JSON Schema validation.
- Domain validators beyond schema.
- Examples for valid/invalid DNA quant, DNA normalization, RNA norm/re-quant.

### Layer 3 — knowledge and RAG

- Synthetic SOPs, workflow specs, exception manuals, DSL docs, guardrail policy.
- Ingestion, chunking, indexing, retrieval, citations, no-answer behavior.
- Retrieval quality metrics and golden cases.

### Layer 4 — controlled agent

- Tools wrap deterministic core operations.
- Tool calls are structured JSON.
- Read-only by default.
- Dry-run required for state-changing tools.
- Approval required to commit generated artifacts.
- Audit events generated for all tool calls.

### Layer 5 — developer platform

- VS Code extension.
- YAML diagnostics.
- Hover docs.
- Commands for validation, AI explanation, dry-run JANUS generation, eval runs.

### Layer 6 — production-shaped platform

- FastAPI API.
- Local store abstractions.
- DynamoDB/S3-shaped interfaces.
- Terraform skeleton for Lambda/API Gateway/DynamoDB/S3/IAM/CloudWatch.
- Observability: structured logs, traces, prompt versions, eval runs.

## v0.1 scope

Build enough to support a polished demo and strong case study. Do not attempt full enterprise LIMS functionality.

Included:

- local deterministic workflows;
- local RAG with citations;
- eval harness;
- controlled agent tools;
- local FastAPI;
- VS Code extension skeleton with meaningful commands;
- AWS IaC skeleton;
- docs and case study.

Excluded:

- real production LIMS connectivity;
- real robot execution;
- clinical/diagnostic claims;
- proprietary STARLIMS internals;
- molarity workflows;
- full auth/enterprise IAM implementation;
- full bioinformatics analysis pipeline.
