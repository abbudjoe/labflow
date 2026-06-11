# Stage 18.15 STARLIMS Portfolio Readiness And Agent Hardening Plan

Status: plan-only; do not execute in this phase.

## Objective

Refocus LabFlow AI Studio as a portfolio project designed to impress a hiring
team evaluating a Senior AI Engineer role focused on production-grade AI inside
LIMS workflows.

This stage should turn the existing technical depth into a clear, shareable,
role-aligned proof of judgment:

- AI is useful, but deterministic validators own lab truth.
- RAG is measured, debuggable, and grounded, not a generic chatbot.
- Tool-using agents operate through controlled execution paths.
- Developer tooling is central: VS Code, workflow DSL diagnostics, and
  AI-assisted debugging are first-class demo surfaces.
- The backend and infrastructure are production-shaped while remaining
  local-first and safe to run.

## Source Inputs

Primary role source:

```text
https://starlims.applytojob.com/apply/LhJMhPf3aQ/Senior-AI-Engineer-STARLIMS-AI-Platform
```

Role themes observed on June 11, 2026:

- RAG over domain-specific and fragmented enterprise content.
- Retrieval ranking, grounding, hallucination reduction, accuracy, and
  consistency evals.
- Production AI systems with reliability, latency, model variability,
  guardrails, fallbacks, observability, prompt evolution, drift, and
  regressions.
- Agentic and tool-using systems with controlled execution paths.
- VS Code developer tooling for a custom framework and DSL.
- AWS-shaped backend services, infrastructure as code, and ownership of
  system architecture.
- Pragmatism, correctness, reliability, maintainability, and end-to-end
  ownership.

Repository doctrine sources:

- `DOCTRINE.md`
- `ENGINEERING.md`
- `DECISIONS_LOCKED.md`
- `PROJECT_PLAN.md`
- `README.md`
- `docs/case_study.md`
- `docs/stage18_14_rag_eval_hardening_plan.md`
- `.codex_build/stage18_14_rag_eval_hardening_execution_assembly.md`

## Strategic Positioning

The portfolio thesis should be:

```text
LabFlow AI Studio demonstrates how I would add AI to a regulated,
domain-heavy LIMS platform without letting the model become the source of truth.
```

The project should not be positioned as:

- a STARLIMS clone;
- a proprietary SOP reconstruction;
- a clinical or production lab system;
- a robot controller;
- a generic chatbot demo;
- a pure eval sandbox with no developer workflow.

The hiring-team story should be:

1. A workflow developer opens synthetic LabFlow workflow YAML in VS Code.
2. Deterministic diagnostics identify why the batch is not robot-ready.
3. The AI answer cites SOP/doctrine/schema sources and deterministic tool
   output.
4. The agent proposes only safe dry-run changes.
5. Deterministic validation decides whether the patch is valid.
6. Approval gates and audit events protect state-changing actions.
7. Eval reports show retrieval quality, groundedness, tool correctness,
   latency, provider behavior, and regressions.
8. The architecture maps cleanly to API, Lambda, DynamoDB, S3, IAM,
   CloudWatch, and Terraform without requiring live cloud credentials.

## Current Strengths To Preserve

- Deterministic lab engine with well, container, quantification,
  normalization, split workflow, RNA re-quant, JANUS preview, readiness, and
  audit concepts.
- RAG corpus with citation-ready synthetic SOPs, doctrine, DSL, exception, and
  guardrail docs.
- Inference eval ladder with control parity, semantic generalization,
  grounded answer quality, and repair planning.
- OpenRouter model adapter and live model evidence.
- Source-family retrieval controls, domain lexical normalizer, grounded answer
  obligations, production-gate reporting, and live repair planning evidence.
- FastAPI boundary and VS Code extension skeleton.
- Terraform skeleton for AWS-shaped deployment.
- Clear doctrine that the system is synthetic, non-clinical, and not a
  proprietary LIMS clone.

## Main Gaps To Close Before Sharing

