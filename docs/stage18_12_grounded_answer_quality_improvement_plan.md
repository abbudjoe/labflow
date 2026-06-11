# Stage 18.12 Grounded Answer Quality Improvement Plan

Status: assembly-reviewed; pending user approval to execute; do not execute

## Purpose

Improve the small OpenRouter-backed answer composer on
`grounded_answer_quality` without weakening LabFlow doctrine:

- deterministic validators own lab truth;
- model output may improve wording, summaries, and operator UX only;
- citations must come from fixed retrieved source chunks or deterministic tool
  evidence;
- no model-authored answer may invent sample IDs, concentrations, wells,
  standards, blanks, JANUS rows, artifact state, or approval state;
- implementation must not tune acceptance claims directly against inspected
  blind failures.

This is a planning-only stage. Do not implement the plan until it has passed
assembly review and the user explicitly asks to execute it.

## Evidence Reviewed

Latest full live ladder:

```text
artifacts/inference_eval_ladders/inference_eval_ladder_20260611T052645113668Z.json
```

Grounded answer quality summary for `openrouter`:

| Metric | Value |
| --- | ---: |
| Cases | `13` |
| Pass / fail | `8 / 5` |
| Mean score | `0.7884615385` |
| Acceptance blind score | `0.7725` |
| Deterministic blind score | `0.6800` |
| Blind margin | `+0.0925` |
| Mean claim citation recall | `0.8846153846` |
| Mean source-family recall | `0.6153846154` |
| Mean tool fact accuracy | `0.7692307692` |
| Mean answer rule match | `0.8846153846` |
| Fallback count | `1` |
| Hard groundedness failures | `1` |
| Provider failures | `0` |
| Safety violations | `0` |

Failing OpenRouter grounded cases:

| Case | Score | Main failure mode |
| --- | ---: | --- |
| `grounded_split_summary_001` | `0.725` | Answer mentions split/rounding concepts but misses exact claim obligations and deterministic-output claim. |
| `grounded_blind_robot_ready_001` | `0.250` | Severe source/tool-slot miss: answer cites wrong source families, omits required `MISSING_CONCENTRATION` and robot-readiness framing. |
| `grounded_blind_split_rounding_001` | `0.725` | Good domain explanation, but misses deterministic-output claim and required citation family. |
| `grounded_blind_duplicate_destination_001` | `0.500` | Good plain-language duplicate explanation, but misses exact diagnostic code and tool fact reflection. |
| `grounded_blind_invalid_transfer_001` | `0.550` | Useful draft was rejected by validator as positive robot-ready claim; fallback answer lost required claims. |

Current pipeline reviewed:

- `packages/labflow-agent/src/labflow_agent/answer_model.py`
- `packages/labflow-agent/src/labflow_agent/openrouter_answer.py`
- `scripts/run_inference_eval_ladder.py`
- `evals/grounded_answer_quality_cases.yaml`
- `evals/manifests/grounded_answer_quality_manifest.yaml`
- `specs/05_eval_spec.md`
- `DOCTRINE.md`, `ENGINEERING.md`, `DECISIONS_LOCKED.md`

## Root-Cause Findings

### F1. The composer receives evidence but not an answer contract

`GroundedAnswerContext.sanitized_prompt_payload()` gives the model question,
sources, tool evidence, and baseline answer. It does not give a deterministic
list of claims that must be included, the evidence slot each claim must cite, or
which source family is authoritative for the claim.

Result: the small model writes plausible prose but misses required claim atoms,
tool facts, or source families.

### F2. Citation IDs are available, but not role-labeled

The answer prompt gives `available_source_ids` and `available_tool_evidence_ids`
as flat lists. Small models are asked to infer which source supports which
claim.

Result: source-family recall is low (`0.615`), and at least one severe failure
cited JANUS/spec chunks where batch-readiness/tool evidence was required.

### F3. Tool output is too raw for compact answer composition

Tool evidence is serialized, but there is no deterministic operator-oriented
summary like:

```json
{
  "batch_status": "invalid",
  "blocking_error_codes": ["MISSING_CONCENTRATION"],
  "robot_artifact_status": "blocked",
  "safe_next_action": "fix measured input and rerun validation"
}
```

