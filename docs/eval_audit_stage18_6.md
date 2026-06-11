# Stage 18.6 Eval Audit

Date: 2026-06-10

## Scope

This audit reviewed LabFlow eval intent, cases, scoring logic, recent artifacts,
and artifact traceability. It did not implement remediation changes.

Primary evidence:

- `docs/inference_eval_ladders.md`
- `scripts/run_inference_eval_ladder.py`
- `scripts/run_model_eval_ladder.py`
- `scripts/run_model_eval_comparison.py`
- `packages/labflow-rag/src/labflow_rag/evals/runner.py`
- `evals/*.yaml`
- `evals/manifests/*.yaml`
- `artifacts/inference_eval_ladders/inference_eval_ladder_20260610T221903029223Z.json`
- `artifacts/inference_eval_ladders/inference_eval_ladder_20260610T222708095135Z.json`
- `artifacts/model_eval_ladders/model_eval_ladder_20260610T203943999093Z.json`

## Executive Summary

The eval system has a good safety-oriented foundation: deterministic golden
cases are broad, RAG retrieval has strong source coverage, fixed-context answer
composition is now separated from planner behavior, manifests protect holdouts,
and artifacts include useful hashes and diagnostics.

The main weakness is that some suite names and aggregate metrics overstate what
is actually being measured. `control_parity` inside the inference ladder does
not rerun current live OpenRouter parity. `repair_planning` is fixture-scored,
not inference-scored. `grounded_answer_quality` measures fixed-context answer
quality, but top-level pass/fail and citation metrics still lean on baseline
context rather than provider-specific answer evidence. The non-control suites
are also too small to support robust claims.

## Inventory

| Area | Count / Status | Notes |
| --- | ---: | --- |
| Golden RAG/planner cases | 40 | Covers 11 categories including batch readiness, guardrails, JANUS gating, SOP alignment, throughput, molarity exclusion. |
| Control parity tier executions | 62 | Overlapping tiers from 40 unique golden cases. Latest separate model ladder shows deterministic and OpenRouter both 62/62. |
| `semantic_generalization` cases | 6 | 2 dev, 2 regression, 2 holdout. |
| `grounded_answer_quality` cases | 3 | 1 dev, 1 regression, 1 holdout. |
| `repair_planning` cases | 3 | 1 dev, 1 regression, 1 holdout. |
| Holdout protection | Present | Manifest validation enforces holdout `tuning_allowed: false`. |
| Offline local gates | Present | `--no-live` path works and does not require OpenRouter credentials. |
| Latest live inference ladder | Partial | Control parity reports 62/62, semantic ties baseline, grounded improves from 0.517 to 0.608 with one guarded fallback, repair planning fixture passes. |
| Latest offline grounded smoke | Healthy fixture path | Baseline 0.517, fixture composer 0.825, margin +0.308, fixture fallback 0. |

## Suite Intent Versus Measurement

| Suite | Intended Measurement | Current Measurement | Audit Judgment |
| --- | --- | --- | --- |
| `control_parity` | Current inference planner must match deterministic safety-critical behavior. | In `run_inference_eval_ladder.py`, deterministic tiers are rerun and live provider metadata is shown, but current live OpenRouter is not rerun. A hardcoded prior artifact path is referenced. | Intent is valid, but inference-ladder implementation is misleading. |
| `semantic_generalization` | UX/intent generalization over paraphrased, ambiguous, low-keyword requests. | Full runtime per provider, scored by task match, unsupported match, source-family recall, tool decision, and retrieval terms. | Measures planning/intent robustness, not answer quality. Name is acceptable; docs should avoid implying prose quality. |
| `grounded_answer_quality` | Answer clarity/grounding over the same retrieved chunks and deterministic tool output. | Fixed deterministic context plus provider answer composer; guarded fallback; scores claim terms, required source families, tool terms, answer terms, next action. | Directionally correct, but citation score currently uses baseline context more than provider-cited evidence. |
| `repair_planning` | Safe dry-run patch proposals or refusals, with deterministic validation authoritative. | Fixture-generated `PatchProposal`; no live provider or model proposer participates. | Useful policy regression, but not an inference eval yet. |
| RAG eval harness | Retrieval/source/citation quality over corpus. | 40/40 retrieval-only top-k=6 tests, citation-preservation tests, no-answer behavior. | Strong retrieval coverage; answer-grounding and conflict-document evals need expansion. |

## Findings

### P0 — `control_parity` Inference Ladder Does Not Rerun Current Live Provider

Category: implementation bug / eval-validity risk.

`run_inference_eval_ladder.py` reports `control_parity` as passing 62/62, but
the suite reruns deterministic tiers only and includes current provider status
as diagnostics. It does not call the current OpenRouter provider in that suite.
The separate `model_eval_ladder_20260610T203943999093Z.json` does show live
OpenRouter 62/62, so historical evidence exists, but the current all-suite live
ladder can give a false sense that parity was rechecked.

Impact: a changed model, prompt, or adapter could regress parity while the
inference ladder still reports control parity as green.

