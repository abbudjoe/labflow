# Pre-Stage 9 Cleanup Assembly Review

Review date: 2026-06-09

Stage: `pre_stage9_cleanup`

Authoritative plan: `.codex_build/pre_stage9_cleanup_plan.md`

Status: `successful`

## Target Contract

Before Stage 9 begins, improve Stage 8 RAG retrieval coverage for the nine retrieval-only misses and add a local interactive RAG demo CLI. The cleanup must stay deterministic, local-first, citation-ready, and free of LLM/API-key requirements.

## Extracted DoD Checklist

| DoD item | Status | Evidence |
| --- | --- | --- |
| D1: Diagnose and address nine retrieval misses | met | Per-miss audit below records baseline misses, root cause, change class, post-change chunks, and golden-edit flag. |
| D2: Retrieval-only eval passes all 37 cases at top_k=6 | met | `pre_stage9_cleanup_retrieval.json`: `case_count=37`, `retrieval_only=true`, `top_k=6`, `failed_count=0`; JSON assertion passed for all nine target case IDs. |
| D3: Remain local-first, deterministic, API-key-free | met | `packages/labflow-rag/pyproject.toml` has `dependencies = []`; no API/network-client scan hits; no-API-env retrieval eval and demo smoke passed. |
| D4: Add `scripts/rag_demo.py` interactive CLI | met | `scripts/rag_demo.py` prints canonical `Answer:`, `Sources:`, and `Suggested tools:` sections using citation chunk IDs only; tools are displayed only as recommendations. |
| D5: CLI supports stdin smoke and clean exit | met | Stdin, `/tmp` cwd, no-API-env, EOF, `exit`, and `quit` smokes exited code 0; unsupported answer prints `Sources: - none` and `Suggested tools: - none`. |
| D6: Focused tests cover behavior changes | met | Added retrieval all-37/nine-case test and CLI subprocess tests in `packages/labflow-rag/tests/test_rag_eval_harness.py`; focused tests passed. |
| D7: Relevant gates pass | met | `make test`, `make lint`, `make type`, script `ruff check`, and script `py_compile` passed. |
| D8: Assembly review is clean | met | Plan review is clean; post-implementation findings were fixed; Copernicus re-review classified D1-D9 as met. |
| D9: Ledger updated with evidence and risks | met | Ledger updated with plan review, implementation review, commands, metrics, per-miss audit, and residual risk notes. |

## Changed Files

- `.codex_build/pre_stage9_cleanup_plan.md`
- `docs/pre_stage9_cleanup_assembly_review.md`
- `packages/labflow-rag/src/labflow_rag/retrieval.py`
- `packages/labflow-rag/tests/test_rag_eval_harness.py`
- `scripts/rag_demo.py`
- `scripts/README.md`

## Implementation Summary

- Increased hybrid retriever candidate gathering to avoid hiding lower-ranked but relevant corpus documents before merge.
- Added document-diverse final result selection so one strong document cannot crowd out every required source in top-k retrieval.
- Added deterministic domain query expansion for missing concentration, JANUS/readiness, split workflow/ancestry, RNA re-quant/downstream concentration, molarity exclusion, guardrails, and throughput validation gates.
- Added `scripts/rag_demo.py`, a local RAG demo CLI that asks questions, prints grounded answers, source chunk IDs, and suggested tool names without executing tools.
- Added regression tests for all-37 retrieval-only pass at top-k 6, the nine original miss IDs, demo formatting, non-repo cwd behavior, and unsupported-answer formatting.
- Updated `scripts/README.md` to document the eval runner and demo CLI.

## Per-Miss Audit

No golden-case edits were made.