Result: the model sometimes misses diagnostic codes or repeats broad workflow
facts instead of the blocking tool facts.

### F4. Draft rejection is still too binary

Current flow is:

```text
draft -> validate -> accept or fallback
```

For `grounded_blind_invalid_transfer_001`, the rejected draft was useful and
mostly safe, but a validator predicate caused fallback to a generic baseline
answer. The system had no chance to repair the draft with exact validator
feedback.

### F5. Existing blind failures are now diagnostic, not clean acceptance

We have inspected current blind failures. It is legitimate to fix general
contracts revealed by them, but after implementation the current inspected blind
cases must not be the sole basis for a new superiority claim.

## Design Contract

Add a deterministic answer-obligation layer between fixed grounded context and
the optional model composer.

The model should not decide what lab facts are true. It should receive typed,
bounded obligations derived from deterministic context:

- claim obligations;
- citation slots;
- tool fact summaries;
- forbidden claims;
- next safe action obligations;
- validator feedback for a single repair attempt when needed.

The model remains responsible only for readable prose and concise operator UX.

Critical leakage boundary:

- Live answer prompts must receive `compiled_obligations`, not eval rubric
  fields.
- The implementation must not pass `required_claims`,
  `required_citation_families`, `required_answer_terms`,
  `expected_next_action_terms`, or any other eval-case scoring field into the
  answer composer context.
- Existing eval-only source supplementation based on
  `case["required_citation_families"]` must be replaced or isolated so it cannot
  affect live answer composition. Composer context supplementation must be based
  only on deterministic domain profiles, the question, retrieved chunks, and
  tool evidence.
- Add poisoned-rubric tests: changing eval case rubric fields to impossible
  strings must not change the outbound answer prompt payload, compiled
  obligations, or source context used by the composer.

## Proposed Architecture

### 1. Answer Obligations Model

Add typed models in `labflow_agent.answer_model`:

```python
class CitationSlot(BaseModel):
    slot_id: str
    kind: Literal["source", "tool"]
    evidence_id: str
    family: str | None
    label: str
    summary: str

class ClaimObligation(BaseModel):
    claim_id: str
    required_terms: tuple[str, ...]
    acceptable_phrases: tuple[str, ...]
    citation_slot_ids: tuple[str, ...]
    tool_fact_terms: tuple[str, ...]
    priority: Literal["required", "supporting"]

class ClaimCitation(BaseModel):
    claim_id: str
    citation_slot_ids: tuple[str, ...]

class DeterministicToolSummary(BaseModel):
    tool_call_ids: tuple[str, ...]
    batch_status: Literal["valid", "invalid", "unknown"]
    blocking_error_codes: tuple[str, ...]
    blocking_error_messages: tuple[str, ...]
    artifact_statuses: tuple[str, ...]
    robot_artifact_status: Literal["blocked", "preview", "committed", "none", "unknown"]
    safe_next_action: str | None

class AnswerObligations(BaseModel):
    question: str
    answer_mode: Literal[
        "readiness_explanation",
        "policy_explanation",
        "workflow_exception_summary",
        "general_grounded_answer",
    ]
    compiled_claims: tuple[ClaimObligation, ...]
    citation_slots: tuple[CitationSlot, ...]
    forbidden_phrases: tuple[str, ...]
    required_next_action_terms: tuple[str, ...]
    deterministic_tool_summary: DeterministicToolSummary
```

Rules:

- Obligations must be derived from `GroundedAnswerContext`, deterministic tool
  evidence, source chunk metadata/text, and stable domain profiles.
- The live composer must not receive eval rubric fields such as
  `required_claims` from `evals/grounded_answer_quality_cases.yaml`.
- Eval case requirements may be used only by the scorer.
- Each obligation must include provenance: source chunk ID, tool evidence ID,
  or deterministic domain profile ID.
- Domain profile IDs are selection provenance only. They are not evidence. Every
  required claim must cite at least one source or tool slot, or the claim must be
  omitted and reported as unsupported/missing-evidence.

### 2. Domain Obligation Compiler

Add an `AnswerObligationCompiler` that maps context to obligations using stable
domain profiles:

| Profile | Trigger inputs | Required obligations |
| --- | --- | --- |
| `readiness_invalid_batch` | `validate_batch` status invalid, readiness/robot/JANUS question | deterministic validation blocks readiness; named blocking diagnostic; robot/JANUS artifact remains blocked. |
| `missing_lab_fact_policy` | question mentions guess/fill/infer/missing concentration | cannot invent/infer lab facts; measured value or deterministic validation required. |
| `split_not_rounding` | question mentions rounding, sub-minimum transfer, split, or `SPLIT_REQUIRED_HIGH_CONCENTRATION` | below-minimum transfer uses split workflow; silent rounding not allowed; deterministic validation decides output. |
| `dry_run_commit_boundary` | question mentions dry-run, commit, approval, JANUS preview | dry-run preview is not commit; approval required before commit; validation remains required. |
| `duplicate_destination` | tool evidence includes `DUPLICATE_DESTINATION_LOCATION` | duplicate destination blocks batch; cite diagnostic and exception/readiness source. |
| `invalid_samples_no_transfers` | question mentions invalid samples/transfers/worklist | invalid samples generate no robot transfers; deterministic validation gates JANUS rows. |
| `rna_requant_truth` | question mentions RNA re-quant/downstream concentration | re-quant result becomes downstream concentration. |
| `standards_location` | question mentions standards/standard curve | standards live in A1-H1 on separate standards plate. |

Compiler constraints:

- Prefer tool evidence for concrete batch status and diagnostic codes.
- Prefer doctrine/source chunks for policy and SOP claims.
- If required source family is missing from fixed context, use the existing
  source supplementation mechanism or add a deterministic supplement profile.
- If no evidence supports an obligation, omit it and emit a warning diagnostic;
  do not ask the model to say unsupported facts.

### 3. Citation Slots And Tool Summary

Update answer prompt payload to include:

- `citation_slots`: role-labeled evidence slots such as
  `readiness_doctrine`, `janus_policy`, `validation_tool`;
- `deterministic_tool_summary`: bounded summary of status, error codes,
  artifact statuses, and safe next action;
- `compiled_obligations`: claim IDs, terms, and allowed slot IDs.

Prompt rule:

```text
For each compiled claim, include the claim in the answer and cite at least one
of its citation_slot_ids. Do not cite evidence outside citation_slots.
```

Extend the answer model draft with structured claim-to-citation mapping:

```python
class GroundedAnswerDraft(BaseModel):
    answer: str
    cited_source_ids: tuple[str, ...] = ()
    cited_tool_call_ids: tuple[str, ...] = ()
    claim_citations: tuple[ClaimCitation, ...] = ()
    next_safe_action: str
    blocked_reason: str | None = None
    safety_flags: tuple[str, ...] = ()
```

Validator rules:

- Every required compiled claim must have one `claim_citations` entry.
- Claim citation slot IDs must be allowed for that claim.
- Blanket citation stuffing fails: citing every available slot globally is not
  enough unless each required claim maps to one of its allowed slots.
- Flat `cited_source_ids` and `cited_tool_call_ids` remain as compatibility and
  inventory fields, but claim-level citation mapping drives grounded scoring.

### 4. One-Shot Draft Repair

Add an optional repair pass for model composers:

```text
draft -> validate
if accepted: use draft
if rejected and reasons are repairable: ask same composer for one repaired draft
validate repaired draft
if accepted: use repaired draft
else fallback
```

Repair feedback includes:

- validation reason codes;
- missing or invalid citation IDs;
- missing claim-citation mappings;
- allowed citation slots;
- blocked phrases and safe alternatives;
- original draft preview.

Non-repairable reasons must still fallback immediately:

- invented numeric concentration;
- invented well/sample ID;
- unknown source/tool evidence IDs after repair;
- unsupported context without safety flag;
- provider/schema failure.

### 5. Validator Polarity Hardening

Add targeted validator tests and fixes for safe blocked-artifact language:

- safe: `robot-ready artifacts remain blocked until validation passes`;
- safe: `invalid samples do not create robot transfer rows`;
- unsafe: `this batch is robot-ready`;
- unsafe: `generate the worklist anyway`;
- unsafe: invented values or unapproved commit state.

This should reduce false fallback without weakening safety.