Suggested change: make inference-ladder `control_parity` execute both
deterministic and current live provider tiers when `--live-openrouter` is set,
or rename the suite to `control_parity_reference` and clearly mark it as a
deterministic replay plus historical evidence pointer.

### P1 — Top-Level Suite Pass/Fail Can Be Baseline-Centric And Misleading

Category: implementation bug / reporting risk.

`semantic_generalization` and `grounded_answer_quality` top-level `pass_count`
and `fail_count` are derived from baseline cases, while inference scores live
inside provider details and `baseline_comparison`. This is confusing in live
reports: grounded OpenRouter improved from 0.517 to 0.608, but the suite still
shows `pass_count=0, fail_count=3` from the deterministic baseline.

Impact: readers may miss inference progress or incorrectly treat baseline
failures as provider failures.

Suggested change: report top-level `baseline_pass_count`,
`inference_pass_count`, and `primary_provider_pass_count`, or make the top-level
suite pass/fail explicitly provider-scoped.

### P1 — `repair_planning` Is Fixture-Scored, Not Inference-Scored

Category: eval-design limitation.

The suite uses `_fixture_patch_proposal()` and does not invoke an inference
repair planner. It does test dry-run/approval policy and deterministic
validation, which is valuable, but it cannot support claims that inference
proposes better repairs.

Impact: the ladder currently cannot answer whether an LLM improves repair
planning UX or patch quality.

Suggested change: rename this suite to `repair_policy_fixture` until a real
repair proposer exists, or add a fixed-context repair-composer interface and
score deterministic baseline versus inference proposals.

### P1 — Grounded Citation Score Uses Baseline Context, Not Provider-Cited Evidence

Category: eval-design limitation / grounding risk.

`grounded_answer_quality` computes `citation_alignment` from
`context.baseline_response.sources`. That verifies required source families were
available in fixed context, but not that the accepted provider draft cited the
right source IDs. Stage 18.5 now records `composer_cited_source_ids` and
`composer_cited_tool_call_ids`, which creates the raw material for a stronger
metric.

Impact: a draft could cite a valid but irrelevant source ID and still benefit
from baseline source-family alignment.

Suggested change: add provider-citation alignment over accepted draft citation
IDs, and separately report fixed-context source availability. Keep fallback on
unknown citations.

### P1 — Non-Control Suites Are Too Small For Robust Claims

Category: eval-design limitation.

`semantic_generalization` has 6 cases; `grounded_answer_quality` has 3; repair
has 3. Each has holdouts, but the sample is too small for reliable model
selection, regression detection, or nuanced claims about UX superiority.

Impact: one case can swing suite conclusions heavily; prompt tweaks can overfit
visible patterns.

Suggested change: expand to at least 20-30 cases per non-control suite with
scenario-balanced dev/regression/holdout splits, including negative controls.

### P1 — Unsupported/Hallucination Checks Are Mostly Phrase Blacklists

Category: safety coverage limitation.

Unsupported claims are checked through small phrase lists such as `valid without
validation`, `generate anyway`, and `estimate the concentration`. The validator
adds stronger numeric/well/readiness controls for answer drafts, but suite-level
hard failures still rely heavily on case-specific terms.

Impact: unsafe paraphrases can evade eval hard-fails.

Suggested change: add structured claim categories to cases, such as
`forbidden_readiness_claim`, `forbidden_artifact_claim`, `forbidden_missing_data_inference`,
and use shared guardrail detectors instead of ad hoc strings.

### P2 — Baseline Metadata Is Stale

Category: provenance/documentation issue.

`evals/baselines/inference_eval_baselines.json` references the Stage 18.2
baseline and `59/59` control parity, while the latest model ladder reports
`62/62`. Run reports recompute hashes, which is good, but the checked-in
baseline metadata no longer reflects current suite state.

Impact: reviewers may compare against outdated baselines.

Suggested change: add a baseline rotation process and update the baseline file
only when case files or scoring semantics intentionally change.

### P2 — Aggregate Counts Mix Overlapping And Non-Comparable Executions

Category: reporting risk.

Control parity reports 62 tier executions from 40 unique cases. The inference
ladder aggregate combines that with small non-control suites. The model ladder
does note overlapping tiers, but top-level aggregate counts can still read like
unique eval cases.

Impact: portfolio readers can overestimate independent coverage.

Suggested change: include `unique_case_count`, `tier_execution_count`, and
`provider_case_count` separately in aggregate summaries.

### P2 — RAG Retrieval Coverage Is Strong, But Conflict And No-Answer Cases Need More Work

Category: eval-design limitation.

RAG evals pass required source retrieval at top-k=6 for all golden cases and
test missing citations. However, there is limited direct coverage for conflicting
source chunks, stale source precedence, and unsupported answers where related
but insufficient context exists.

Impact: groundedness may look stronger than it is when the corpus contains
nearby but conflicting policy text.

Suggested change: add conflict-document fixtures and required behavior:
cite both, prefer doctrine/controlled SOP where specified, or say unsupported
when conflict cannot be resolved.

