# Stage 3 Assembly Review

Review date: 2026-06-08

Stage: `03_core_quant_norm_migration`

Authoritative spec: `.codex_build/prompts/03_core_quant_norm_migration.md`

Status: `successful`

## Target Contract

Stage 3 builds the deterministic workflow engine in `labflow-core` by migrating/adapting quantification, normalization, RNA re-quant, JANUS/protocol exports, batch readiness, and throughput simulation. It must keep all logic deterministic and independent of LLM/RAG/agent packages.

## Extracted DoD Checklist

| DoD item | Status | Evidence |
| --- | --- | --- |
| Inspect reference quantification modules/tests | met | Read reference Varioskan, standard curve, quant processor, and quantification tests. |
| Inspect reference normalization/RNA modules/tests | met | Read target, split, planner, RNA re-quant behavior, and related tests. |
| Inspect reference robot/throughput modules/tests | met | Read protocol IR, JANUS, readiness/throughput modules, and related tests. |
| Implement `quant/varioskan.py` | met | Added schema-mapped TSV parser and typed readings. |
| Implement `quant/standards.py` | met | Added linear standard curve fitting, range checks, structured invalid/missing/extra standard layout exceptions, and exact A1-H1 enforcement. |
| Implement `quant/processors.py` | met | Added quantification config, blank/dilution processing, exact 95-sample plus blank plate validation, stock concentration rows, ancestry, and output writers. |
| Implement `norm/targets.py` | met | Added final concentration + volume and final mass + volume modes; molarity fields and direct extra fields rejected. |
| Implement `norm/planner.py` | met | Added CSV input validation, standard normalization, low concentration/source volume/destination checks, in-place, split rows, ancestry, and output writers. |
| Implement `norm/split.py` | met | Added split config enforcing 1 uL source transfer and child concentration estimate. |
| Implement `norm/requant.py` | met | Added RNA re-quant policy, downstream concentration rows, manual-review exceptions, ancestry, and output writers. |
| Implement `robots/protocol_ir.py` | met | Added protocol IR with diluent/sample/mix ordering and split/in-place handling. |
| Implement `robots/janus.py` | met | Added minimal JANUS CSV rows, audit rows, invalid-row exclusion, and worklist writers. |
| Implement `throughput/readiness.py` | met | Added deterministic readiness gate input/result models and evaluator. |
| Implement `throughput/simulator.py` | met | Added configurable default scenarios, one-vs-three container comparison, and output writers. |
| Implement `throughput/metrics.py` | met | Added throughput metric and comparison models. |
| Varioskan TSV parser with schema mapping | met | `test_varioskan_schema_mapping_and_sorted_tsv_parse` passed. |
| Standards plate once per batch with 8 standards A1-H1 | met | Standard curve tests cover exact A1-H1, partial layouts, and invalid standard well labels. |
| Linear standard curve | met | `test_standard_curve_with_8_standards_fits_expected_line` passed. |
| Per-plate blank correction and dilution-factor correction | met | `test_quantification_blank_dilution_stock_and_outputs` passed with 95 synthetic samples plus one configured blank. |
| Stock concentration ng/uL output | met | Quantification test verifies stock concentration and stock manifest output. |
| Missing standards/blank exceptions | met | Missing standard and missing blank tests passed. |
| Final concentration + volume target mode | met | Target and normalization math tests passed. |
| Final mass + volume target mode | met | Target test and RNA config test passed. |
| Reject molarity fields | met | Target test rejects `nM` through both `from_config` and direct Pydantic `model_validate`. |
| Standard normalization formula | met | `test_standard_new_container_normalization_math` passed. |
| Required source volume formula with 2 uL residual + 1 uL margin | met | Source-volume block test passed through planner. |
| Destination max 999 uL | met | Destination overflow tests passed. |
| Low concentration block | met | Low concentration test passed. |
| In-place normalization | met | In-place workflow and invalid-destination tests passed. |
| Split workflow when calculated transfer is below 1 uL | met | Split workflow, split config, and split capacity tests passed. |
| RNA re-quant result becomes downstream concentration | met | RNA re-quant test verifies `DOWNSTREAM_READY` and downstream concentration value. |
| Missing/invalid RNA re-quant result becomes manual review/repeat quant | met | RNA re-quant test covers missing, invalid, out-of-range, and downstream-impossible branches. |
| JANUS minimal CSV and rich audit CSV | met | JANUS test verifies minimal and audit rows. |
| Invalid rows excluded from JANUS | met | JANUS invalid and duplicate participant tests passed. |
| Throughput compares baseline 1-container and optimized 3-container batches | met | Default and configurable throughput comparison tests passed. |
| Robot run time and human prep configurable defaults | met | Throughput scenario defaults include 10 min prep and 3 min robot runtime; runtime outside 2-4 min is rejected. |
| Port/adapt reference tests and add gaps | met | Added adapted workflow tests covering quant, norm, RNA, robot export, readiness, throughput, output writers, standard-layout edge cases, and exact sample-plate layout validation. |
| Core workflow tests pass | met | `make test`: 41 passed. |
| Core package can generate example quant/norm/JANUS outputs from synthetic files | met | Tests write synthetic TSV/CSV files, run processors/planners, and verify quant, normalization, RNA, JANUS, and protocol output files. |
| No LLM/RAG/agent dependency exists in `labflow-core` | met | Dependency/import scan for `openai`, `langchain`, `llm`, `labflow_rag`, `labflow_agent`, and `labflow_api` returned no matches. |