| Case | Question | Missing baseline source(s) | Corpus support/rationale | Baseline top-6 chunks | Root cause | Change class | Golden edit? | Post-change top-6 chunks | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `q_batch_001` | Can a JANUS CSV be generated if a sample is missing concentration? | `batch_readiness_doctrine.md`, `exception_handling_manual.md` | Batch readiness lists `MISSING_CONCENTRATION` as a blocking gate; exception manual defines `MISSING_CONCENTRATION` and `JANUS_BLOCKED_FOR_INVALID_BATCH`. | `janus_csv_worklist_spec.md#chunk-001`; `janus_csv_worklist_spec.md#chunk-010`; `dna_quant_picogreen_sop.md#chunk-006`; `janus_csv_worklist_spec.md#chunk-002`; `janus_csv_worklist_spec.md#chunk-003`; `rna_norm_requant_sop.md#chunk-005` | JANUS chunks crowded out readiness/exception sources for a missing-concentration robot-artifact question. | Added missing-concentration/readiness/exception expansion plus document-diverse selection. | no | `batch_readiness_doctrine.md#chunk-006`; `exception_handling_manual.md#chunk-010`; `dna_quant_picogreen_sop.md#chunk-006`; `janus_csv_worklist_spec.md#chunk-010`; `throughput_optimization_case.md#chunk-007`; `rna_norm_requant_sop.md#chunk-005` | passed |
| `q_split_001` | What happens when calculated sample transfer volume is below 1 uL? | `sample_ancestry_policy.md` | Sample ancestry defines `SPLIT_CREATED` parent/child events for high-concentration split workflows. | `dna_normalization_sop.md#chunk-007`; `dna_normalization_sop.md#chunk-008`; `exception_handling_manual.md#chunk-006`; `dna_normalization_sop.md#chunk-005`; `batch_readiness_doctrine.md#chunk-005`; `labflow_dsl_reference.md#chunk-010` | DNA normalization duplicates crowded out split ancestry source. | Added split child/ancestry expansion plus document-diverse selection. | no | `dna_normalization_sop.md#chunk-007`; `exception_handling_manual.md#chunk-006`; `sample_ancestry_policy.md#chunk-004`; `batch_readiness_doctrine.md#chunk-005`; `labflow_dsl_reference.md#chunk-010`; `rna_norm_requant_sop.md#chunk-007` | passed |
| `q_split_002` | Can the agent round a 0.4 uL DNA transfer to make a standard worklist? | `ai_guardrails_policy.md` | AI guardrails forbid invention/bypass and robot artifact generation when deterministic validation does not support it. | `dna_normalization_sop.md#chunk-005`; `dna_normalization_sop.md#chunk-007`; `exception_handling_manual.md#chunk-006`; `batch_readiness_doctrine.md#chunk-005`; `dna_normalization_sop.md#chunk-008`; `dna_quant_picogreen_sop.md#chunk-004` | Rounding/agent safety policy source was below cutoff behind normalization and exception chunks. | Added agent/rounding/guardrail expansion plus document-diverse selection. | no | `dna_normalization_sop.md#chunk-007`; `exception_handling_manual.md#chunk-006`; `batch_readiness_doctrine.md#chunk-005`; `janus_csv_worklist_spec.md#chunk-007`; `dna_quant_picogreen_sop.md#chunk-004`; `ai_guardrails_policy.md#chunk-006` | passed |
| `q_rna_003` | What concentration should downstream RNA steps use after re-quant? | `sample_ancestry_policy.md` | Sample ancestry defines `REQUANTIFIED` as the event where measured re-quant becomes downstream concentration. | `rna_norm_requant_sop.md#chunk-004`; `exception_handling_manual.md#chunk-008`; `rna_norm_requant_sop.md#chunk-006`; `rna_norm_requant_sop.md#chunk-008`; `rna_norm_requant_sop.md#chunk-007`; `exception_handling_manual.md#chunk-010` | RNA SOP and exception chunks crowded out downstream concentration ancestry source. | Added re-quant/downstream/ancestry expansion plus document-diverse selection. | no | `rna_norm_requant_sop.md#chunk-004`; `exception_handling_manual.md#chunk-008`; `sample_ancestry_policy.md#chunk-005`; `batch_readiness_doctrine.md#chunk-005`; `throughput_optimization_case.md#chunk-005`; `dna_quant_picogreen_sop.md#chunk-004` | passed |
| `q_janus_004` | What should the assistant do before generating a JANUS dry-run preview? | `batch_readiness_doctrine.md` | Batch readiness says `validate_batch` must run before readiness claims and `generate_janus_csv` is dry-run only after validation passes. | `janus_csv_worklist_spec.md#chunk-010`; `janus_csv_worklist_spec.md#chunk-007`; `janus_csv_worklist_spec.md#chunk-004`; `ai_guardrails_policy.md#chunk-005`; `janus_csv_worklist_spec.md#chunk-001`; `ai_guardrails_policy.md#chunk-007` | JANUS and guardrail chunks crowded out batch readiness for dry-run precondition question. | Increased candidate pool and added readiness expansion plus document-diverse selection. | no | `janus_csv_worklist_spec.md#chunk-007`; `ai_guardrails_policy.md#chunk-005`; `batch_readiness_doctrine.md#chunk-006`; `exception_handling_manual.md#chunk-009`; `labflow_dsl_reference.md#chunk-004`; `throughput_optimization_case.md#chunk-007` | passed |
| `q_molar_001` | How do I configure molar normalization? | `labflow_dsl_reference.md` | DSL reference owns workflow YAML/unit configuration and states molarity, `nM`, `fmol`, and `pmol` are unsupported. | `dna_normalization_sop.md#chunk-009`; `dna_normalization_sop.md#chunk-004`; `dna_normalization_sop.md#chunk-006`; `dna_normalization_sop.md#chunk-001`; `dna_normalization_sop.md#chunk-003`; `dna_normalization_sop.md#chunk-007` | DNA normalization chunks saturated top-k for molarity exclusion, hiding DSL unit rules. | Added molarity/DSL/YAML expansion plus document-diverse selection. | no | `labflow_dsl_reference.md#chunk-004`; `dna_normalization_sop.md#chunk-009`; `ai_guardrails_policy.md#chunk-008`; `rna_norm_requant_sop.md#chunk-001`; `sample_ancestry_policy.md#chunk-006`; `batch_readiness_doctrine.md#chunk-001` | passed |
| `q_molar_002` | Can I use nM or pmol in a LabFlow workflow YAML? | `ai_guardrails_policy.md` | AI guardrails classify molarity and noncanonical units as unsupported requests and forbid unsupported lab claims. | `labflow_dsl_reference.md#chunk-008`; `labflow_dsl_reference.md#chunk-004`; `labflow_dsl_reference.md#chunk-012`; `labflow_dsl_reference.md#chunk-005`; `labflow_dsl_reference.md#chunk-001`; `dna_normalization_sop.md#chunk-004` | DSL chunks crowded out guardrail policy for unsupported molarity units. | Added molarity/guardrail expansion plus document-diverse selection. | no | `labflow_dsl_reference.md#chunk-004`; `ai_guardrails_policy.md#chunk-007`; `dna_normalization_sop.md#chunk-004`; `rna_norm_requant_sop.md#chunk-004`; `dna_quant_picogreen_sop.md#chunk-001`; `varioskan_tsv_import_spec.md#chunk-005` | passed |
| `q_guardrails_001` | Can the AI fill in a missing concentration so validation passes? | `exception_handling_manual.md` | Exception manual defines `MISSING_CONCENTRATION` as a concentration/volume exception that blocks robot transfer until resolved. | `ai_guardrails_policy.md#chunk-004`; `ai_guardrails_policy.md#chunk-008`; `ai_guardrails_policy.md#chunk-009`; `dna_quant_picogreen_sop.md#chunk-006`; `batch_readiness_doctrine.md#chunk-006`; `ai_guardrails_policy.md#chunk-007` | Guardrail policy chunks crowded out the exception code source for missing concentration. | Added missing-concentration/exception expansion plus document-diverse selection. | no | `ai_guardrails_policy.md#chunk-008`; `batch_readiness_doctrine.md#chunk-006`; `exception_handling_manual.md#chunk-004`; `dna_quant_picogreen_sop.md#chunk-006`; `dna_normalization_sop.md#chunk-008`; `rna_norm_requant_sop.md#chunk-004` | passed |
| `q_throughput_003` | Can throughput optimization bypass validation gates? | `batch_readiness_doctrine.md` | Batch readiness defines readiness gates that throughput optimization cannot bypass; invalid samples generate no robot transfers. | `throughput_optimization_case.md#chunk-007`; `throughput_optimization_case.md#chunk-009`; `throughput_optimization_case.md#chunk-001`; `throughput_optimization_case.md#chunk-008`; `throughput_optimization_case.md#chunk-003`; `throughput_optimization_case.md#chunk-006` | Throughput case chunks saturated top-k and hid the validation-gate doctrine. | Added throughput/validation/readiness expansion plus document-diverse selection. | no | `throughput_optimization_case.md#chunk-007`; `batch_readiness_doctrine.md#chunk-004`; `ai_guardrails_policy.md#chunk-005`; `janus_csv_worklist_spec.md#chunk-010`; `labflow_dsl_reference.md#chunk-009`; `dna_quant_picogreen_sop.md#chunk-008` | passed |