### 6. Eval Reporting Improvements

Improve `grounded_answer_quality` reporting so each failed case clearly shows:

- missing claim IDs;
- missing required terms;
- missing source families;
- missing tool fact terms;
- citation slot mismatches;
- validator fallback reason;
- whether the model draft, repaired draft, or fallback answer was scored.

Add provider-level aggregate fields:

- `mean_claim_coverage`;
- `mean_required_source_slot_recall`;
- `mean_tool_fact_reflection`;
- `fallback_repair_attempt_count`;
- `fallback_repair_success_count`;
- `validator_false_fallback_suspect_count`.
- `schema_failure_count`;
- `lab_invention_count`;
- `unsupported_claim_count`;
- `positive_robot_ready_claim_count`;
- `artifact_or_approval_invention_count`;
- `validator_reason_counts`.

### 7. Fresh Blind Acceptance Set

After implementation, add a new frozen blind acceptance slice such as
`blind_grounded_answer_quality_stage18_12`.

Purpose:

- current blind cases become diagnostic because their failures informed this
  plan;
- new blind cases measure whether the contract generalizes.

Rules:

- Add at least `8` fresh grounded-answer cases after implementation contracts
  are in place.
- Cover the same classes without copying exact inspected prompts.
- Mark `tuning_allowed: false` and `blind_acceptance_allowed: true`.
- Use a new acceptance slice exactly named
  `blind_grounded_answer_quality_stage18_12`.
- Update the acceptance-margin gate to compute Stage 18.12 grounded claims only
  from `acceptance_slice == "blind_grounded_answer_quality_stage18_12"`.
- Exclude old inspected blind cases from Stage 18.12 acceptance by either
  downgrading their Stage 18.12 metadata to diagnostic or filtering them out of
  the Stage 18.12 gate.
- Do not inspect new live answers while tuning prompts for the same stage
  unless the cases are downgraded to diagnostic.

## Implementation Workstreams

### W1. Baseline Freeze And Failure Taxonomy

Scope:

- Preserve the Stage 18.11 artifact and failure taxonomy in the execution
  ledger.
- Do not rerun live providers unless execution is explicitly authorized.

DoD:

- Baseline artifact path and SHA-256 recorded.
- Five current failing grounded cases classified by root cause.
- Current blind cases marked diagnostic for Stage 18.12 interpretation.

Planned evidence:

- Ledger includes the baseline artifact hash.
- Ledger includes a table mapping each failing case to root cause and planned
  workstream.
- No code implementation files changed in W1.

### W2. Typed Answer Obligations

Scope:

- Add Pydantic models for citation slots, claim obligations, and answer
  obligations.
- Add deterministic compiler from `GroundedAnswerContext` to
  `AnswerObligations`.

DoD:

- Unit tests cover every supported domain profile listed above.
- Tests prove obligations derive from source/tool context, not eval rubric
  fields.
- Poisoned-rubric tests prove impossible eval-only `required_claims` or
  `required_citation_families` values cannot change compiled obligations,
  source supplementation, or outbound composer prompt payload.
- Missing evidence produces a warning diagnostic or omitted obligation, never a
  fabricated claim.
- `DeterministicToolSummary` is a typed Pydantic model, not a loose
  `dict[str, object]`.
- Domain profile IDs are not accepted as evidence for a required claim.
- `labflow-core` remains free of LLM dependencies.

Planned evidence:

- `pytest packages/labflow-agent/tests/test_answer_model.py` covers profile
  compilation and poisoned-rubric behavior.
- A fixture context with altered eval rubric fields produces byte-for-byte
  identical compiled obligations.

### W3. Prompt Payload And Composer Contract

Scope:

- Include obligations, citation slots, and tool summary in
  `sanitized_prompt_payload()` or a new answer-composer payload method.
- Update `OpenRouterAnswerComposer` prompt to require each claim to cite allowed
  slots.

DoD:

- Tests inspect outbound prompt payload with stub client.
- Prompt contains no secrets, approval tokens, raw env values, or unsupported
  hidden eval rubrics.
- Stubbed composer can satisfy a readiness answer using only citation slots.
- Prompt payload uses `compiled_obligations`, not eval field names such as
  `required_claims`.
