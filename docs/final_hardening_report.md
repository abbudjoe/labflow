# Final Hardening Report

Date: 2026-06-10

Stage: `18_final_hardening_review`

Status: portfolio walkthrough ready, with documented v0.2 risks.

## Summary

LabFlow AI Studio v0.1 is ready for a local portfolio walkthrough. The deterministic demo path works, the full test/lint/type suite passes, Terraform validates, retrieval-only evals pass all golden cases, and documentation clearly states the synthetic/non-production boundaries.

One important limitation remains: the current local extractive answer composer is not tuned to pass the full answer-term eval set. Retrieval is strong, but full answer-quality and tool-recommendation tuning should be v0.2 work or handled when real inference is added behind provider adapters.

## Commands Run

### Repository Structure

```text
find . -path './.git' -prune \
  -o -path './apps/vscode-extension/node_modules' -prune \
  -o -path './packages/labflow-core/.venv' -prune \
  -o -path './infra/terraform/.terraform' -prune \
  -o -maxdepth 3 -type d -print | sort
```

Result: pass. Expected monorepo directories are present:

- `packages/labflow-core`
- `packages/labflow-rag`
- `packages/labflow-agent`
- `apps/api`
- `apps/vscode-extension`
- `knowledge`
- `evals`
- `examples`
- `infra/terraform`
- `docs`
- `scripts`

### Tests

```text
make test
```

Result: pass.

```text
117 passed, 1 warning
```

The warning is a third-party FastAPI/Starlette deprecation warning from the test client dependency path.

### Lint

```text
make lint
```

Result: pass.

```text
All checks passed!
```

### Type Checks And VS Code Build

```text
make type
```

Result: pass.

```text
mypy --strict: Success, no issues found in 78 source files
npm --prefix apps/vscode-extension run compile: passed
```

### RAG Evals

Retrieval-only eval:

```text
python3 scripts/run_rag_evals.py --retrieval-only --eval-run-id stage18_retrieval --output-dir /tmp/labflow-stage18-evals
```

Result: pass.

```text
cases=37
passed=37
failed=0
retrieval_recall_at_k=1.000
citation_precision_proxy=0.320
answer_contains_match=0.100
disallowed_violations=0
```

Full local answer eval:

```text
python3 scripts/run_rag_evals.py --eval-run-id stage18_answer --output-dir /tmp/labflow-stage18-evals
```

Result: diagnostic limitation documented.

```text
cases=37
passed=1
failed=36
retrieval_recall_at_k=1.000
citation_precision_proxy=0.923
answer_contains_match=0.295
disallowed_violations=0
```

Interpretation: retrieval is working, but the deterministic extractive answer composer is not yet tuned to satisfy the full answer-term/tool-call golden set. The portfolio demo should use the retrieval-only eval artifact and the deterministic demo path. Full answer-composition quality is recommended v0.2 work.

### Demo Script

```text
python3 scripts/run_demo.py --output-dir /tmp/labflow-stage18-demo
```

Result: pass.

```text
invalid_errors=6
fixed_janus=ok
eval_passed=37/37
```

The demo validates the invalid RNA workflow, blocks JANUS generation for invalid inputs, validates the fixed workflow, generates a dry-run JANUS preview, parses synthetic Varioskan TSV files, writes audit artifacts, and runs retrieval-only evals.

### Terraform

```text
terraform -chdir=infra/terraform validate
```

Result: pass.

```text
Success! The configuration is valid.
```

No `terraform plan` or `terraform apply` was run.

### Secret And Confidential Data Scan

```text
rg -n --hidden \
  -g '!.git' \
  -g '!apps/vscode-extension/node_modules' \
  -g '!packages/labflow-core/.venv' \
  -g '!infra/terraform/.terraform' \
  -g '!artifacts' \
  -g '!*.lock' \
  "AKIA[0-9A-Z]{16}|secret_key|access_key|BEGIN (RSA|OPENSSH|PRIVATE)|password\\s*=" .
```

