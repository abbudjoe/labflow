# Role Alignment: Senior AI Engineer, AI/LIMS Platform

This document maps LabFlow AI Studio to the capabilities expected for a Senior
AI Engineer building AI features inside a LIMS platform. It is written for
portfolio review, not as a claim of STARLIMS internals, access, or product
compatibility.

## Positioning

LabFlow AI Studio demonstrates how I would add AI to a regulated,
domain-heavy LIMS workflow environment without letting the model become the
source of truth.

The project uses synthetic NGS quantification, normalization, and RNA
re-quantification workflows because they make the hard AI/LIMS problems visible:
sample identity, well locations, missing concentrations, standards, blanks,
readiness gates, downstream QC handoffs, robot-facing artifacts, audit events,
and exception handling.

## Evidence Map

| Role Theme | LabFlow Evidence |
| --- | --- |
| RAG over domain-specific content | `packages/labflow-rag`, `knowledge/`, `scripts/rag_demo.py`, `docs/eval_summary.md` |
| Retrieval ranking and grounding | source-family retrieval controls, policy boosts, citation-ready chunks, `packages/labflow-rag/tests/test_rag_foundation.py` |
| Corpus lifecycle reliability | corpus manifests, fingerprinted eval reports, drift suite, conflict/staleness notices, `docs/corpus_lifecycle_reliability.md` |
| Eval frameworks | `scripts/run_inference_eval_ladder.py`, `evals/`, `docs/eval_summary.md` |
| Hallucination reduction | unsupported-answer behavior, grounded answer verifier, deterministic claim obligations, no-invention guardrails |
| Production AI reliability | provider diagnostics, fallback paths, production-gate summaries, prompt/model metadata |
| Guardrails and approval workflows | `packages/labflow-agent/src/labflow_agent/policies.py`, `approvals.py`, `tool_runtime.py` |
| Tool-using agents | controlled `validate_batch`, `generate_janus_csv`, workflow validation, audit-backed tool execution |
| Downstream provenance | `labflow_core.qc`, QC provenance tools, lineage report demo artifacts |
| Controlled execution paths | read-only by default, dry-run before state change, approval before commit, invalid batches block artifacts |
| VS Code DSL developer tooling | `apps/vscode-extension`, diagnostics, hovers, API-backed commands |
| Backend API boundaries | `apps/api`, FastAPI routes for workflows, RAG, agent, tools, evals, audit, and artifacts |
| AWS-shaped architecture | `infra/terraform`, `docs/aws_architecture_decisions.md`, DynamoDB/S3/Lambda/API Gateway mapping |
| Prompt/model regression tracking | inference eval ladder, prompt hashes, model metadata, frozen baseline plan |
| Observability | traces, audit events, production gates, eval artifacts |

## Adjacent Role Themes

| Theme | Current Project Position |
| --- | --- |
| React/Next/Tailwind frontend | Not core to the demo. The portfolio surface is VS Code plus FastAPI because the role emphasizes developer tooling for a DSL. A future web dashboard could reuse the API and eval summary outputs. |
| Pinecone or managed vector search | Optional Pinecone-shaped backend, indexing metadata preview, and backend comparison scripts are included. Local hybrid retrieval remains the default so reviewers do not need external services. |
| Containerization/orchestration | Not required for local portfolio use. The API boundary and Terraform skeleton make later container or Lambda packaging straightforward. |
| Distributed-systems debugging | Represented by traces, provider diagnostics, eval reports, and API/agent/RAG separation. Full distributed tracing is future production work. |
| Latency/cost tradeoffs | Captured in `docs/eval_summary.md`: deterministic paths are fast and free; live model paths provide language generalization at variable latency and provider availability. |

## Why This Is Not A STARLIMS Clone

- No STARLIMS APIs, schemas, internal workflows, or proprietary SOPs are used.
- The domain content is synthetic and reconstructed for portfolio purposes.
- The project demonstrates AI/LIMS engineering judgment, not product
  compatibility with any proprietary platform.
- It avoids clinical, diagnostic, production lab, and robot-control claims.

## Interview Narrative

Problem:
Lab workflow developers need AI help, but an LLM cannot be trusted to invent
sample facts, concentrations, wells, standards, blanks, or robot worklists.

Architecture:
LabFlow separates deterministic lab truth from AI assistance. The deterministic
core validates workflows and generates dry-run artifacts. RAG retrieves
source-grounded domain context. The agent composes answers and proposes safe
actions through typed tools.

Tradeoff:
This is slower to build than a chatbot, but it produces a system that can be
evaluated, audited, and safely refused when evidence is missing.

Evidence:
The eval ladder reports control parity, semantic generalization, grounded answer
quality, and repair-planning behavior. The VS Code/API surfaces show how the
same deterministic validations can support developer workflows.

Limitation:
This is not production software. Before production it would need auth,
tenancy, monitored drift, human baseline promotion, stronger incident
playbooks, real deployment hardening, and customer-specific SOP ingestion.

## Best Demo Thread

Open the invalid RNA normalization/re-quant workflow, show deterministic
diagnostics, ask why it is not robot-ready, inspect cited sources and
`validate_batch` output, propose only a dry-run patch, require approval before
commit, rerun validation, generate a JANUS-style dry-run preview, and inspect
audit evidence. Then show the optional downstream QC provenance step: ingest
synthetic QC summary metrics, generate a dry-run lab-to-analysis lineage report,
and ask the agent to explain a failed QC sample without inventing a lab root
cause.

See `docs/demo_script_starlims_role.md`.