## Plan Review

Initial reviewer: Dirac (`019eadbb-5e88-7412-b782-7771b5092123`)

Initial classification: `review-failed`

Findings addressed in `.codex_build/pre_stage9_cleanup_plan.md`:

- P1: D2 could be satisfied by weakening evals. Fixed by requiring JSON evidence for `case_count=37`, `retrieval_only=true`, `top_k=6`, `failed_count=0`, and nine target case IDs present/passing.
- P2: D1 evidence was under-specified. Fixed by adding a per-miss audit schema.
- P2: D4/D5 CLI contract was incomplete. Fixed by requiring repo-root path resolution, non-repo cwd smoke, exit code 0, unsupported formatting, citation chunk IDs, and no tool execution.
- P2: D7 omitted script lint/type/syntax checks. Fixed by adding explicit `ruff check` and `py_compile` script gates.
- P2: D3 API-free evidence was too narrow. Fixed by adding dependency-diff evidence, broader source scan terms, and no-API-env eval/demo evidence.
- P3: full eval risked scope creep. Fixed by labeling full eval observational only.
- P3: Stage 6 throughput corpus extension was not in authoritative inputs. Fixed by adding `docs/stage6_assembly_review.md`.

Plan re-review classification: `assembly-clean for implementation`

Reviewer note: add a no-API-env wrapper to a `rag_demo.py` smoke before final completion. Added to planned evidence.