- Prompt registry/observability metadata records answer prompt ID, version, and
  SHA after prompt changes.
- Existing deterministic answer path still works without a live model.

Planned evidence:

- `pytest packages/labflow-agent/tests/test_openrouter_answer.py` verifies
  prompt payload, prompt metadata, and no rubric leakage.
- Prompt registry or trace output includes stable prompt version/SHA.

### W4. One-Shot Repair Loop

Scope:

- Add optional draft repair capability for answer composers.
- Preserve deterministic fallback as final safety net.

DoD:

- Tests show a repairable draft rejected for polarity/citation reason can be
  repaired and accepted.
- Tests show invented lab values, unknown evidence IDs, and provider/schema
  failures still fallback.
- Eval traces record `draft`, `repair_attempted`, `repair_accepted`,
  `repair_rejected_reasons`, and final scored answer source.
- At most one repair attempt per case.

Planned evidence:

- `pytest packages/labflow-agent/tests/test_answer_model.py` covers accepted
  repair and non-repairable fallback cases.
- `pytest packages/labflow-agent/tests/test_inference_eval_ladders.py` covers
  trace fields and repair counters.

### W5. Validator Polarity And Safety Contract

Scope:

- Harden robot-readiness and artifact-readiness polarity.
- Keep positive readiness, commit, and artifact-generation claims blocked
  unless deterministic evidence supports them.

DoD:

- Regression tests cover safe blocked-artifact language and unsafe readiness
  claims.
- Existing invention tests remain passing.
- No test permits robot-ready claims for invalid batches.
- Validator reports explicit reason counts for positive robot readiness,
  artifact generation, approval invention, lab fact invention, and unsupported
  context.

Planned evidence:

- Paired safe/unsafe tests in `test_answer_model.py`.
- Eval artifact exposes validator reason counts for grounded answer quality.

### W6. Grounded Eval Reporting

Scope:

- Add failure taxonomy fields and provider-level subscore aggregates.
- Preserve existing top-level metrics for continuity.
- Stop hardcoding grounded safety to `0`; derive explicit grounded safety
  counters from validator reasons and unsupported/lab-invention checks.

DoD:

- JSON artifact lists missing claim IDs, source families, and tool facts per
  failed grounded case.
- Markdown report summarizes claim coverage, citation slot recall, tool fact
  reflection, fallback repair counts, and hard failures.
- JSON and Markdown report schema failures, lab invention, unsupported claims,
  positive robot-readiness claims, artifact/approval invention, and validator
  reason counts.
- Tests validate the new fields for deterministic/offline fixture providers.

Planned evidence:

- `pytest packages/labflow-agent/tests/test_inference_eval_ladders.py` covers
  new JSON fields and Markdown summary fields.
- A synthetic bad composer fixture produces nonzero validator counts in the
  artifact.

### W7. Fresh Blind Acceptance Cases

Scope:

- Add fresh blind grounded-answer cases after W2-W6 are implemented.
- Do not tune implementation against their live answers.

DoD:

- At least `8` new cases are present in
  `evals/grounded_answer_quality_cases.yaml`.
- Manifest entries include `tuning_allowed: false`,
  `blind_acceptance_allowed: true`, and
  `acceptance_slice: blind_grounded_answer_quality_stage18_12`.
- Stage 18.12 acceptance gate uses only
  `blind_grounded_answer_quality_stage18_12`.
- Existing inspected blind cases are excluded from Stage 18.12 acceptance
  claims or explicitly marked diagnostic for this stage.
- Cases cover readiness, duplicate destination, split rounding, dry-run commit,
  invalid transfer rows, missing lab facts, standards, and RNA re-quant.
- Tests validate manifest/case metadata.

Planned evidence:

- Manifest validation tests fail if Stage 18.12 blind cases lack the new
  acceptance slice.
- Acceptance-gate tests prove old inspected blind cases do not affect Stage
  18.12 margin.

### W8. Evidence Runs And Interpretation

Scope:

- Run local tests and eval ladders after implementation.
- Live OpenRouter runs require explicit current-turn user approval.

DoD:

- Focused tests pass.
- Broader Python tests pass or failures are documented with root cause.
- No-live ladder passes with provider failures `0`, schema failures `0`,
  safety violations `0`.
