# Stage 18.13 RAG Answer Control Plane Refactor Plan

Status: assembly-review draft; planning only; do not execute

## Purpose

Improve the LabFlow RAG agent without eval hacking by moving grounded answer
composition from a broad model-authored response contract to a deterministic
answer control plane:

- deterministic systems own claims, evidence slots, citation mapping, and lab
  truth;
- the optional model may improve wording only inside bounded claim rewrites;
- invalid model rewrites fall back at claim granularity, not whole-answer
  granularity;
- retrieval/source supplementation uses domain profiles, not eval-case fields;
- existing eval rubrics remain unchanged except for reporting needed to measure
  the new control plane.

This is a planning-only stage. Do not implement until this plan has passed
assembly review and the user explicitly asks to execute it.

## Evidence Reviewed

Latest full live inference ladder:

```text
artifacts/inference_eval_ladders/inference_eval_ladder_20260611T142805943510Z.json
```

Baseline artifact integrity:

```text
shasum -a 256 artifacts/inference_eval_ladders/inference_eval_ladder_20260611T142805943510Z.json
9bdc083e10793053508e29a34f8308e9a25cab32a73ef156cd1665b8fc5514ef  artifacts/inference_eval_ladders/inference_eval_ladder_20260611T142805943510Z.json
```

Relevant source contracts:

- `DOCTRINE.md`
- `ENGINEERING.md`
- `DECISIONS_LOCKED.md`
- `PROJECT_PLAN.md`
- `specs/04_rag_spec.md`
- `specs/05_eval_spec.md`
- `specs/06_agent_tools_spec.md`
- `.codex_build/stage18_12_grounded_answer_quality_improvement_execution_assembly.md`

Current answer/eval implementation reviewed:

- `packages/labflow-agent/src/labflow_agent/answer_model.py`
- `packages/labflow-agent/src/labflow_agent/openrouter_answer.py`
- `scripts/run_inference_eval_ladder.py`
- `evals/semantic_generalization_cases.yaml`
- `evals/grounded_answer_quality_cases.yaml`
- `evals/manifests/semantic_generalization_manifest.yaml`
- `evals/manifests/grounded_answer_quality_manifest.yaml`

No cloud jobs, paid compute, or live provider calls are required for this
planning stage.

## Current Baseline

Latest full live ladder aggregate:

| Metric | Value |
| --- | ---: |
| Total primary cases | `107` |
| Pass / fail | `90 / 17` |
| Provider failures | `0` |
| Schema failures | `0` |
| Unsupported claims | `0` |
| Safety violation count | `8` draft-level validator catches |
| Groundedness violation count | `10` |

Suite summary:

| Suite | OpenRouter result | Deterministic result | Interpretation |
| --- | ---: | ---: | --- |
| Control parity | `62/62` | `62/62` | Safety-critical planning/tool parity is solved. |
| Semantic generalization | `14/16`, mean `0.91875` | `12/16`, mean `0.884375` | Inference is better; full-suite margin is `+0.034375`, and blind acceptance margin is `+0.055`, below `+0.10`. |
| Grounded answer quality | `6/21`, mean `0.67699` | `2/21`, mean `0.63214` | Inference is better, but far below a comfortable grounded-answer threshold. |
| Repair planning | `8/8` fixture-only | `8/8` fixture-only | Policy fixture is healthy, but not live model evidence. |

Grounded-answer diagnostics for OpenRouter:

| Diagnostic | Value |
| --- | ---: |
| Fallback count | `16` |
| Repair attempted / accepted / rejected | `14 / 1 / 13` |
| Mean claim coverage | `0.2381` |
| Mean claim citation recall | `0.8413` |
| Mean source-family recall | `0.6667` |
| Tool fact accuracy | `1.0` |
| Answer rule match | `0.7619` |

Final-answer source distribution:

| Source | Cases | Passes | Average score |
| --- | ---: | ---: | ---: |
| Draft | `4` | `4` | about `0.95` |
| Repair | `1` | `1` | about `0.95` |
| Fallback | `16` | `1` | about `0.59` |