1. The repo tells a strong technical story, but the shareable portfolio path is
   still too diffuse.
2. Many eval artifacts are large JSON files; reviewers need compact summaries,
   stable baselines, and a guided demo.
3. The VS Code path should become the centerpiece, because the target role calls
   out developer tooling and replacement of legacy IDE workflows.
4. The agent should expose its production controls more clearly: traces,
   failure taxonomy, source requirements, provider fallback, replay, and
   approval boundaries.
5. RAG should demonstrate enterprise-like problems: fragmented SOPs, source
   conflicts, stale docs, policy-vs-SOP precedence, and retrieval debugging.
6. The project needs a final share-readiness gate: no secrets, no noisy caches,
   no accidental proprietary claims, no broken demo commands.

## Workstreams

### W1. Shareable Portfolio Hygiene

Spec:

Prepare the repository so a hiring team can inspect it without local clutter,
secrets, or confusing artifacts.

Required changes:

- Audit `.gitignore` for:
  - `.env`;
  - `.codex_build` if the final public repo should not include build
    scaffolding;
  - Python caches;
  - Node modules;
  - VS Code extension build artifacts if generated;
  - Terraform local state and plugin folders;
  - large generated eval/artifact directories unless explicitly curated.
- Add or update `.env.example` with non-secret placeholders for model provider
  configuration.
- Create a curated artifact policy:
  - keep small human-readable summaries;
  - keep selected representative JSON artifacts only if they support the case
    study;
  - move noisy historical artifacts out of the shareable path or document that
    they are local-only.
- Add `docs/share_readiness_checklist.md`.
- Add a script or Make target that checks:
  - no `.env` is tracked;
  - no obvious API keys are present;
  - curated docs exist;
  - demo commands are documented;
  - latest eval summary exists.
  - claim-safety text checks pass for public-facing docs;
  - no public-facing doc implies proprietary STARLIMS access, clinical
    readiness, production LIMS status, or robot-control readiness.

DoD:

- `make portfolio-check` or equivalent passes locally.
- `.env` and local caches are ignored.
- The README points to curated artifacts, not a wall of raw JSON.
- `docs/share_readiness_checklist.md` states what is safe to publish and what
  remains local-only.
- No wording claims clinical, production, proprietary, or robot-ready status.
- Claim-safety checks are automated enough that they can run in
  `make portfolio-check`, with a short allowlist for doctrine disclaimers.

Evidence:

- `git status --ignored` or equivalent hygiene report.
- `make portfolio-check` output.
- Link to curated artifact summary.
- Claim-safety grep/checklist report.

### W2. Role Alignment Narrative

Spec:

Create a concise, explicit mapping from the project to the Senior AI Engineer
role requirements.

Required changes:

- Add `docs/role_alignment_starlims.md`.
- Include a table mapping role requirement to LabFlow evidence:
  - RAG pipelines over domain content;
  - retrieval quality, ranking, grounding;
  - eval frameworks;
  - fragmented enterprise data;
  - production AI reliability;
  - guardrails, fallbacks, observability;
  - prompt/model drift and regression tracking;
  - agent/tool-use systems;
  - controlled execution paths;
  - VS Code DSL developer tooling;
  - platform APIs and contextual knowledge;
  - AWS Lambda/API Gateway/DynamoDB/S3/Terraform shape.
- Include an "adjacent role themes" section that names what is not core to the
  demo but is understood architecturally:
  - React/Next/Tailwind frontend exposure;
  - Pinecone/vector database and vector-search scaling;
  - containerization and orchestration;
  - distributed-systems debugging;
  - explicit latency/cost/quality tradeoffs.
- Include a short "why this is not a STARLIMS clone" section.
- Include a short interview narrative:
  - problem;
  - architectural choice;
  - tradeoff;
  - evidence;
  - limitation.
- Update `README.md` and `docs/case_study.md` to link to the role-alignment
  doc without overfitting the project identity to one company.

DoD:

- Hiring-team reviewer can understand the role fit in under 5 minutes.
- Every major job-description theme maps to a concrete file, test, artifact, or
  demo command.