## Evidence Commands

```text
make test
make lint
make type-python
make type
rg -n "openai|langchain|llm|labflow_rag|labflow_agent|labflow_api" packages/labflow-core || true
git -C /Users/joseph/ngs_lab_automation status --short
```

Evidence summary:

- `make test`: 41 passed.
- `make lint`: all checks passed.
- `make type-python`: no issues found in 32 source files.
- `make type`: Python mypy plus VS Code compile passed.
- Forbidden dependency/import scan: clean.
- Reference repo was not modified by this stage; status showed only an untracked `.DS_Store`, which was not touched.

## Review Findings

Reviewer: Parfit (`019ea8d3-17da-7a43-8c48-7c4ef90f8370`).

Initial review found valid assembly and contract findings:

- Ledger incorrectly marked Stage 3 successful before subagent review.
- `NormalizationTarget` direct Pydantic validation allowed molarity-like extra keys.
- Standard curve fitting did not fully enforce the exact A1-H1 standard layout.
- Quantification accepted incomplete sample plates instead of enforcing 95 samples plus one configured blank.

Follow-up review found two additional layout edges:

- Invalid configured standard well labels could raise unstructured validation errors.
- Sample plate validation checked count without proving exact well coverage, allowing duplicate wells plus missing wells.

Fixes applied:

- `NormalizationTarget` now forbids extra fields, including direct `model_validate` inputs.
- Standard concentration layout validation now returns structured blocking exceptions for invalid, missing, or extra standard wells and requires exactly A1-H1.
- Sample plate validation now requires the sample well set to equal all A1-H12 wells minus the configured blank, with no duplicate or unexpected wells.
- Tests now pin partial standard layouts, invalid standard labels, incomplete sample plates, duplicate/missing sample wells, and direct molarity rejection.

Final reviewer outcome: clean. No blocking findings remain.

## Notes

- RNA re-quant is implemented in `labflow_core.norm.requant` rather than embedded in the normalization planner, matching the new core spec boundary.
- Stage 3 output-generation evidence is test-backed with temporary synthetic files rather than committed generated artifacts.
- YAML config loaders were not added in this stage to avoid an unnecessary runtime dependency; deterministic processors accept typed configs and file paths directly.

## Subagent Review

Subagent review was run after the user explicitly asked whether assembly review was using a reviewer subagent.

- Reviewer: Parfit (`019ea8d3-17da-7a43-8c48-7c4ef90f8370`).
- First pass: review-failed with valid contract findings.
- Second pass: review-failed with valid invalid-label and duplicate-well layout findings.
- Final pass: clean; DoD items for A1-H1 standards, 95 samples plus blank, molarity rejection, and review evidence classified as `met`.

## Final Classification

Stage 3 status: `successful`

All required Stage 3 DoD items are `met`; no items are `partial`, `blocked`, or `not-started`.