Result: pass with expected non-secret hits only. Matches were the literal scan patterns recorded in assembly ledgers.

### Molarity Boundary Scan

```text
rg -n "molarity|\\bnM\\b|\\bfmol\\b|\\bpmol\\b" packages examples docs knowledge evals README.md
```

Result: pass. Matches are rejection paths, negative examples, docs, and eval cases. Molar target fields remain out of scope and are rejected by deterministic validation.

### JANUS And Agent Safety Tests

```text
PYTHONPATH="packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src" \
uv run --python /Users/joseph/.local/bin/python3.12 \
  --with pytest --with pydantic --with pyyaml \
  python -m pytest --rootdir=. \
  packages/labflow-core/tests/test_core_tools.py::test_invalid_batch_blocks_janus \
  packages/labflow-core/tests/test_core_workflows.py::test_janus_export_excludes_invalid_and_writes_protocol \
  packages/labflow-core/tests/test_core_workflows.py::test_duplicate_participants_generate_no_janus_rows \
  packages/labflow-agent/tests/test_agent_runtime.py::test_agent_refuses_unsupported_question
```

Result: pass.

```text
4 passed
```

This confirms:

- invalid batches block JANUS generation;
- invalid rows are excluded from JANUS exports;
- duplicate participants generate no robot rows;
- unsupported agent questions receive no-answer behavior.

### Reference Repository

```text
git -C /Users/joseph/ngs_lab_automation status --short
```

Result:

```text
?? .DS_Store
```

The reference repository was not modified by this stage. The `.DS_Store` entry pre-existed.

## Fixes Made

- Removed local `.DS_Store` files from the new repository.
- Removed generated Python/test cache directories after validation.
- Added this final hardening report.
- No behavioral code fixes were required by the Stage 18 checks.

## Docs Against Behavior

The current docs match the implemented behavior:

- README describes the project as local-first, synthetic, non-production, and deterministic by default.
- Demo walkthrough matches `scripts/run_demo.py`.
- Case study explains deterministic core, RAG/evals, guardrails, VS Code, API, and AWS skeleton.
- Limitations document explicitly states no production LIMS, no clinical/diagnostic use, no robot execution, no live model provider by default, and no applied cloud environment.

## Remaining Risks

- Full answer-composition eval is not passing. Retrieval is strong, but deterministic answer text and tool-call recommendation wording need v0.2 tuning or live-model integration behind guardrails.
- VS Code extension is a skeleton and compiles, but the final user experience has not been manually exercised in an installed VS Code session during this stage.
- Terraform validates locally, but no cloud plan/apply was run and no cloud environment was provisioned.
- Approval and durable artifact stores are still local/prototype-shaped.
- Security review, auth, tenancy, and secrets management are not implemented.
- JANUS output is a dry-run preview format for portfolio demonstration, not a certified production robot worklist.

## Recommended v0.2 Work

1. Add a real inference provider adapter behind explicit environment configuration, keeping deterministic model behavior as the default test path.
2. Tune answer composition and tool-call recommendation behavior until the full answer eval suite is meaningful and passing.
3. Add durable local or cloud-backed stores for approvals, audit events, eval runs, and generated artifacts.
4. Add an end-to-end VS Code demo script or screenshot checklist.
5. Add security review and threat modeling for API/tool boundaries.
6. Add CI that runs tests, lint, type checks, RAG retrieval evals, demo smoke, and Terraform validate.
7. Add richer generated case-study artifacts, such as screenshots or a short demo transcript.
8. Add optional cloud sandbox planning with explicit user authorization and no default apply path.

## Final Readiness

LabFlow AI Studio v0.1 is ready for a portfolio walkthrough centered on:

- deterministic lab workflow validation;
- synthetic RNA normalization/re-quant demo;
- guarded JANUS dry-run preview generation;
- local RAG retrieval and evals;
- controlled tool-using agent architecture;
- VS Code/API developer platform shape;
- production-shaped AWS infrastructure mapping;
- honest limitations and disclosure.