- Adjacent role themes are classified as implemented, represented by analogous
  project evidence, or intentionally future work.
- The doc avoids implying access to STARLIMS internals or proprietary SOPs.
- The case study still reads as generally useful AI/LIMS platform work.
- Public-facing claim-safety checks backstop reviewer judgment.

Evidence:

- Link-check or grep check for expected docs.
- Human-readable role alignment table.
- Reviewer confirms no proprietary-clone implication.
- Deterministic claim-safety check output for public-facing docs.

### W3. Five-Minute Demo Script

Spec:

Create a tight demo path that can be run live or narrated with screenshots.
The demo should center on the VS Code workflow developer experience while
remaining reproducible from CLI/API.

Required changes:

- Add `docs/demo_script_starlims_role.md`.
- Add `make demo-portfolio` or document exact commands if a Make target is not
  yet appropriate.
- The scripted demo should cover:
  1. open invalid RNA normalization/re-quant workflow YAML;
  2. show deterministic diagnostics for missing blank, missing concentration,
     duplicate destination or invalid readiness;
  3. ask the agent "Why is this batch not robot-ready?";
  4. show cited sources and deterministic `validate_batch` output;
  5. propose a dry-run patch;
  6. require approval before commit;
  7. rerun validation;
  8. generate JANUS-style dry-run preview only after validation passes;
  9. show audit event chain;
  10. show compact eval summary.
- Provide fallback CLI-only demo commands for machines without VS Code.

DoD:

- The demo can be completed in 5 to 7 minutes.
- Each step points to a concrete command, UI action, or file.
- The demo includes at least one safe refusal or blocked action.
- The demo includes citations and deterministic tool output.
- The demo does not require live model access by default, but has an optional
  live model path.

Evidence:

- Demo script document.
- Optional generated transcript under `examples/portfolio_demo/`.
- Smoke run of CLI fallback path.

### W4. Compact Eval And Evidence Reports

Spec:

Turn the large JSON-heavy eval history into a reviewer-friendly evidence
surface.

Required changes:

- Add `docs/eval_summary.md`.
- Summarize current best representative artifacts:
  - control parity;
  - semantic generalization;
  - grounded answer quality;
  - repair planning;
  - RAG retrieval-only evals;
  - live model comparison if available.
- Add compact tables:
  - pass rate;
  - safety violations;
  - provider failures;
  - schema failures;
  - unsupported claims;
  - fallback count;
  - mean groundedness;
  - semantic margin;
  - latency percentiles where available;
  - estimated provider cost where available or explicit "not measured" notes;
  - model quality/latency tradeoff summary.
- Add `scripts/summarize_portfolio_evals.py` or extend existing scripts to
  produce Markdown summaries from selected artifacts.
- Add a curated manifest such as `artifacts/portfolio_manifest.json` that names
  the artifacts considered canonical for sharing.

DoD:

- A reviewer does not need to open raw JSON to understand model/RAG quality.
- The summary links to raw artifacts for auditability.
- The summary separates deterministic baseline, frozen baseline, live model,
  fixture-only evidence, and active provider failures.
- The summary explains what pass rate is acceptable for portfolio demo versus
  production.
- The summary includes a latency/cost/quality tradeoff paragraph for the
  selected live model and deterministic fallback.
- The summary documents known residual risks.

Evidence:

- `docs/eval_summary.md`.
- Generated Markdown from selected artifacts.
- Test or smoke command for the summary script.

### W5. Frozen Baselines And Regression Gates

Spec:

Make eval comparisons stable enough to discuss in an interview. The current
`frozen_keyword_baseline` is explicit, but code-backed; future retrieval changes
could move it.

Required changes:

- Persist frozen per-case baseline scores for semantic generalization and
  grounded answer quality.
- Record baseline metadata:
  - case file hash;
  - prompt hash;
  - corpus hash;
  - retriever version;
  - model/provider identity;
  - date created;
  - acceptance rationale.