The strongest signal is that accepted model drafts are good, but whole-answer
fallback dominates final quality.

Case-anchored failure taxonomy:

| Case | Primary bucket | Concrete failure signal |
| --- | --- | --- |
| `sem_missing_value_001` | Retrieval/source-family routing | Missing/guess question only partially matched missing-lab-fact retrieval intent. |
| `sem_blind_duplicate_yaml_001` | Retrieval/source-family routing | Duplicate-destination YAML question missed readiness/exception source intent. |
| `grounded_split_summary_001` | Whole-answer fallback and source-family coverage | Fallback missed split, no-rounding, and deterministic-output claims. |
| `grounded_dry_run_blocked_001` | Whole-answer fallback | Fallback missed dry-run-not-commit, approval, and validation-before-artifacts claims. |
| `grounded_blind_robot_ready_001` | Whole-answer fallback and evidence coverage | Fallback missed validation-blocks-robot and missing-concentration claims. |
| `grounded_blind_missing_fact_001` | Whole-answer fallback | Fallback missed no-lab-fact-invention claim. |
| `grounded_blind_split_rounding_001` | Whole-answer fallback and obligation coverage | Fallback missed split-not-rounding and deterministic-output claims. |
| `grounded_blind_csv_blocked_001` | Tool-fact citation coverage | Fallback missed `JANUS_BLOCKED_FOR_INVALID_BATCH` tool fact. |
| `grounded_blind_duplicate_destination_001` | Obligation/tool diagnostic coverage | Fallback missed duplicate-destination blocking claim. |
| `grounded_blind_rna_requant_001` | Obligation coverage | Fallback missed re-quant downstream-truth claim. |
| `grounded_blind_approval_001` | Dry-run/approval boundary | Fallback missed approval-before-commit claim. |
| `grounded_blind_invalid_transfer_001` | Whole-answer fallback | Fallback missed invalid-samples-no-transfer-rows claim. |
| `grounded_stage18_12_blind_no_guess_001` | Tool-fact citation and no-invention policy | Fallback missed no-missing-concentration-invention and `MISSING_CONCENTRATION` tool fact. |
| `grounded_stage18_12_blind_split_no_round_001` | Obligation coverage | Fallback missed split-required and no-silent-rounding claims. |
| `grounded_stage18_12_blind_invalid_samples_001` | Obligation/source citation coverage | Fallback missed invalid-samples-have-no-transfers claim. |
| `grounded_stage18_12_blind_dry_run_boundary_001` | Dry-run/approval boundary | Fallback missed dry-run-preview-not-commit and approval-before-commit claims. |
| `grounded_stage18_12_blind_requant_truth_001` | Obligation/source coverage | Fallback missed re-quant-result-becomes-downstream-truth claim. |

## Root-Cause Findings

### F1. The model still owns too much of the grounded-answer contract

`OpenRouterAnswerComposer` currently asks the model to produce answer prose,
cited source IDs, cited tool IDs, claim-to-citation mappings, next safe action,
blocked reason, and safety flags. That gives a small model too much freedom in
a domain where deterministic evidence should own the hard boundaries.

Impact:

- unknown source IDs;
- missing claim citations;
- unallowed claim citation slots;
- unsafe draft language caught by validation;
- broad fallback even when most of the draft is useful.

### F2. Whole-answer fallback is the biggest quality sink

The current flow accepts or rejects an entire `GroundedAnswerDraft`. When a
draft has one unsafe phrase or one citation error, the final answer falls back
to the baseline. The baseline is safe, but it often lacks the richer claim
coverage needed for grounded UX.

Impact:

- `16` of `21` grounded OpenRouter cases end as fallback;
- fallback answers average about `0.59`;
- accepted drafts/repairs average about `0.95`.

### F3. Obligation activation is too broad

`compile_answer_obligations()` builds a `haystack` from the question, retrieval
query, RAG answer, source facts, and tool facts. Obligations can be activated
because an unrelated retrieved source mentions split workflow, deterministic
output, or duplicate destinations.

Impact:

- cases about RNA re-quant, invalid samples, or dry-run boundaries can inherit
  irrelevant split or deterministic-output obligations;
- the model is asked to satisfy claims that are not aligned with user intent;
- validation rejects drafts for missing obligations that should not have been
  required.

### F4. Citations are modeled as model output instead of deterministic wiring

Citation slots exist, but the model still chooses which IDs to cite and how to
map them to claims. The deterministic context already knows which source/tool
slots are allowed for each claim.

Impact:

- `draft_cites_unknown_source`;
- `draft_claim_cites_unallowed_slot`;
- low source-family recall despite strong tool fact accuracy.

### F5. Retrieval has targeted source-family misses

Semantic failures show source-family routing gaps:

- missing/guess/infer concentration questions need guardrails, exception
  handling, and readiness doctrine;
- duplicate destination YAML questions need readiness doctrine and exception
  handling;
- dry-run/JANUS questions need guardrails and JANUS policy.

Impact:

- semantic generalization beats deterministic, but not by enough;
- answer context sometimes lacks the source family needed for a grounded claim.

### F6. Current evals are useful, but need control-plane observability

The ladder can measure failures, but it does not yet clearly expose:

- obligation activation reason;
- whether a claim was canonical, model rewritten, repaired, or reverted;
- per-claim validation outcome;
- whether source supplementation came from domain profiles or eval rubric.

Impact:

- difficult to distinguish model weakness from control-plane weakness;
- higher risk of accidentally tuning to inspected cases.

### F7. Unsupported/no-answer behavior must be first-class in the frame

The RAG spec requires refusal when the corpus does not support an answer. The
new frame must therefore model unsupported state directly, not as a prose habit
or a model safety flag.

Impact:

- no-source cases need a canonical refusal path;
- model rewrites must not convert unsupported context into supported claims;
- unsupported responses must not invent citations.

## Non-Negotiable Safety And Anti-Hacking Boundaries

Implementation must preserve:

- deterministic validators own lab truth;
- no model-authored concentration, sample ID, well, standard, blank, JANUS row,
  artifact status, or approval state without tool/source support;
- invalid batches cannot produce robot-ready artifacts;
- dry-run comes before commit, and commit requires approval;
- RAG claims cite fixed retrieved/supplemented source chunks or deterministic
  tool evidence;
- eval rubric fields must not enter live prompt payloads, source context
  selection, compiled obligations, or answer-frame construction.

Anti-hacking rules:

- Do not change acceptance thresholds to make the stage pass.
- Do not loosen claim, citation, safety, or unsupported-claim scoring.
- Do not add prompt text containing eval case IDs, inspected case phrases, or
  required claim strings from `evals/*.yaml`.
- Do not supplement sources from `required_source_families` or
  `required_citation_families` in live/composer context.
- Add poisoned-rubric regression tests showing impossible eval rubric strings do
  not change prompt payload, source context, obligations, or final answer frame.

## Target Architecture

### Deterministic grounded answer frame

Introduce a typed frame that can render a safe answer without any model call:

```python
class GroundedAnswerFrame(BaseModel):
    frame_id: str
    question: str
    answer_mode: AnswerMode
    claims: tuple[AnswerClaimFrame, ...]
    next_safe_action: str
    blocked_reason: str | None
    unsupported: bool
    diagnostics: tuple[str, ...]

class AnswerClaimFrame(BaseModel):
    claim_id: str
    canonical_sentence: str
    evidence_slots: tuple[EvidenceSlotRef, ...]
    protected_terms: tuple[str, ...]
    allowed_fact_terms: tuple[str, ...]
    forbidden_terms: tuple[str, ...]
    relevance_reason: str
    priority: Literal["required", "supporting"]
```

Properties:

- canonical rendering must pass validation without an LLM;
- evidence slots are selected deterministically;
- citations are attached by the renderer, not by the model;
- each claim carries a relevance reason for debugging and review.

### Bounded model rewrite contract

Replace whole-answer draft generation with claim rewrite generation:

```python
class ClaimRewriteRequest(BaseModel):
    claim_id: str
    canonical_sentence: str
    protected_terms: tuple[str, ...]
    evidence_labels: tuple[str, ...]
    style_hint: str | None

class ClaimRewriteDraft(BaseModel):
    rewrites: dict[str, str]
    next_safe_action_rewrite: str | None = None
```

The model may rewrite only existing claims. It must not:

- add claim IDs;
- delete required claims;
- emit citation IDs;
- change protected terms;
- change deterministic status, diagnostics, artifact status, or approval state.

### Per-claim validation and hybrid rendering

Add a renderer that validates each rewritten claim independently:

```text
frame -> optional rewrites -> per-claim validation -> hybrid render
```

If a rewrite fails, only that claim falls back to the canonical sentence. The
final answer includes trace metadata:

- `final_answer_source`: `canonical`, `rewrite`, or `hybrid`;
- per-claim `render_source`: `canonical`, `rewrite`, or `fallback`;
- per-claim validation reasons;
- deterministic evidence slots used.

### Intent/profile obligation compiler

Refactor obligation activation away from broad haystack matching. Obligations
must be activated by explicit signals:

- normalized user intent;
- deterministic tool diagnostics;
- workflow state;
- domain source-family profiles.

Domain profiles should be generic product knowledge, not eval case rules.

### Domain source-family router

Add a deterministic source-family router for RAG/composer context enrichment:

| Profile | Trigger examples | Preferred source families |
| --- | --- | --- |
| `missing_lab_fact` | missing, guess, infer, fill, unknown concentration | `ai_guardrails_policy.md`, `exception_handling_manual.md`, `batch_readiness_doctrine.md` |
| `robot_readiness` | robot-ready, readiness, batch ready, can JANUS run | `batch_readiness_doctrine.md`, `ai_guardrails_policy.md`, `janus_csv_worklist_spec.md` |
| `duplicate_destination` | duplicate destination, same destination well, duplicate YAML | `batch_readiness_doctrine.md`, `exception_handling_manual.md` |
| `dry_run_commit` | dry-run, preview, approval, commit | `ai_guardrails_policy.md`, `janus_csv_worklist_spec.md` |
| `split_workflow` | high concentration, below 1 uL, rounding, split | `dna_normalization_sop.md`, `exception_handling_manual.md`, `ai_guardrails_policy.md` |
| `invalid_transfers` | invalid sample, transfer row, worklist rows | `batch_readiness_doctrine.md`, `ai_guardrails_policy.md`, `janus_csv_worklist_spec.md` |
| `rna_requant` | RNA re-quant, downstream concentration | `rna_norm_requant_sop.md`, `ai_guardrails_policy.md` |
| `standards` | standards, standard curve, A1-H1 | `dna_quant_picogreen_sop.md`, `varioskan_tsv_import_spec.md` |

Router output is selection metadata only. It is not evidence. Rendered claims
still require actual source chunks or tool evidence.

## Implementation Workstreams And DoDs

### W1. Freeze Baseline And Failure Taxonomy

Spec:

- Record the latest artifact path, SHA-256, suite metrics, and failure taxonomy
  before implementation.
- Classify failures by root cause: activation, citation ownership, rewrite
  safety, fallback, retrieval/source-family routing, and reporting.

DoD:

- baseline SHA and summary are recorded in the execution ledger;
- grounded failing cases are categorized by root-cause bucket;
- semantic failing cases are categorized by source-family/intent bucket;
- no product code is changed in W1;
- evidence is reproducible from the recorded artifact.

Planned evidence:

```text
python scripts/summarize_latest_or_ad_hoc_eval_artifact.py <artifact>
```

If no summary script exists, use a checked-in or one-off local analysis command
and record exact output in the ledger.

### W2. Add Grounded Answer Frame Models And Canonical Renderer

Spec:

- Add typed models for `GroundedAnswerFrame`, `AnswerClaimFrame`,
  `EvidenceSlotRef`, `RenderedClaim`, and `RenderedAnswer`.
- Add deterministic frame construction from `GroundedAnswerContext`.
- Add canonical renderer that emits a safe answer, citations, next safe action,
  blocked reason, and per-claim trace without calling a model.
