# Stage 18.6 Eval Audit And Remediation Plan

Date: 2026-06-10

This audit reviews the current LabFlow eval system after the Stage 18.x model
adapter and inference-ladder work. It is intentionally an audit and plan only:
no eval behavior is changed in this stage.

## Scope And Evidence

Authoritative inputs:

- `DOCTRINE.md`
- `ENGINEERING.md`
- `docs/inference_eval_ladders.md`
- `scripts/run_inference_eval_ladder.py`
- `scripts/run_model_eval_ladder.py`
- `scripts/run_model_eval_comparison.py`
- `packages/labflow-rag/src/labflow_rag/evals/runner.py`
- `evals/*.yaml`
- `evals/manifests/*.yaml`
- recent artifacts under `artifacts/inference_eval_ladders/` and
  `artifacts/model_eval_ladders/`

Evidence inspected:

- Latest live model ladder:
  `artifacts/model_eval_ladders/model_eval_ladder_20260610T203943999093Z.json`
- Latest live inference ladder:
  `artifacts/inference_eval_ladders/inference_eval_ladder_20260610T221903029223Z.json`
- Local no-live grounded-answer smoke:
  `artifacts/inference_eval_ladders/inference_eval_ladder_20260610T222708095135Z.json`

No live OpenRouter run, cloud job, paid compute, or production resource mutation
was performed for this audit.

## Eval Inventory

| Eval surface | Case source | Current size | Claimed target | Current status |
| --- | --- | ---: | --- | --- |
| RAG golden eval | `evals/golden_questions.yaml` | 40 unique cases | Retrieval, citation, answer-term, and suggested-tool correctness over corpus docs | Useful retrieval regression surface, but groundedness is mostly proxy-based |
| Model eval ladder | `evals/golden_questions.yaml` | 62 overlapping tier executions across 40 unique cases | Deterministic vs live planner/tool-call parity on safety-critical golden cases | Latest live artifact shows 62/62 deterministic and 62/62 OpenRouter pass |
| Inference `control_parity` | `evals/golden_questions.yaml` | 62 overlapping tier executions across 40 unique cases | Inference must match deterministic safety behavior | Current runner only reruns deterministic inside this suite and links stale live evidence |
| Inference `semantic_generalization` | `evals/semantic_generalization_cases.yaml` | 6 cases | Paraphrase/ambiguous/low-keyword intent generalization | Measures task/source/tool/retrieval-intent matching, not answer quality |
| Inference `grounded_answer_quality` | `evals/grounded_answer_quality_cases.yaml` | 3 cases | Better cited explanations from the same retrieved chunks/tool output | Good fixed-context shape; scoring still partly measures context quality rather than composed citation quality |
| Inference `repair_planning` | `evals/repair_planning_cases.yaml` | 3 cases | Safe dry-run patch proposals and safe refusals | Fixture-only today; it does not evaluate a live inference repair proposer |

Manifest policy:

- `control_parity` has one manifest entry for the existing ladder evidence.
- `semantic_generalization` has 2 dev, 2 regression, and 2 holdout cases.
- `grounded_answer_quality` has 1 dev, 1 regression, and 1 holdout case.
- `repair_planning` has 1 dev, 1 regression, and 1 holdout case.
- Manifest validation enforces split names and requires holdout cases to have
  `tuning_allowed: false`, but holdouts are still visible in the repository.

## Recent Results

Latest live model ladder:

| Provider | Tier executions | Pass | Fail | Errors | Missing required tool calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| deterministic | 62 | 62 | 0 | 0 | 0 |
| openrouter | 62 | 62 | 0 | 0 | 0 |

Latest live inference ladder:

| Suite | Cases | Pass | Fail | Baseline score | Inference score | Margin | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| control_parity | 62 | 62 | 0 | 1.000 | n/a | n/a | Deterministic-only inside this runner |
| semantic_generalization | 6 | 5 | 1 | 0.883 | 0.883 | 0.000 | Inference did not beat deterministic |
| grounded_answer_quality | 3 | 0 | 3 | 0.517 | 0.608 | +0.092 | OpenRouter improved but failed the grounded gate because one live draft fell back |
| repair_planning | 3 | 3 | 0 | 1.000 | n/a | n/a | Fixture-only |

Local no-live grounded-answer smoke:

| Suite | Baseline score | Fixture composer score | Margin | Note |
| --- | ---: | ---: | ---: | --- |
| grounded_answer_quality | 0.517 | 0.825 | +0.308 | Validates fixture/scoring plumbing, not live model quality |

## What The Current Evals Do Well

- The deterministic lab engine remains the safety source of truth.
- Golden cases cover the main doctrine categories: batch readiness, blank and
  standards rules, split workflow, in-place normalization, RNA requant,
  SOP alignment, JANUS gating, ancestry, molarity exclusion, guardrails, and
  throughput.