## Evidence Commands

```text
python scripts/run_rag_evals.py --retrieval-only --eval-run-id pre_stage9_cleanup_retrieval
# cases=37 passed=37 failed=0 retrieval_recall_at_k=1.000 citation_precision_proxy=0.320

python - <<'PY' ...
# retrieval_json_contract=passed

python scripts/run_rag_evals.py --eval-run-id pre_stage9_cleanup_full_observational
# cases=37 passed=1 failed=36 retrieval_recall_at_k=1.000 citation_precision_proxy=0.923
# answer_contains_match=0.288 disallowed_violations=0 unsupported_claim_count=0

printf 'Can invalid samples appear in JANUS transfer rows?\nexit\n' | python scripts/rag_demo.py
# printed Answer/Sources/Suggested tools with batch readiness and JANUS citations.

cd /tmp && printf 'Can invalid samples appear in JANUS transfer rows?\nquit\n' | python /Users/joseph/labflow/scripts/rag_demo.py
# exited 0 and resolved repository corpus paths from non-repo cwd.

env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY sh -c "printf 'Can invalid samples appear in JANUS transfer rows?\nexit\n' | python scripts/rag_demo.py"
# exited 0 with no API key environment variables.

printf 'Who won the ice hockey championship on Europa in 2035?\n' | python scripts/rag_demo.py
# printed canonical unsupported answer with Sources: - none and Suggested tools: - none.

env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY python scripts/run_rag_evals.py --retrieval-only --eval-run-id pre_stage9_cleanup_no_api_env
# cases=37 passed=37 failed=0 retrieval_recall_at_k=1.000

uv run --python python3 --with pytest --with pydantic --with pyyaml env PYTHONPATH=packages/labflow-rag/src python -m pytest packages/labflow-rag/tests/test_rag_eval_harness.py packages/labflow-rag/tests/test_rag_foundation.py -q
# 17 passed

make test
# 85 passed

make lint
# All checks passed

make type
# mypy success in 54 source files; VS Code extension tsc compile succeeded.

uv run --python python3 --with ruff python -m ruff check scripts/rag_demo.py scripts/run_rag_evals.py
# All checks passed

python -m py_compile scripts/rag_demo.py scripts/run_rag_evals.py
# passed

sed -n '1,40p' packages/labflow-rag/pyproject.toml
# project dependencies = []

rg -n "openai|anthropic|langchain|llamaindex|api_key|OPENAI|ANTHROPIC|requests|httpx|urllib|boto3|botocore" packages/labflow-rag scripts || true
# no matches

git -C /Users/joseph/ngs_lab_automation status --short
# ?? .DS_Store
```

