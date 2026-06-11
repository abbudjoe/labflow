# Resume Bullets

Use or adapt these bullets depending on the role and space available.

## AI Platform / LIMS Workflow

- Built LabFlow AI Studio, a local-first AI-assisted LIMS workflow development studio for synthetic NGS quantification, normalization, and RNA re-quantification workflows.
- Implemented a deterministic lab workflow engine for well validation, Matrix 96 x 1 mL containers, Varioskan TSV parsing, standard-curve fitting, DNA/RNA normalization, split workflows, in-place normalization, RNA re-quantification, JANUS-style previews, exceptions, ancestry, and audit records.
- Designed guardrails so AI components can retrieve, explain, and call tools, while deterministic validators remain the source of truth for robot-readiness and artifact generation.

## RAG / Evals / Agents

- Built a local RAG stack over synthetic lab workflow documentation with stable chunk IDs, citation metadata, unsupported-answer behavior, and retrieval evals over golden cases.
- Implemented an eval harness for retrieval recall, citation proxy checks, answer-term matching, disallowed-answer violations, tool-call expectations, latency, and prompt/model metadata.
- Built a controlled tool-using agent runtime that combines RAG retrieval with deterministic LabFlow tools, dry-run guardrails, audit events, and prompt/model tracing.
- Added production-shaped eval ladders for control parity, semantic generalization, grounded answer quality, repair planning, provider failure reporting, frozen baselines, and regression gates.
- Added enterprise-style RAG diagnostics for source conflicts, stale/retired SOP content, policy precedence, and retrieval debug traces.

## Developer Platform / Backend / Infra

- Created a VS Code workflow DSL extension skeleton with diagnostics, hover docs, validation commands, AI explanation commands, JANUS dry-run commands, eval execution, and audit viewing.
- Exposed local FastAPI routes for workflow validation, RAG, agent execution, tool calls, evals, audit events, and artifact retrieval.
- Modeled an AWS-shaped Terraform skeleton for Lambda, API Gateway, DynamoDB, S3, IAM, and CloudWatch while keeping local development independent of cloud credentials.

## Portfolio Demo

- Built a synthetic end-to-end demo that shows invalid RNA normalization/re-quant workflows blocked for missing blank and missing concentration, then a fixed workflow generating a dry-run JANUS preview with standard, split, and in-place rows.
- Documented architecture, limitations, demo walkthrough, and case study narrative with Mermaid diagrams and explicit non-production disclosures.

## STARLIMS-Style AI Platform Framing

- Demonstrated how to integrate AI into a LIMS-like developer workflow without making the LLM authoritative over lab data, readiness, or robot-facing artifacts.
- Built role-aligned portfolio evidence for RAG over domain content, grounded answer evals, agent guardrails, VS Code DSL diagnostics, local API boundaries, and AWS-shaped infrastructure.
- Created share-readiness checks and curated eval summaries so reviewers can inspect safety, grounding, provider behavior, and limitations without opening large raw JSON artifacts.
