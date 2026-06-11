# Interview Review Quiz

Use these answers to prepare for a role-focused project walkthrough.

## Why did you use this chunking strategy?

The RAG corpus is chunked by markdown heading and paragraph windows so citations
stay stable, small, and human-readable. This is enough for a local portfolio
corpus and keeps source IDs deterministic for evals. Before production, I would
compare this with semantic chunking and section-aware embeddings on real SOPs.

Evidence: `packages/labflow-rag/src/labflow_rag/chunking.py`.

## What happens when retrieval fails?

The RAG answer returns an explicit unsupported response rather than fabricating.
The agent can still run deterministic validation if a concrete workflow is
provided, but it cannot invent missing lab facts.

Evidence: `packages/labflow-rag/src/labflow_rag/answering.py`.

## How do you prevent invalid JANUS output?

JANUS-style output is generated through deterministic tools. Invalid samples or
invalid batches block artifact generation. Commit-style actions require a prior
dry-run audit event and approval token.

Evidence: `packages/labflow-agent/src/labflow_agent/tool_runtime.py`,
`packages/labflow-agent/src/labflow_agent/policies.py`.

## How do you measure groundedness?

Grounded answer evals check citation families, claim coverage, tool-fact
accuracy, unsupported claims, fallback behavior, and active-provider failures.
The portfolio summary separates deterministic comparison from active provider
production gates.

Evidence: `scripts/run_inference_eval_ladder.py`, `docs/eval_summary.md`.

## What are your golden eval cases?

Golden cases cover batch readiness, missing concentration, standards/blanks,
split workflow, in-place normalization, RNA re-quant, JANUS blocking, ancestry,
molarity exclusion, and guardrails.

Evidence: `evals/golden_questions.yaml`, `evals/semantic_generalization_cases.yaml`,
`evals/grounded_answer_quality_cases.yaml`.

## What breaks when source documents conflict?

Conflict is treated as a first-class retrieval condition. The answer should
state that conflict was detected, cite both sources, and defer to current
guardrail policy and deterministic validation.

Evidence: `packages/labflow-rag/src/labflow_rag/enterprise.py`.

## How are prompts versioned?

Prompt metadata includes IDs, versions, and hashes in agent traces/eval reports.
The prompt registry would move to durable storage before production.

Evidence: `packages/labflow-agent/src/labflow_agent/prompts.py`,
`packages/labflow-agent/src/labflow_agent/tracing.py`.

## How do you detect regressions?

The eval ladder checks control parity, semantic generalization, grounded answer
quality, and repair planning. Stage 18.15 adds persisted frozen baselines and a
baseline rotation policy so comparison targets do not move silently.

Evidence: `evals/baselines/portfolio_frozen_baselines.json`,
`docs/baseline_rotation.md`.

## Why is the agent read-only by default?

Read-only default prevents the model from causing hidden mutations. State
changes require deterministic tools, dry-run first, explicit approval for
commit, and audit events.

Evidence: `DOCTRINE.md`, `packages/labflow-agent/src/labflow_agent/policies.py`.

## What actions require approval?

Commit-style artifact generation requires approval. Dry-run previews can be
created only through allowed tools and audited execution.

Evidence: `packages/labflow-agent/src/labflow_agent/approvals.py`.

## What is deterministic versus LLM-driven?

Deterministic: parsing, validation, concentration math, normalization planning,
JANUS-style preview generation, audit events, policy enforcement, eval scoring.

LLM-driven: optional planning, explanation phrasing, retrieval query shaping,
and repair proposal drafting. LLM output is never lab truth.

## What would you change before production?

Add auth, tenancy, immutable audit storage, managed secrets, customer SOP
approval workflows, monitored drift, incident playbooks, deployment pipelines,
stronger red-team suites, and security review.

Evidence: `docs/threat_model.md`, `docs/aws_architecture_decisions.md`.

## How does this map to STARLIMS without being a STARLIMS clone?

It maps to the engineering problem: AI over LIMS workflows, RAG, evals,
guardrails, tool use, VS Code developer tooling, and AWS-shaped backend
architecture. It does not use STARLIMS internals, APIs, or proprietary SOPs.

Evidence: `docs/role_alignment_starlims.md`.

## What tradeoff did you make between latency, quality, and cost?

Deterministic paths are fastest and free, so they own validation and safety.
Live model calls improve language generalization but add provider variability
and latency. The eval summary reports this separation explicitly.

Evidence: `docs/eval_summary.md`.

## What would you do with real enterprise SOPs?

Add ingestion review, source metadata, versioning, effective/retired status,
conflict detection, policy precedence, human approval for corpus promotion, and
per-customer eval cases.

Evidence: `packages/labflow-rag/src/labflow_rag/enterprise.py`,
`docs/baseline_rotation.md`.

## Why no React/Next/Tailwind app?

For this role, the stronger portfolio surface is VS Code plus API because the
role emphasizes developer tooling for a custom framework/DSL. A web dashboard
could be added later using the same API and eval summaries.

## How would you move to Pinecone or managed vector search?

Keep chunking, metadata, source-family requirements, evals, and citations as
the contract. Replace or augment the retriever backend with managed vector
search, then rerun retrieval, grounding, latency, and cost evals before
promotion.

## How would you debug distributed failures?

Follow trace IDs across VS Code/API/agent/RAG/tool layers. Inspect provider
diagnostics, retrieval debug reports, audit events, deterministic tool results,
and eval production gates.

Evidence: `docs/agent_failure_taxonomy.md`, `docs/api_contract.md`.