- The model ladder now records provider errors and does not collapse them into
  vague `OpenRouterError` messages.
- The grounded-answer path composes over a fixed deterministic context, which is
  the right shape for separating retrieval/tool evidence from answer style.
- The answer-draft validator blocks unknown citations and unsafe robot-readiness
  claims before returning a live-model answer.
- Artifacts include case-file hashes, manifest hashes, provider metadata,
  fallback reasons, cited source ids, and cited tool evidence ids.

## Findings

### EVAL-AUDIT-001: `control_parity` does not run the live provider

Severity: high

Category: implementation bug / unfair comparison

The inference ladder documentation says `control_parity` answers whether the
inference planner matches deterministic safety behavior. In
`scripts/run_inference_eval_ladder.py`, `_run_control_parity` always calls
`run_model_eval_comparison._run_provider("deterministic", ...)` for every tier.
It never runs the live OpenRouter provider in this suite. The report then stores
OpenRouter metadata under `provider_diagnostics`, but the suite score and pass
counts are deterministic-only.

The same suite links a hardcoded stale parity artifact:
`artifacts/model_eval_ladders/model_eval_ladder_20260610T185121008242Z.json`.
The latest audited live parity artifact is
`artifacts/model_eval_ladders/model_eval_ladder_20260610T203943999093Z.json`.

Impact: current inference-ladder aggregate pass counts can imply live
control-parity confidence that was not produced by that command.

### EVAL-AUDIT-002: suite-level pass/fail counts are baseline-centric

Severity: high

Category: implementation bug / reporting risk

`semantic_generalization` and `grounded_answer_quality` put live-provider scores
under `suite_metrics.providers` and `baseline_comparison`, but top-level
`pass_count` and `fail_count` are computed from the deterministic baseline cases.
The aggregate report then sums these top-level fields.

Impact: the headline aggregate can obscure the actual provider under test. A
live provider can regress while the top-level aggregate still looks mostly green.

### EVAL-AUDIT-003: `repair_planning` is fixture-only

Severity: high

Category: eval-design limitation

The repair-planning suite claims to measure safe dry-run patch proposals and
safe refusals. The current implementation uses `_fixture_patch_proposal(case)`
and does not run an inference repair proposer. It is a useful deterministic
policy and validator fixture, but it does not answer whether an inference agent
can propose better safe patches.

Impact: the current 3/3 repair result should not be described as model repair
planning quality.

### EVAL-AUDIT-004: grounded citation scoring measures context more than composer citations

Severity: medium-high

Category: eval-design limitation

`grounded_answer_quality` correctly records `composer_cited_source_ids` and
`composer_cited_tool_call_ids`, but `claim_citation_alignment` is computed from
the fixed deterministic context sources, not from the composer cited ids. The
validator prevents unknown citations, which is valuable, but accepted drafts are
not directly scored on whether they cited the required source families.

Impact: a composer can get citation-alignment credit because the context had
the right source family, even if its own citation selection is weak.

### EVAL-AUDIT-005: non-control inference suites are too small

Severity: medium

Category: eval-design limitation / statistical weakness

The semantic suite has 6 cases, grounded answer quality has 3 cases, and repair
planning has 3 cases. That is enough for smoke tests and prompt-debugging, but
not enough to claim robust model superiority. With three grounded cases, one
fallback changes the conclusion.

Impact: current live results are useful directional signals, not strong
evidence that inference beats deterministic on language/UX tasks.

### EVAL-AUDIT-006: several scoring rules are keyword-gameable

Severity: medium

Category: eval-design limitation

The RAG runner uses substring checks for required and disallowed answer terms.
The semantic suite scores retrieval intent by matching expected terms in the
retrieval query or answer. Grounded answer claim coverage and next-safe-action
quality also use term recall.

Impact: a model or prompt can satisfy several metrics by repeating magic words
without producing a better, clearer, or safer answer.

### EVAL-AUDIT-007: unsupported-claim detection is narrow

Severity: medium

Category: safety metric gap

The RAG eval currently records `unsupported_claim_count=0` for every case. The
inference grounded suite checks a short blacklist such as `valid without
validation`, `generate anyway`, and `estimate the concentration`, plus per-case
disallowed terms. The readiness-polarity helper is a good targeted improvement,
but polarity handling is still narrow: it mainly protects explicit negated vs
unnegated robot-readiness phrases and does not generalize to every way a model
could imply readiness, validation success, approval, or worklist generation.
Unsupported-claim detection therefore remains incomplete.

Impact: the evals can miss hallucinated but differently phrased lab claims.

### EVAL-AUDIT-008: baseline and evidence pointers are stale