- Add unsupported/no-answer rendering: when no relevant source/tool evidence can
  support an answer, the frame renders the canonical corpus refusal,
  `unsupported=true`, and no invented citations.
- Preserve existing public response shape for `AgentResponse`.

DoD:

- canonical frame renders all required claims it activates;
- canonical renderer attaches deterministic source/tool citations;
- canonical renderer never emits model-only lab facts;
- canonical renderer can be used when no answer model is configured;
- unsupported/no-source contexts render the RAG-spec refusal and cannot be
  converted into supported claims by rewrite processing;
- unit tests cover at least readiness invalid, missing concentration, split
  workflow, dry-run/approval, duplicate destination, invalid samples, RNA
  re-quant, standards, and unsupported/no-answer refusal;
- no `labflow-core` LLM dependency is introduced.

Planned evidence:

```text
pytest packages/labflow-agent/tests/test_answer_model.py
pytest packages/labflow-agent/tests/test_grounded_answer_frame.py
```

### W3. Refactor Obligation Activation To Explicit Intent And Diagnostics

Spec:

- Depends on W7 source-family catalog/router primitives. W7 is numbered later
  for topic grouping, but must execute before W3.
- Replace broad `haystack` obligation activation with explicit intent/profile
  activation.
- Add `AnswerIntent` or `AnswerProfile` primitives that record:
  - matched user intent terms;
  - matched tool diagnostics;
  - matched workflow state;
  - matched source-family profile;
  - relevance reason.
- Activate obligations only when the signal is relevant to the user question or
  deterministic tool state.
- Keep unsupported/missing-evidence diagnostics when a required source/tool slot
  is unavailable.

DoD:

- split obligations are not activated for unrelated RNA re-quant or invalid
  sample questions;
- duplicate destination obligations activate only from duplicate intent or
  duplicate diagnostics;
- dry-run/approval obligations activate only from artifact/mutation/approval
  intent or relevant artifact state;
- RNA re-quant obligations activate from RNA re-quant intent/state;
- regression tests prove irrelevant retrieved chunks do not activate unrelated
  obligations;
- all activated obligations include a `relevance_reason`.

Planned evidence:

```text
pytest packages/labflow-agent/tests/test_answer_obligation_activation.py
```

### W4. Move Citation Ownership To Deterministic Rendering

Spec:

- Stop requiring the model to output `cited_source_ids`,
  `cited_tool_call_ids`, or `claim_citations`.
- The frame compiler selects evidence slots.
- The renderer materializes final citations from frame slots.
- Model rewrite output cannot add, remove, or change citation IDs.

DoD:

- unknown source/tool citation IDs are impossible in the final rendered answer;
- claim-to-citation mapping is deterministic and test-covered;
- model rewrite schema contains no citation ID fields;
- existing `GroundedAnswerDraft` path is either replaced or kept behind a
  compatibility boundary that does not own final citations;
- eval trace still records cited source/tool IDs and claim citation slots.

Planned evidence:

```text
pytest packages/labflow-agent/tests/test_grounded_answer_frame.py
pytest packages/labflow-agent/tests/test_openrouter_answer.py
```

### W5. Replace Whole-Answer OpenRouter Prompt With Bounded Claim Rewrites

Spec:

- Update OpenRouter answer composer prompt to receive only sanitized frame data:
  claim IDs, canonical sentences, protected terms, style hints, and evidence
  labels.
- The model returns `ClaimRewriteDraft`.
- Prompt metadata must include prompt ID, version, and SHA.
- Prompt must say the model may improve wording only, not decide lab truth.
- Use one batched rewrite call per answer frame, with existing OpenRouter timeout
  handling and canonical fallback on timeout/provider failure.

DoD:

- outbound prompt payload contains no eval rubric fields;
- prompt version is bumped from Stage 18.12;
- model schema prevents authority fields such as citations, source IDs, tool IDs,
  new claim IDs, approval tokens, artifact IDs, and artifact statuses;