- Add a baseline rotation process:
  - when to rotate;
  - who approves;
  - what evidence must be attached;
  - how old and new baselines are compared.
- Add regression gates:
  - safety-control cases must pass at 100 percent;
  - active-provider safety/provider/schema failures must remain zero for
    shareable demo runs;
  - semantic margin must remain above threshold against frozen baseline;
  - groundedness cannot regress below the documented threshold;
  - source-family recall cannot regress for policy-critical families.

DoD:

- Eval runner can use persisted frozen baseline artifacts.
- Baseline reports clearly distinguish active deterministic parity from frozen
  UX/generalization comparison.
- Baseline rotation is documented.
- Regression failures are named and actionable.

Evidence:

- Updated baseline artifact under `evals/baselines/`.
- Updated eval runner tests.
- Passing no-live and live-smoke eval runs.

### W6. RAG Enterprise Hardening

Spec:

Demonstrate RAG behavior beyond a clean synthetic corpus by adding enterprise
knowledge-system problems common in regulated organizations.

Required changes:

- Add source conflict detection:
  - if two retrieved sources disagree on a policy-critical rule, the answer
    must say a conflict was detected and cite both.
- Add policy precedence:
  - doctrine/guardrail documents outrank SOP convenience text for AI safety
    rules;
  - schema docs outrank prose for DSL field validity;
  - deterministic tool output outranks all prose for concrete workflow state.
- Add stale-source metadata:
  - source version;
  - effective date;
  - retired or draft status;
  - retrieval penalty or warning for stale docs.
- Add fragmented SOP scenario:
  - one rule is distributed across SOP, exception manual, schema doc, and
    guardrail policy;
  - answer must synthesize only cited supported facts.
- Add retrieval debug output:
  - original question;
  - normalized concepts;
  - expanded query terms;
  - source-family requirements;
  - top-k ranks;
  - supplemented sources;
  - missing required source families.
- Add a groundedness verifier stage:
  - reject or fall back if answer claims are not supported by citations or tool
    facts;
  - expose rejection reasons in trace.

DoD:

- Conflict-case evals pass without unsupported claims.
- Stale-source tests prove the retriever warns or penalizes stale material.
- Retrieval debug view is available through CLI/API and documented.
- Groundedness verifier rejects unsupported claims deterministically.
- Policy-critical source families maintain recall.

Evidence:

- New knowledge fixtures using synthetic/non-proprietary content.
- New RAG and agent tests.
- Eval artifact showing conflict and stale-source cases.
- Demo snippet in `docs/eval_summary.md`.

### W7. Agent Production Hardening

Spec:

Make the agent feel like a production control plane rather than a prompt wrapper.

Required changes:

- Add typed action intents:
  - read-only answer;
  - validation;
  - dry-run patch proposal;
  - dry-run artifact generation;
  - approval-gated commit;
  - unsupported/refusal.
- Add explicit state transition policy:
  - read-only -> dry-run allowed;
  - dry-run -> commit requires approval token;
  - invalid validation -> artifact generation blocked;
  - missing trusted facts -> no invented patch values.
- Add replayable traces:
  - request;
  - retrieval query and source ranks;
  - selected model and prompt version;
  - tool calls and audit event IDs;
  - answer-frame obligations;
  - verifier result;
  - final response.
- Add provider fallback policy:
  - timeout;
  - schema failure;
  - unsafe plan;
  - fallback to deterministic answer composer;
  - report fallback reason.
- Add safety red-team evals:
  - invented concentration;
  - invented sample ID;
  - invented blank/standard;
  - invalid JANUS worklist;
  - commit without approval;
  - hidden state mutation;
  - prompt injection through SOP text;
  - prompt injection through workflow YAML comments.
- Add failure taxonomy:
  - retrieval miss;
  - context conflict;
  - unsupported question;
  - provider failure;
  - schema invalid model output;
  - deterministic validation failure;
  - approval missing;
  - policy violation.

DoD:

- Every state-changing path has dry-run first and approval-gated commit tests.
- Every tool call creates an audit event.
- Unsafe provider output falls back or refuses deterministically.
- Trace replay can reproduce the decision path without calling the model again.
- Red-team suite has zero safety violations.

Evidence:

- Agent tests.
- Trace fixture.
- Red-team eval artifact.
- Failure taxonomy documentation.

### W8. VS Code Developer Platform Polish

Spec:

Make the VS Code extension the most visible demo surface, because the role
explicitly emphasizes developer tooling for a custom framework and DSL.

Required changes:

- Add a guided demo workspace under `examples/vscode_demo/`.
- Improve diagnostics display:
  - missing blank;
  - missing concentration;
  - duplicate destination;
  - invalid standard location;
  - high-concentration split required;
  - invalid JANUS readiness.
- Add or polish commands:
  - validate workflow;
  - explain diagnostic;
  - ask why not robot-ready;
  - propose dry-run patch;
  - apply approved patch preview;
  - generate JANUS dry-run preview;
  - show audit events;
  - run portfolio eval summary.
- Add patch preview UX:
  - never silently edit;
  - show proposed YAML diff;
  - require explicit user action.
- Add trace/evidence panel or command:
  - show citations;
  - show deterministic tool output;
  - show audit IDs;
  - show blocked reason.
- Add extension test coverage for command wiring and diagnostic mapping.

DoD:

- A reviewer can run the VS Code demo from documented steps.
- Extension compile passes.
- Diagnostic mapping tests pass.
- AI commands degrade gracefully when local API or live model is unavailable.
- No command can commit or generate robot-facing artifacts without validation
  and approval policy.

Evidence:

- VS Code smoke test.
- TypeScript compile.
- Demo screenshots or transcript.
- API-backed command tests where practical.

### W9. API And AWS Production Shape

Spec:

Strengthen the production architecture story without requiring cloud mutation.

Required changes:

- Add `docs/api_contract.md`:
  - workflow validation;
  - RAG query;
  - agent run;
  - patch proposal;
  - JANUS dry-run preview;
  - audit event retrieval;
  - eval summary retrieval.
- Add local store interfaces that map to:
  - DynamoDB workflow state;
  - DynamoDB audit events;
  - DynamoDB eval runs;
  - S3 knowledge/artifacts/eval reports.
- Add `docs/aws_architecture_decisions.md`:
  - Lambda/API Gateway tradeoffs;
  - DynamoDB key design;
  - S3 artifact lifecycle;
  - IAM least privilege;
  - CloudWatch logging;
  - Cognito/auth as future work.
- Add a lightweight threat model:
  - secrets;
  - prompt injection;
  - artifact generation;
  - approval bypass;
  - tenant isolation as future work;
  - audit tampering.
- Keep Terraform validation local-only.
- Whitelist only local, non-mutating Terraform evidence commands:
  - `terraform -chdir=infra/terraform fmt -check`;
  - `terraform -chdir=infra/terraform init -backend=false`;
  - `terraform -chdir=infra/terraform validate`.
- Explicitly exclude `terraform plan`, `terraform apply`, `terraform destroy`,
  and any command requiring cloud credentials from the portfolio readiness gate
  unless a future turn authorizes cloud mutation.

DoD:

- API contract is documented and matches implemented routes.
- Terraform validates without backend or cloud credentials.
- Evidence uses only the whitelisted non-mutating Terraform commands.
- AWS docs explicitly separate implemented skeleton from future production
  requirements.
- Threat model identifies concrete controls and known gaps.

Evidence:

- API route smoke tests.
- `terraform -chdir=infra/terraform validate`.
- Docs cross-linked from README and case study.

### W10. Interview And Review Preparation

Spec:

Make the project easy to discuss under interview pressure.

Required changes:

- Update `.codex_build/project_quiz_questions.md` or add
  `.codex_build/project_quiz_review_stage18_15.md`.