Severity: medium

Category: provenance / artifact hygiene

`evals/baselines/inference_eval_baselines.json` still points at the
`20260610T185121008242Z` model ladder and records 59/59 overlapping tier
executions. The current golden ladder has 62 overlapping tier executions in the
latest live artifact.

Impact: future readers can confuse old baseline evidence with the latest eval
contract.

### EVAL-AUDIT-009: exploratory commands do not enforce gates

Severity: medium

Category: CI and release-process gap

The model eval comparison explicitly reports
`gate_policy: exploratory_report_only`, and nonzero failures do not fail the
command. That is reasonable for live-model exploration, but there is no separate
strict mode for release gates.

Impact: regressions can be visible in artifacts but not enforced by automation.

### EVAL-AUDIT-010: holdouts are labeled, not hidden

Severity: low-medium

Category: eval-design limitation / leakage risk

The manifest split metadata is useful, but holdout cases live in the repository
beside dev and regression cases. For a portfolio project this is acceptable,
but it is not equivalent to a blind holdout set.

Impact: holdout performance should not be presented as unbiased production-like
generalization evidence.

### EVAL-AUDIT-011: live model variance is not measured

Severity: low-medium

Category: model-performance limitation

Live model results are single-run snapshots. The artifacts record latency and
provider metadata, but they do not record repeated trials, confidence intervals,
or pass-rate variance by model.

Impact: small score differences, especially on 3-case suites, are not reliable
enough to justify strong conclusions.

### EVAL-AUDIT-012: readiness polarity is a current explicit risk class

Severity: medium

Category: safety metric gap / answer-quality risk

LabFlow's doctrine depends on careful negative claims: "not robot-ready" is safe
when validation blocks a batch, while "robot-ready" is unsafe unless the
deterministic validator supports it. The current eval code has special handling
for some negated readiness phrases, but that handling is intentionally narrow
and phrase-based.

Impact: answer-quality evals can over- or under-penalize readiness statements
when the model uses unusual phrasing, double negatives, or indirect claims such
as "nothing prevents worklist generation."

## Interpretation Of Current Results

The latest live model ladder is a positive control-parity result: OpenRouter and
deterministic both passed 62/62 overlapping golden tier executions in the latest
model ladder artifact. That says the live planner can follow the safety-critical
tool/unsupported contract for the current golden cases.

It does not yet prove that the inference-powered agent is better overall. The
latest live inference ladder shows:

- semantic generalization: inference tied deterministic, 0.883 vs 0.883;
- grounded answer quality: inference improved, 0.608 vs 0.517, but failed the
  grounded gate because one live draft triggered a robot-readiness fallback;
- repair planning: no live inference model was evaluated.

The fair project claim today is:

> LabFlow has deterministic safety parity evidence for the live planner on the
> golden control ladder, plus early evidence that a live answer composer can
> improve grounded explanations. The eval ladder still needs reporting fixes,
> larger language/UX case sets, composer-citation scoring, and a real inference
> repair-planning path before claiming robust model superiority.

## Suggested Change Plan

### P0: fix control-parity reporting and enforcement

Goal: `control_parity` must either run the provider under test or explicitly
declare that it is importing external parity evidence.

Changes:

- Update `scripts/run_inference_eval_ladder.py` so `control_parity` can run both
  deterministic and live providers when `--live-openrouter` is supplied.
- Replace the hardcoded stale artifact path with the current run's provider
  results, or with an explicit `external_evidence_path` argument.
- Add provider-aware control-parity summaries: pass/fail/error/missing-tool
  counts by provider.
- Add a test using a fake second provider to prove the control suite actually
  evaluates a non-deterministic provider path.

Evidence gate:

```text
uv run --python /Users/joseph/.local/bin/python3.12 \
  --with pydantic --with pyyaml --with fastapi --with httpx \
  pytest tests scripts -q
```

Optional live evidence:

```text
uv run --python /Users/joseph/.local/bin/python3.12 \
  --with pydantic --with pyyaml --with fastapi --with httpx \
  python scripts/run_inference_eval_ladder.py \
  --suite control_parity \
  --live-openrouter \
  --verbose
```

### P0: make aggregate metrics provider-aware

Goal: top-level summaries must not hide live-provider failures behind baseline
counts.

Changes:

- Add `aggregate_by_provider` to inference ladder reports.
- Add `primary_provider_under_test`.
- For each suite, report provider-specific case counts, pass counts, fail
  counts, hard-fail counts, fallback counts, and mean scores.
- Keep baseline scores, but label them as baseline-only.
- In markdown output, show provider rows instead of a single baseline-centric
  pass/fail row.

Evidence gate:

- Unit tests over fixture provider results.
- Snapshot or structural tests for the JSON report shape.
- Re-run no-live all-suites smoke and confirm the aggregate states that
  OpenRouter was skipped.

### P1: score grounded answers by cited evidence, not only available context

Goal: grounded answer quality should measure what the composer actually cites.

Changes:

- Compute required source-family coverage from `composer_cited_source_ids`.
- Compute required tool-evidence coverage from `composer_cited_tool_call_ids`.
- Preserve the validator's unknown-citation fallback.
- Add a fixture case where the fixed context contains the right source but the
  draft cites the wrong source, and assert the score drops or hard-fails.

Evidence gate:

```text
uv run --python /Users/joseph/.local/bin/python3.12 \
  --with pydantic --with pyyaml --with fastapi --with httpx \
  python scripts/run_inference_eval_ladder.py \
  --suite grounded_answer_quality \
  --no-live \
  --verbose
```

### P1: turn repair planning into a real inference eval

Goal: repair planning should measure model-generated dry-run proposals while
deterministic validation still decides safety.

Changes:

- Add a typed `RepairProposalModelAdapter` or equivalent answer-composer mode.
- Give the model a fixed diagnostic context and require a `PatchProposal` JSON
  shape.
- Validate every proposal with the existing deterministic patch and
  `validate_batch` path.
- Keep fixture-only mode as a local no-live plumbing baseline, but label it
  separately.
- Add safe-refusal cases for missing concentration, missing ancestry, unknown
  well, and below-minimum transfer.

Evidence gate:

- No-live fixture repair suite remains green.
- Live repair suite records proposal JSON, validator result, and fallback reason
  for every case.

### P1: expand the language/UX ladder

Goal: inference should have a fair chance to beat deterministic where language
models are useful.

Minimum case targets:

- semantic generalization: expand from 6 to at least 20 cases.
- grounded answer quality: expand from 3 to at least 15 cases.
- repair planning: expand from 3 to at least 10 cases.

Case types to add:

- paraphrases with low overlap to doctrine vocabulary;
- ambiguous questions that require asking for or using deterministic context;
- multi-part explanations;
- validation-output summaries in human terms;
- "why not robot-ready?" explanations with tool evidence;
- dry-run patch suggestions;
- safe refusals where data is missing and must not be invented;
- source-conflict cases where the answer must name the conflict or say
  unsupported;
- out-of-domain and molarity-bait cases.

Evidence gate:

- Case manifests include split, tuning policy, source families, and expected
  safety behavior.
- Dev cases may tune prompts; regression and holdout cases may not.

### P1: improve unsupported-claim and contradiction checks

Goal: safety failures should not depend only on exact forbidden phrases.

Changes:

- Define structured claim classes, such as readiness claim, concentration
  claim, worklist-generation claim, approval claim, and unit claim.
- Add rule-based detectors for high-risk claim classes before adding any model
  judge.
- Make readiness polarity a first-class detector instead of only a small set of
  negated phrase exceptions.
- Add conflict-doc eval cases where retrieved docs disagree and the expected
  answer must acknowledge the conflict.
- Keep deterministic validation as the final authority for robot artifacts.

Evidence gate:

- Tests for negated vs unnegated readiness claims.
- Tests for invented concentrations, sample ids, plate wells, and worklist
  generation claims.

### P2: add strict gate mode

Goal: exploratory evals and release gates should be separate.

Changes:

- Add `--fail-on-threshold` or `--strict` to model and inference ladder scripts.
- Strict mode should fail nonzero when:
  - control parity has provider failures;
  - safety violations are nonzero;
  - groundedness hard-fails are nonzero;
  - required margins are not met for non-control suites;
  - live provider was requested but skipped.
- Keep exploratory mode as the default for live-model iteration.

Evidence gate:

- Tests that strict mode exits nonzero on fixture failures.
- CI can run no-live strict checks without credentials.

### P2: rotate baselines and document model variance

Goal: artifact provenance should be easy to trust.

Changes:

- Update `evals/baselines/inference_eval_baselines.json` only through a
  documented baseline-rotation command or checklist.
- Record the latest accepted live model ladder artifact and reason for rotation.
- Add optional repeated live runs for small suites, recording mean, min, max,
  and failure variance.

Evidence gate:

- Baseline file references current case-file hashes and accepted artifacts.
- Report markdown includes baseline id and rotation notes.

## Recommended Next Stage

The next implementation stage should be a focused eval-infrastructure cleanup,
not prompt tuning:

1. Fix `control_parity` and provider-aware aggregate reporting.
2. Add tests for those reporting contracts.
3. Re-run the no-live ladder.
4. Optionally re-run the live ladder after the reporting fix.

Only after the eval report itself is trustworthy should the project expand
language/UX cases or tune prompts again.