### P2 — Live Model Variance Is Not Measured

Category: model-performance limitation.

Live OpenRouter runs are single-pass. Temperature is zero, but provider/model
behavior can still vary due routing or backend changes.

Impact: small score movements can be mistaken for durable improvements.

Suggested change: add optional `--repetitions N` for live suites and report
mean, min, max, and fallback-rate variance.

### P3 — Docs Could Better Separate UX Intent From Answer Quality

Category: documentation issue.

`semantic_generalization` is sometimes discussed as UX/generalization, but it
does not judge final prose quality. `grounded_answer_quality` is the answer
quality suite.

Impact: project explanation can blur what was actually measured.

Suggested change: update docs and quiz notes to use:

- `semantic_generalization`: intent/planning UX robustness;
- `grounded_answer_quality`: cited explanatory answer quality;
- `repair_policy_fixture` or future `repair_planning`: safe patch planning.

## What Is Already Good

- Deterministic lab truth remains protected by validators and tool wrappers.
- Fixed-context answer composition prevents provider retrieval differences from
  contaminating grounded answer scoring.
- Unknown source/tool citation IDs trigger fallback.
- Parsed invalid draft citation IDs are now visible in artifacts without raw
  provider envelopes.
- Holdout manifests are validated and locked against tuning.
- RAG retrieval coverage over the current corpus is broad and currently passes.
- Local/no-live evaluation is supported and credential-free.

## Suggested Remediation Plan

### Phase 1 — Reporting Correctness

1. Fix `control_parity` in `run_inference_eval_ladder.py` so live runs execute
   the current provider or clearly rename the suite as historical reference.
2. Split top-level suite pass/fail into baseline and inference/provider
   pass/fail fields.
3. Update aggregate reporting to distinguish unique cases from tier executions.
4. Rotate `evals/baselines/inference_eval_baselines.json` after scoring changes.

Evidence gates:

- Unit tests proving live control parity calls provider when requested.
- JSON snapshot test for baseline/inference pass fields.
- No-live run remains credential-free.

### Phase 2 — Groundedness Metric Tightening

1. Score provider citation alignment using `composer_cited_source_ids` and
   `composer_cited_tool_call_ids`.
2. Keep fixed-context source availability as a separate metric.
3. Replace phrase-only unsupported checks with structured guardrail categories.
4. Add conflict-source and no-answer cases to RAG and grounded answer suites.

Evidence gates:

- Bad citation fixture fails provider-citation alignment.
- Source-available-but-not-cited case fails answer grounding.
- Conflict fixture requires cite-both/prefer-policy/unsupported behavior.

### Phase 3 — Real Repair Planning Eval

1. Rename current fixture suite or mark it explicitly as policy fixture.
2. Add a `RepairProposalAdapter` / fixed repair context if inference repair
   planning is in scope.
3. Score safe refusal quality, minimal patch correctness, validation delta,
   dry-run/approval policy, audit expectation, and lab fact invention.

Evidence gates:

- Missing concentration still safe-refuses.
- Duplicate destination patch uses only specified allowed well.
- Split workflow refusal cannot round below-minimum transfer.
- Live provider remains optional.

### Phase 4 — Case-Set Expansion

1. Expand `semantic_generalization` to 20-30 cases:
   paraphrases, ambiguity, low-keyword questions, off-domain near misses, and
   adversarial wording.
2. Expand `grounded_answer_quality` to 20-30 cases:
   validation summaries, policy-only answers, conflicting source cases, tool
   output summarization, JANUS gating, split workflow, RNA re-quant, no-answer.
3. Expand repair suite after real proposer exists.

Evidence gates:

- Manifests preserve dev/regression/holdout splits.
- Holdouts remain `tuning_allowed: false`.
- Per-category metrics are reported.

### Phase 5 — Live Variance And Gates

1. Add optional repetitions for live provider runs.
2. Add `--fail-on-threshold` for CI-friendly gating.
3. Report fallback rate confidence/variance across repetitions.

Evidence gates:

- Offline CI uses deterministic/no-live threshold gates.
- Live exploratory runs report variance but do not block local development by
  default.

## Recommended Priority Order

1. Fix `control_parity` current-provider execution/reporting.
2. Fix provider-specific pass/fail and citation-alignment reporting.
3. Clarify/rename repair fixture suite.
4. Expand grounded and semantic cases.
5. Add conflict/no-answer grounding cases.
6. Add live repetitions and threshold-gate mode.

## Quiz-Ready Answers

- Groundedness is currently measured by fixed-context source availability, tool
  fact reflection, answer-rule terms, and hard-fail guardrails. It should be
  tightened to measure provider-cited evidence directly.
- UX/generalization currently means intent and planning robustness, not prose
  quality.
- The strongest eval today is control parity in the separate model ladder
  artifact; the inference ladder's control parity should be fixed to rerun live
  provider parity.
- The most important limitation is small non-control case sets and keyword-heavy
  scoring.
- The next production-shaped improvement is provider-specific reporting with
  stronger groundedness and conflict-source tests.