- Add answers for questions likely to be asked:
  - Why this chunking strategy?
  - What happens when retrieval fails?
  - How do you prevent invalid JANUS output?
  - How do you measure groundedness?
  - What are the golden eval cases?
  - What breaks when source documents conflict?
  - How are prompts versioned?
  - How do you detect regressions?
  - Why is the agent read-only by default?
  - What actions require approval?
  - What is deterministic versus LLM-driven?
  - What would change before production?
  - How does this map to STARLIMS without being a STARLIMS clone?
  - What tradeoff did you make between latency, quality, and cost?
  - What would you do with real enterprise SOPs?
  - Why is there no React/Next/Tailwind app in the core demo?
  - How would you move from local retrieval to Pinecone or another vector
    database?
  - How would you containerize or orchestrate the system later?
  - How would you debug failures across VS Code, API, agent, retriever, model
    provider, and deterministic tools?
- Add `docs/resume_bullets.md` updates for the role-specific project framing.

DoD:

- There is a concise review quiz with answers.
- The answers cite project files and artifacts.
- The answers are honest about limitations.
- Resume bullets highlight production AI, RAG evals, agent guardrails,
  developer tooling, and AWS-shaped architecture.

Evidence:

- Quiz review file.
- Updated resume bullets.

## Recommended Execution Order

1. W1 Shareable Portfolio Hygiene.
2. W2 Role Alignment Narrative.
3. W4 Compact Eval And Evidence Reports.
4. W5 Frozen Baselines And Regression Gates.
5. W3 Five-Minute Demo Script.
6. W8 VS Code Developer Platform Polish.
7. W6 RAG Enterprise Hardening.
8. W7 Agent Production Hardening.
9. W9 API And AWS Production Shape.
10. W10 Interview And Review Preparation.

Rationale:

- Start by making the repo safe and understandable.
- Then create the role-specific narrative and evidence layer.
- Stabilize evals before changing demos or agent behavior.
- Polish the VS Code path before adding deeper RAG and agent complexity.
- Finish with infrastructure story and interview preparation.

## Target Portfolio Acceptance Gate

The project is ready to share for this role when:

- A fresh reviewer can run a documented demo in under 10 minutes.
- README, case study, role alignment, eval summary, and demo script are
  coherent and cross-linked.
- `make portfolio-check` passes.
- Safety-control evals pass at 100 percent.
- Active provider safety/provider/schema failures are zero for the canonical
  live smoke.
- RAG answers either cite sources or say unsupported.
- The agent cannot generate JANUS-style artifacts for invalid batches.
- Approval policy is visible in tests, docs, and demo behavior.
- The VS Code demo shows deterministic diagnostics and AI explanation.
- Terraform validates locally without cloud mutation.
- The docs clearly say synthetic, non-clinical, non-production, and not a
  proprietary LIMS clone.

## Out Of Scope For Stage 18.15 Implementation

- Real STARLIMS integration.
- Real customer, patient, clinical, or production lab data.
- Real robot execution.
- Real AWS deployment or `terraform apply`.
- Authenticated enterprise multi-tenancy.
- Paid cloud or GPU jobs.
- Production vector database deployment.
- Bioinformatics QC expansion unless separately requested.

## Risks And Guardrails

- Do not tune evals by editing expected answers to match current behavior.
- Do not add exact blind-case phrase triggers.
- Do not let live model output become authoritative over deterministic
  validation.
- Do not imply STARLIMS proprietary knowledge or internal architecture.
- Do not make live model keys or cloud credentials required for local tests.
- Do not bury important evidence in large JSON files without summaries.
- Do not broaden the product into a generic LIMS clone.

## Plan DoD

This planning stage is complete when:

- this document exists with detailed specs and DoDs for each workstream;
- the plan maps directly to the STARLIMS role themes and LabFlow doctrine;
- the plan distinguishes documentation/readiness work from implementation work;
- a matching assembly ledger exists under `.codex_build/`;
- a subagent performs spec-conformance review of the plan;
- reviewer findings are fixed or explicitly documented;
- final status is ready for user approval before implementation.
