# Baseline Rotation Policy

LabFlow eval baselines are evidence contracts. They should not move silently
when retrieval, corpus, prompt, or scoring code changes.

## Current Frozen Baseline

Portfolio frozen baselines live at:

```text
evals/baselines/portfolio_frozen_baselines.json
```

They currently cover:

- `semantic_generalization`;
- `grounded_answer_quality`.

Each baseline records:

- baseline set ID;
- source artifact paths;
- case file hashes;
- provider/model identity;
- per-case scores;
- pass/fail totals;
- rotation policy.

## Rotation Rules

Rotate a frozen baseline only when one of these is true:

- eval cases intentionally change;
- corpus chunking or retrieval contracts intentionally change;
- prompt/model contracts intentionally change;
- scoring rubric changes after documented eval audit;
- the prior baseline is no longer representative of the portfolio claim.

Do not rotate a baseline merely to make a failing run pass.

## Required Evidence For Rotation

- Old baseline artifact.
- New baseline artifact.
- Case file hash delta.
- Corpus hash or retrieval contract delta when relevant.
- Old-vs-new score table.
- Explanation of whether the change affects safety, groundedness, or only UX.
- Human approval noted in the assembly ledger.

## Regression Gates

- Safety-control cases must pass at 100 percent.
- Active-provider safety/provider/schema failures must be zero for canonical
  portfolio smoke runs.
- Semantic margin must remain above the documented threshold against the frozen
  baseline.
- Groundedness cannot regress below the documented threshold.
- Policy-critical source-family recall cannot regress.

## Reporting

Eval reports must distinguish:

- active deterministic parity;
- frozen baseline comparison;
- live model results;
- fixture-only evidence;
- active-provider production gate failures.