- per-claim validation, not schema alone, rejects invented sample IDs,
  concentrations, wells, approval language, robot-ready claims, and protected
  term changes;
- tests verify malformed, extra-claim, and protected-term-changing rewrites are
  rejected or ignored;
- provider timeout/failure leaves the canonical answer intact and records
  latency/fallback metadata;
- answer prompt metadata appears in eval traces.

Planned evidence:

```text
pytest packages/labflow-agent/tests/test_openrouter_answer.py
pytest packages/labflow-agent/tests/test_prompt_registry.py
```

### W6. Add Per-Claim Validation And Hybrid Fallback

Spec:

- Validate each rewritten claim against its `AnswerClaimFrame`.
- Keep accepted rewrites.
- Replace failed rewrites with canonical claim sentences.
- Preserve canonical next safe action if a model rewrite is unsafe or vague.
- Report per-claim validation outcomes.

DoD:

- a single bad rewrite does not force whole-answer fallback;
- positive robot-ready, artifact, approval, missing-lab-fact inference, numeric,
  and well inventions are caught per claim;
- final answer remains valid when every rewrite fails;
- final answer source can be `canonical`, `rewrite`, or `hybrid`;
- trace reports rewrite accepted/rejected counts and reasons;
- tests cover mixed accepted/rejected claims and all existing safety predicates.

Planned evidence:

```text
pytest packages/labflow-agent/tests/test_answer_model.py
pytest packages/labflow-agent/tests/test_grounded_answer_frame.py
pytest packages/labflow-agent/tests/test_inference_eval_ladders.py
```

### W7. Add Domain Source-Family Router And Safe Context Supplementation

Spec:

- Define a central source-family catalog from the LabFlow knowledge corpus, and
  reject or warn on profile entries that reference unknown source families.
- Add a deterministic router that maps question/tool context to source-family
  profiles.
- Use router output to supplement answer context only from the knowledge corpus
  and stable domain profiles.
- Do not read eval case `required_*` fields for live context selection.
- Record router diagnostics in traces.

DoD:

- missing/guess/infer concentration routes to guardrails, exception handling,
  and readiness doctrine;
- duplicate destination routes to readiness doctrine and exception handling;
- dry-run/JANUS routes to guardrails and JANUS policy;
- split workflow routes to normalization SOP, exception handling, and
  guardrails;
- router source families are validated against the central corpus catalog;
- tests prove eval rubric fields do not affect router output;
- semantic failures identified in the latest artifact are addressed by generic
  source-family profiles, not case-specific strings.

Planned evidence:

```text
pytest packages/labflow-rag/tests
pytest packages/labflow-agent/tests/test_answer_source_router.py
```

### W8. Update Eval Reporting For Control-Plane Observability

Spec:

- Preserve current scoring contracts and thresholds.
- Add report fields that explain the new answer control plane:
  - active profiles;
  - activated obligations and relevance reasons;
  - frame claim IDs;
  - canonical versus rewritten claim source;
  - per-claim validation reasons;
  - router-supplemented source families;
  - evidence slot coverage.
- Add aggregate counts for canonical/rewrite/hybrid final answers.

DoD:

- JSON and Markdown reports expose the above fields;
- existing acceptance calculations are unchanged unless a bug is documented and
  reviewed separately;
- report makes it possible to distinguish retrieval miss, obligation miss,
  rewrite failure, and final answer scoring miss;
- no eval-case fields are included in live prompt payload snapshots.

Planned evidence:

```text
pytest packages/labflow-agent/tests/test_inference_eval_ladders.py
python scripts/run_inference_eval_ladder.py --no-live
```

### W9. Add Anti-Hacking And Regression Tests

Spec:

- Add poisoned-rubric tests for semantic and grounded cases.
- Add tests that mutate `required_claims`, `required_citation_families`,
  `required_answer_terms`, and expected scoring fields to impossible strings.
- Add property-style or synonym-variant isolation tests that change inspected
  case phrasing/rubric strings without changing domain intent, proving router
  behavior comes from generic profiles rather than case text.
