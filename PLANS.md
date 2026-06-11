# Execution Plan Template for Codex

For complex tasks, Codex should create or update a short plan before implementation.

## Plan format

```markdown
# Plan: <stage name>

## Goal

## Files to inspect first

## Files expected to change

## Test strategy

## Risks / assumptions

## Out of scope

## Completion checklist
```

## Rules

- Do not implement before inspecting relevant files.
- Do not edit the source repo at `/Users/joseph/ngs_lab_automation`.
- Keep each stage scoped.
- Add or update tests in the same stage.
- If a requested feature conflicts with `DOCTRINE.md`, stop and report the conflict.
