# Stage 8 Assembly Review

Review date: 2026-06-08

Stage: `08_rag_eval_harness`

Authoritative spec: `.codex_build/prompts/08_rag_eval_harness.md`

Status: `successful`

## Target Contract

Stage 8 builds local eval tooling for retrieval, citation, answer-text, unsupported-claim placeholder, latency, and tool-call expectation checks over the Stage 6 golden questions and Stage 7 RAG foundation. The harness must run locally without API keys and write JSON reports to `artifacts/eval_reports/<eval_run_id>.json`.

## Extracted DoD Checklist

| DoD item | Status | Evidence |
| --- | --- | --- |
| Read `AGENTS.md` | met | Project operating rules read during preflight. |
| Read `ENGINEERING.md` | met | Engineering guide read during preflight. |
| Read `DOCTRINE.md` | met | Product doctrine read during preflight. |
| Read `DECISIONS_LOCKED.md` | met | Locked domain decisions read during preflight. |
| Read relevant RAG/eval specs | met | `specs/04_rag_spec.md` and `specs/05_eval_spec.md` read during preflight. |
| Implement `evals/cases.py` | met | Added strict golden-case loader and validation. |
| Implement `evals/runner.py` | met | Added local eval runner over RAG index/retriever/answering. |
| Implement `evals/metrics.py` | met | Added per-case results and aggregate metrics. |
| Implement `evals/reports.py` | met | Added JSON report writer. |
| Implement `scripts/run_rag_evals.py` | met | Added local CLI entrypoint with repo-root path resolution. |
| Calculate `retrieval_recall_at_k` | met | Metric included in per-case and aggregate report output. |
| Calculate citation precision proxy | met | Metric included and full-case pass gated on positive citation precision. |
| Calculate required answer contains match | met | Metric included in per-case and aggregate report output. |
| Calculate disallowed answer violations | met | Metric included in per-case and aggregate report output. |
| Include unsupported claim count placeholder | met | Placeholder included in per-case and aggregate report output. |
| Include latency metrics | met | Per-case latency and aggregate avg/p50/p95 included. |
| Write JSON report to `artifacts/eval_reports/<eval_run_id>.json` | met | CLI smoke wrote `artifacts/eval_reports/stage8_smoke.json`. |
| Test loading golden cases | met | `test_load_golden_cases`. |
| Test retrieval-only eval | met | `test_run_retrieval_only_eval_passes_known_baseline_cases`. |
| Test failure when required source missing | met | `test_eval_fails_when_required_source_missing`. |
| Test known baseline cases pass | met | Baseline retrieval-only cases pass. |
| `python scripts/run_rag_evals.py` works locally | met | Default CLI smoke and non-repo cwd smoke passed. |

## Evidence Commands

```text
python scripts/run_rag_evals.py
make test
make lint
make type
rg -n "openai|langchain|api_key|OPENAI" packages/labflow-rag scripts/run_rag_evals.py || true
git -C /Users/joseph/ngs_lab_automation status --short
```

## Review Findings

- James first review: `review-failed`.
  - P2: citation precision was measured but not part of full-case pass/fail. Fixed by recording `missing_required_citations`, carrying it in JSON, and requiring positive citation precision for non-retrieval-only pass semantics.
  - P2: CLI defaults were cwd-relative. Fixed by resolving relative paths against `REPO_ROOT` and adding a non-repo cwd CLI regression.
  - P3: `cases=()` loaded the full golden set. Fixed by distinguishing `cases is None` from an explicit empty tuple and adding a regression.
- James final review: clean, no blocking findings.
- Residual note: citation precision remains a Stage 8 proxy, not a final citation-quality metric.

## Subagent Review

Reviewer: James (`019ea933-90e3-7ea1-8b17-fb7b77f614a7`)

Final classification from reviewer:

- Citation pass semantics: `met`
- Report shape: `met`
- CLI cwd robustness: `met`
- Empty case handling: `met`

Evidence:

```text
python scripts/run_rag_evals.py --eval-run-id stage8_smoke
# wrote artifacts/eval_reports/stage8_smoke.json

cd /tmp && python /Users/joseph/labflow/scripts/run_rag_evals.py --retrieval-only --eval-run-id stage8_cwd_smoke --output-dir <tmpdir>
# wrote JSON report from non-repo cwd

make test
# 82 passed

make lint
# All checks passed

make type
# mypy success in 54 source files and VS Code extension tsc success

rg -n "openai|langchain|api_key|OPENAI" packages/labflow-rag scripts/run_rag_evals.py || true
# no matches

git -C /Users/joseph/ngs_lab_automation status --short
# ?? .DS_Store
```

## Final Classification

`successful`