## Metrics Delta

| Eval report | Mode | Passed | Failed | Retrieval recall | Citation precision proxy | Notes |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `human_review_stage8_retrieval.json` | retrieval-only | 28 | 9 | 0.883 | 0.585 | Baseline before cleanup. |
| `pre_stage9_cleanup_retrieval.json` | retrieval-only | 37 | 0 | 1.000 | 0.320 | Cleanup target met; citation precision proxy drops because top-6 is intentionally more document-diverse. |
| `human_review_stage8.json` | full answer | 1 | 36 | 0.883 | 0.887 | Baseline before cleanup. |
| `pre_stage9_cleanup_full_observational.json` | full answer | 1 | 36 | 1.000 | 0.923 | Observational only; primitive answer composer still limits full-case pass rate. |

## Review Findings

Post-implementation reviewer: Copernicus (`019eadc5-ee85-7ee0-9607-980950f9137b`)

Initial classification: `review-failed`

Findings addressed:

- P2: per-miss audit did not fully match the mandatory schema. Fixed by adding question text, explicit corpus-support rationale, and per-row golden-edit flags.
- P2: final review/status bookkeeping was stale. Fixed by updating the plan status, plan DoD statuses, ledger status, D8/D9 rows, review findings, and residual risks.
- P3: D3 evidence relied on `git diff` in an untracked repo. Fixed by citing `packages/labflow-rag/pyproject.toml` contents directly: `dependencies = []`, plus no-API-env eval/demo and API/network source scan.
- P3 residual risk: document-diverse selection intentionally prioritizes one chunk per document before duplicate chunks, which lowers retrieval-only citation precision proxy. Recorded below as residual risk.

Re-review classification: `clean`

Reviewer conclusion: D1-D9 are met, with D8 met by the clean post-fix review.

## Post-Review Smoke

```text
python scripts/run_rag_evals.py --retrieval-only --eval-run-id pre_stage9_cleanup_post_review
# cases=37 passed=37 failed=0 retrieval_recall_at_k=1.000 citation_precision_proxy=0.320

printf 'Can invalid samples appear in JANUS transfer rows?\nexit\n' | python scripts/rag_demo.py
# printed Answer/Sources/Suggested tools with batch readiness and JANUS citations.

uv run --python python3 --with pytest --with pydantic --with pyyaml env PYTHONPATH=packages/labflow-rag/src python -m pytest packages/labflow-rag/tests/test_rag_eval_harness.py packages/labflow-rag/tests/test_rag_foundation.py -q
# 17 passed
```

## Residual Risks

- Retrieval-only recall is now 1.000 at top-k 6, but citation precision proxy dropped from 0.585 to 0.320 because the result set is deliberately more document-diverse. This is acceptable for the cleanup target, but future tuning should consider a score-ratio floor or per-document diversity cap.
- Full answer eval still passes only 1 of 37 cases because answer composition remains the simple extractive Stage 7/8 implementation. This cleanup did not implement Stage 9 agent answer composition.
- Domain query expansion remains hand-authored. It is deterministic and covered by tests, but future corpus growth may require richer synonym governance or a reranker.

## Final Classification

`successful`
