# Case Study: LabFlow AI Studio

## Background Problem

Laboratory automation work is often framed as robot programming, but the harder software problem is the coordination layer around the robot. A batch is not robot-ready just because a CSV can be written. It needs valid sample identity, source and destination locations, concentrations, blanks, standards, exception handling, ancestry, and auditability.

LabFlow AI Studio uses synthetic NGS quantification and normalization workflows to demonstrate how an AI-assisted developer platform can help with that coordination layer without replacing deterministic validation.

## Product Goal

The goal is a portfolio-ready system that shows:

- deterministic lab workflow modeling;
- RAG over domain-specific workflow docs;
- evals for retrieval and answer behavior;
- guarded tool-using agents;
- VS Code workflow developer tooling;
- local API boundaries;
- production-shaped AWS architecture.

For the role-focused review path, see `docs/role_alignment_starlims.md`,
`docs/demo_script_starlims_role.md`, and `docs/eval_summary.md`.

The project is not a production LIMS, clinical system, robot controller, or proprietary workflow reproduction.

## Deterministic Lab Engine

The deterministic engine lives in `packages/labflow-core`. It models:

- canonical units: ng/uL, uL, ng;
- wells A1-H12 and standards A1-H1;
- Matrix 96 x 1 mL containers;
- sample, status, exception, and ancestry records;
- Varioskan TSV parsing;
- linear standard curves;
- quantification and normalization;
- split workflow when transfer volume is below 1 uL;
- in-place normalization when source volume is constrained;
- RNA re-quant downstream concentration;
- JANUS-style dry-run CSV previews.

This layer is intentionally independent of LLMs. If the agent disappeared, validation and artifact gating would still work.

## AI And RAG Layer

The RAG layer lives in `packages/labflow-rag`. It loads synthetic markdown files from `knowledge/`, chunks them with stable chunk IDs, retrieves relevant context, and provides citation metadata.

The current answer composer is local and extractive. Unsupported questions return an explicit unsupported response. This keeps the demo reproducible and avoids claiming live model behavior before the rest of the system is hardened.

## Eval Harness

The eval harness measures whether the retrieval and answer stack can find and cite the right source material. Golden cases live in `evals/golden_questions.yaml` and cover:

- batch readiness;
- standards and blanks;
- split workflow;
- in-place normalization;
- RNA re-quant;
- JANUS gating;
- sample ancestry;
- molarity exclusion;
- guardrails;
- throughput.

Stage 16 adds a retrieval-only demo eval report in `examples/expected/eval_report.json`. That report proves corpus coverage for the demo. Earlier eval code also supports answer-term checks, disallowed-answer checks, tool-call expectations, latency, and prompt/model metadata.

## Guardrails

The core safety doctrine is deterministic before generative:

- validators own lab truth;
- the agent does not invent concentrations, IDs, wells, blanks, standards, or worklists;
- RAG answers cite sources or say unsupported;
- invalid batches cannot generate JANUS previews;
- state-changing actions require dry-run first;
- commit-style actions require approval infrastructure;
- tool calls create audit events.

The Stage 16 demo makes this concrete. The invalid RNA workflow reports missing blank and missing concentration errors, and JANUS generation is blocked until the workflow is fixed.

## Developer Platform

The VS Code extension is the developer-facing surface. It provides diagnostics and commands for LabFlow workflow YAML files. The local FastAPI app exposes the same underlying capabilities so CLI, API, and editor workflows use the same deterministic system.

The demo script in `scripts/run_demo.py` ties the pieces together by validating workflows, parsing synthetic Varioskan TSVs, generating expected artifacts, writing audit logs, and running retrieval evals.

## AWS-Shaped Architecture

Stage 15 added Terraform modules for a production-shaped AWS mapping:

- FastAPI adapter to Lambda;
- API Gateway HTTP API;
- DynamoDB tables for workflow state, audit events, eval runs, artifacts, and prompt versions;
- S3 buckets and prefixes for knowledge, instrument files, generated artifacts, and eval reports;
- IAM roles and policies;
- CloudWatch logs.

This is deliberately a skeleton. It validates with Terraform but is not applied by default and does not require cloud credentials for local development.

## Lessons Learned And Tradeoffs

The main tradeoff is speed versus safety. It would be faster to let an LLM produce a plausible answer or CSV directly, but that would undermine the lab automation story. LabFlow keeps lab truth deterministic and uses AI-shaped components only where they can be grounded, evaluated, and audited.

Another tradeoff is demo reliability versus realism. The project currently defaults to deterministic model behavior so tests and demos are stable. Real inference should be added later behind provider adapters, with the same RAG, eval, trace, dry-run, and approval controls.

The final tradeoff is local-first simplicity versus production depth. The AWS skeleton shows deployment boundaries, but production would still need authentication, tenancy, durable stores, CI/CD, observability dashboards, secrets management, and security review.

## Result

LabFlow AI Studio now demonstrates a coherent AI/LIMS workflow platform shape:

- a deterministic lab engine;
- source-grounded knowledge retrieval;
- evals and prompt/model tracking;
- guarded tool use;
- local API/editor integration;
- synthetic demo artifacts;
- clear production-shaped infrastructure boundaries.

The portfolio hardening path adds share-readiness checks, curated eval
summaries, frozen baseline policy, retrieval conflict/staleness diagnostics,
agent failure taxonomy, and explicit AWS/API/threat-model documentation.
