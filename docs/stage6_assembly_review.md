# Stage 6 Assembly Review

Review date: 2026-06-08

Stage: `06_knowledge_corpus`

Authoritative spec: `.codex_build/prompts/06_knowledge_corpus.md`

Status: `successful`

## Target Contract

Stage 6 creates a synthetic, non-production LabFlow knowledge corpus for later RAG retrieval and an initial golden-question eval set. The corpus must provide grounded, chunk-friendly domain material without proprietary SOP claims, production readiness claims, or clinical/diagnostic positioning.

## Extracted DoD Checklist

| DoD item | Status | Evidence |
| --- | --- | --- |
| Read `AGENTS.md` | met | Project operating rules read during preflight. |
| Read `ENGINEERING.md` | met | Engineering guide read during preflight. |
| Read `DOCTRINE.md` | met | Product doctrine read during preflight. |
| Read `DECISIONS_LOCKED.md` | met | Locked domain decisions read during preflight. |
| Read `PROJECT_PLAN.md` | met | Project plan read during preflight. |
| Read relevant RAG/eval specs | met | `specs/04_rag_spec.md` and `specs/05_eval_spec.md` read during preflight. |
| Write `knowledge/dna_quant_picogreen_sop.md` | met | Synthetic SOP includes scope, rules, diagnostics, and cross-references. |
| Write `knowledge/dna_normalization_sop.md` | met | Synthetic SOP includes formulas, modes, constraints, diagnostics, and cross-references. |
| Write `knowledge/rna_norm_requant_sop.md` | met | Synthetic SOP includes downstream re-quant policy, diagnostics, and cross-references. |
| Write `knowledge/batch_readiness_doctrine.md` | met | Readiness gates and robot-ready doctrine written. |
| Write `knowledge/exception_handling_manual.md` | met | Exception-code manual and handling guidance written. |
| Write `knowledge/janus_csv_worklist_spec.md` | met | JANUS dry-run/worklist gating spec written. |
| Write `knowledge/varioskan_tsv_import_spec.md` | met | TSV import and schema-mapping spec written. |
| Write `knowledge/sample_ancestry_policy.md` | met | Ancestry policy for derived samples and re-quant written. |
| Write `knowledge/ai_guardrails_policy.md` | met | Guardrails for RAG, tools, approvals, and audit written. |
| Write `knowledge/labflow_dsl_reference.md` | met | DSL reference for workflow YAML written. |
| Write `knowledge/throughput_optimization_case.md` | met | Synthetic throughput case with non-production caveats written. |
| Each knowledge doc includes title | met | Corpus validation and subagent review confirmed. |
| Each knowledge doc includes scope | met | Corpus validation and subagent review confirmed. |
| Each knowledge doc includes synthetic/non-production note | met | Corpus validation and subagent review confirmed. |
| Each knowledge doc states clear rules | met | Corpus validation and subagent review confirmed. |
| Each knowledge doc includes diagnostic/exception codes where relevant | met | Corpus validation and subagent review confirmed. |
| Each knowledge doc includes cross-references | met | Corpus validation and subagent review confirmed. |
| Create `evals/golden_questions.yaml` | met | Added 37 parseable golden cases. |
| Golden evals cover batch readiness | met | 4 cases in `batch_readiness`. |
| Golden evals cover standards/blank rules | met | 5 cases in `standards_blank_rules`. |
| Golden evals cover split workflow | met | 3 cases in `split_workflow`. |
| Golden evals cover in-place normalization | met | 3 cases in `in_place_normalization`. |
| Golden evals cover RNA re-quant | met | 4 cases in `rna_requant`. |
| Golden evals cover JANUS gating | met | 4 cases in `janus_gating`. |
| Golden evals cover sample ancestry | met | 3 cases in `sample_ancestry`. |
| Golden evals cover molarity exclusion | met | 3 cases in `molarity_exclusion`. |
| Golden evals cover guardrails | met | 5 cases in `guardrails`. |
| Golden evals cover throughput | met | 3 cases in `throughput`. |
| Do not cite proprietary SOPs | met | Subagent review found no proprietary SOP citation. |
| Do not claim production/clinical readiness | met | Subagent review found positive clinical/production terms only in negative disclaimers or refusal-style eval cases. |

## Evidence Commands

```text
python -c corpus/eval validation script
make test
make lint
make type
rg -n "proprietary|clinical|diagnostic|production-ready|production ready" knowledge evals || true
git -C /Users/joseph/ngs_lab_automation status --short
```

## Review Findings

- Boyle review: clean, no blocking findings.
- Residual note: some seed evals use `required_tool_calls` on abstract policy questions. This is acceptable for Stage 6 seed data; the later eval harness should define whether that field means actual invocation required or recommendation expected.

## Subagent Review

Reviewer: Boyle (`019ea920-01de-70a3-a18e-d96706f3d37c`)

Final classification from reviewer:

- Knowledge corpus: `met`
- Golden evals: `met`
- Safety/provenance constraints: `met`
- Stage scope and ledger: `met for review`

Evidence:

```text
uv run --python python3 --with pyyaml python - <<'PY' ...
# validated 11 knowledge docs and 37 golden cases
# categories: batch_readiness, guardrails, in_place_normalization, janus_gating,
# molarity_exclusion, rna_requant, sample_ancestry, split_workflow,
# standards_blank_rules, throughput

make test
# 68 passed

make lint
# All checks passed

make type
# mypy success and VS Code extension tsc success

git -C /Users/joseph/ngs_lab_automation status --short
# ?? .DS_Store
```

## Final Classification

`successful`