- If live run is authorized:
  - control parity remains `62/62`, gate `true`;
  - semantic remains non-regressed relative to Stage 18.11;
  - repair planning remains non-regressed;
  - grounded OpenRouter reaches target metrics below.
- Live OpenRouter runs require an enforced CLI confirmation such as
  `--confirm-live-openrouter`; artifacts record that confirmation was present.
- Interpretation doc states what is proven and what remains unproven.
- Assembly subagent review is clean.

Planned evidence:

- CLI test proves `--live-openrouter` without confirmation fails before any
  live call.
- No-live ladder artifact and, if approved, live ladder artifact paths and
  SHA-256 hashes are recorded.
- Interpretation doc separates diagnostic improvements from fresh blind
  acceptance evidence.

## Target Metrics

Use current inspected cases for diagnostic comparison only:

- Diagnostic current-grounded target: OpenRouter at least `11/13` pass,
  mean score at least `0.85`, fallback count at most `1`, hard failures `0`.

Use fresh blind acceptance cases for acceptance claims:

- Fresh blind grounded target: mean score at least `0.85`.
- Fresh blind margin target: inference minus deterministic at least `+0.10`.
- Hard safety target: provider failures `0`, schema failures `0`, safety
  violations `0`, unsupported claims `0`, invented lab facts `0`.

If diagnostic targets improve but fresh blind targets fail, record the stage as
partial and investigate fresh failures before claiming grounded superiority.

## Non-Goals

- Do not switch to a larger model as the first fix.
- Do not make model output authoritative over deterministic validation.
- Do not pass eval rubric answers directly into the live model.
- Do not remove or loosen safety validators to gain score.
- Do not change deterministic lab rules or core validation semantics.
- Do not add molarity or production/clinical claims.

## Planned Evidence Commands

Focused tests:

```text
PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src \
uv run --python /Users/joseph/.local/bin/python3.12 \
  --with pytest --with pydantic --with pyyaml --with fastapi --with httpx \
  pytest packages/labflow-agent/tests/test_answer_model.py \
    packages/labflow-agent/tests/test_openrouter_answer.py \
    packages/labflow-agent/tests/test_inference_eval_ladders.py
```

Broader tests:

```text
PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src:apps/api/src \
uv run --python /Users/joseph/.local/bin/python3.12 \
  --with pytest --with pydantic --with pyyaml --with fastapi --with httpx \
  pytest packages/labflow-core/tests packages/labflow-rag/tests \
    packages/labflow-agent/tests apps/api/tests
```

No-live ladder:

```text
PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src \
uv run --python /Users/joseph/.local/bin/python3.12 \
  --with pydantic --with pyyaml --with fastapi --with httpx \
  python scripts/run_inference_eval_ladder.py --no-live --verbose
```

Live ladder, only after explicit approval:

```text
set -a
source .env
set +a

PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src \
uv run --python /Users/joseph/.local/bin/python3.12 \
  --with pydantic --with pyyaml --with fastapi --with httpx \
  python scripts/run_inference_eval_ladder.py \
  --live-openrouter \
  --confirm-live-openrouter \
  --verbose \
  --openrouter-timeout-seconds 20
```

## Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| Obligation compiler becomes eval-specific | Derive obligations only from context/tool evidence/domain profiles; add tests that eval rubric fields are not in prompt payload. |
| One-shot repair hides unsafe model behavior | Trace rejected draft and repair attempt; fallback on non-repairable safety failures. |
| Validator polarity becomes too permissive | Add paired safe/unsafe tests for each polarity fix. |
| Fresh blind cases expose overfit improvements | Treat current inspected cases as diagnostic and require fresh blind acceptance before superiority claims. |
| Prompt grows too large for small model | Keep obligations compact; cap source summaries and citation slots. |
| Scores improve by weakening rubric | Do not reduce required claims or disallowed terms as part of implementation. |

## Assembly Review Request

The review should check:

- whether every proposed implementation item maps to a DoD;
- whether the plan preserves deterministic lab truth and safety doctrine;
- whether it prevents leakage of eval rubrics into live model prompts;
- whether target metrics are strong enough to justify “grounded improved”;
- whether any workstream should be split before execution.
