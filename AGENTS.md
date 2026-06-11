# AGENTS.md — LabFlow AI Studio

## Mission

Build LabFlow AI Studio: an AI-assisted LIMS workflow development studio for synthetic NGS quantification and normalization workflows.

## Always read first

Before implementing non-trivial changes, read:

- `DOCTRINE.md`
- `ENGINEERING.md`
- `DECISIONS_LOCKED.md`
- `PROJECT_PLAN.md`
- relevant files in `specs/`

## Source repository rule

The existing reference repo is:

```text
/Users/joseph/ngs_lab_automation
```

You may inspect it. Do not modify it.

The new repo is:

```text
/Users/joseph/labflow
```

All implementation work belongs in the new repo.

## Non-negotiable domain rules

- Molarity is out of scope.
- Use ng/µL, µL, and ng as canonical units.
- Valid wells are A1-H12.
- Standards default to A1-H1.
- Sample plates have 95 samples + 1 blank.
- Standards plate is separate and run once per batch.
- Minimum transfer volume is 1 µL.
- Source residual dead volume is 2 µL.
- Robot aspiration safety margin is 1 µL.
- Max Matrix 1 mL tube working volume is 999 µL.
- Calculated transfer below 1 µL triggers split workflow, not silent rounding.
- RNA re-quant result becomes downstream concentration.
- Invalid samples generate no robot transfers.
- JANUS worklists require deterministic validation.

## AI rules

- Deterministic validators own lab truth.
- RAG answers cite sources or say unsupported.
- Agent is read-only by default.
- State-changing actions require dry-run first.
- Commit actions require approval token.
- Every tool call is audited.
- Do not invent missing data.

## Engineering rules

- Keep `labflow-core` free of LLM dependencies.
- Add tests with behavior changes.
- Run relevant tests before completing a task.
- Do not remove tests to make things pass.
- Keep local development independent of cloud credentials.
- Avoid broad rewrites unless the stage prompt requires them.

## Definition of done

A task is complete when:

- scope matches the prompt;
- tests were added/updated;
- tests/lints were run or failure is documented;
- docs were updated if behavior changed;
- risks and assumptions are summarized.