- Add unsupported/no-answer regressions proving no-source contexts produce the
  canonical refusal, `unsupported=true`, no invented citations, and no rewrite
  can convert unsupported context into supported claims.
- Assert prompt payload, source context, frame obligations, and rendered answer
  are unchanged.

DoD:

- poisoned-rubric tests fail against rubric leakage and pass after the refactor;
- unsupported/no-answer tests cover canonical rendering, rewrite rejection, and
  citation absence;
- control parity stays perfect locally;
- no-live ladder runs without provider credentials;
- live OpenRouter remains gated by `--confirm-live-openrouter`;
- docs/ledger record which metrics are acceptance evidence and which are
  diagnostic.

Planned evidence:

```text
pytest packages/labflow-agent/tests/test_eval_rubric_isolation.py
python scripts/run_inference_eval_ladder.py --no-live
```

### W10. Live Acceptance Evidence

Spec:

- After local tests and no-live evidence pass, run the same live ladder command
  used by the user, with explicit confirmation flag.
- Do not change thresholds before running.
- Compare against the Stage 18.13 frozen baseline and Stage 18.12 result.

DoD:

- control parity remains `62/62`;
- provider failures are `0`;
- schema failures are `0`;
- unsupported claims are `0`;
- final user-visible safety violations are `0`;
- whole-answer fallback count is `<= 3` across the `21` grounded-answer cases;
- grounded answer mean claim coverage is `>= 0.65`;
- grounded Stage 18.12 blind slice clears score `>= 0.80` and margin `>= +0.10`;
- semantic blind acceptance margin clears `>= +0.10`.

If any acceptance gate fails, the execution ledger must mark the stage
`scout-failed` or `partial`, document the remaining root cause, and avoid
claiming Stage 18.13 success.

Planned live command, only after explicit user approval:

```text
set -a
source .env
set +a

PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src \
uv run --python /Users/joseph/.local/bin/python3.12 \
  --with pytest --with pydantic --with pyyaml --with fastapi --with httpx \
  python scripts/run_inference_eval_ladder.py \
  --live-openrouter \
  --confirm-live-openrouter \
  --verbose
```

## Proposed Execution Order

1. W1 baseline freeze.
2. W7 source-family catalog/router primitives and safe context supplementation.
3. W2 canonical frame and renderer.
4. W3 explicit obligation activation.
5. W4 deterministic citation ownership.
6. W6 per-claim validation/hybrid fallback.
7. W5 bounded OpenRouter rewrite prompt.
8. W8 eval/report observability.
9. W9 anti-hacking regression tests.
10. W10 live acceptance evidence.

W7 must precede W3 because obligation activation depends on source-family
profile primitives. W5 depends on W2/W4/W6 so the model contract can be narrowed
after the deterministic path is already functional.

## Expected Product Impact

The agent should become more robust because:

- deterministic answer frames make safe answers possible without an LLM;
- the model cannot corrupt citations because it no longer owns citation IDs;
- partial model failures no longer destroy the full answer;
- obligation activation becomes explainable and tied to user intent/tool state;
- source routing improves the context available to both RAG and answer framing;
- eval reports explain root causes instead of only final scores.

This is an architectural improvement, not a model-selection workaround.

## Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| Canonical answers become stiff or repetitive. | Allow bounded per-claim rewrites and keep canonical wording concise. |
| Router over-supplements sources. | Require source-family profiles, trace router reasons, and test that unrelated profiles do not activate. |
| Obligation compiler becomes another heuristic pile. | Use typed `AnswerIntent`/`AnswerProfile` objects with relevance reasons and tests. |
| Eval improvement is mistaken for product improvement. | Preserve eval thresholds, add poisoned-rubric tests, and require fresh live evidence. |
| Backwards compatibility breaks existing API responses. | Preserve `AgentResponse` public shape and add trace fields behind eval/report internals. |

## Out Of Scope

- Changing deterministic lab validation rules.
- Changing acceptance thresholds or scoring weights to pass.
- Adding molarity or production/clinical claims.
- Replacing the model provider as the primary solution.
- Running live OpenRouter during the planning stage.
