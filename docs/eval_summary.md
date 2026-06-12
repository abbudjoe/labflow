# Portfolio Eval Summary

This summary curates the eval evidence a reviewer should read first. Raw JSON artifacts remain available for audit, but the portfolio story should start here.

## Canonical Artifacts

- `semantic_generalization_live`: Historical live semantic/generalization evidence after frozen keyword baseline reporting; not a Stage 19.1 live release claim.
- `grounded_answer_quality_live`: Historical live grounded-answer evidence after Stage 18.14 claim and source-family hardening; not a Stage 19.1 live release claim.
- `repair_planning_live`: Historical live repair-planning evidence with dry-run patch/refusal safety checks; not a Stage 19.1 live release claim.
- `stage19_1_offline_ladder`: Current Stage 19.1 local/offline reliability evidence. It intentionally fails the downstream QC release gate on semantic QC tool correctness; live release evidence is pending an explicitly authorized live run.
- `rag_retrieval_sop_check`: Retrieval-only corpus check after SOP alignment work.
- `rag_retrieval_stage19_demo`: Checked-in retrieval-only demo evidence including Stage 19 downstream QC provenance golden cases.

## Results

| Artifact | Suite | Provider | Pass Rate | Safety | Provider Failures | Schema Failures | Unsupported Claims | Fallback | Mean Score | Acceptance Margin | Latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| semantic_generalization_live | semantic_generalization | openrouter | 26/26 (100.0%) | 0 | 0 | 0 | 0 | 0 | 1.000 | 0.220 | p50=2766.391; p95=12484.235; max=18785.135 |
| grounded_answer_quality_live | grounded_answer_quality | openrouter | 21/21 (100.0%) | 0 | 0 | 0 | 0 | 0 | 0.986 | 0.238 | p50=2982.698; p95=21578.842; max=34861.695 |
| repair_planning_live | repair_planning | openrouter | 8/8 (100.0%) | 0 | 0 | 0 | 0 | 0 | 1.000 | 0.000 | p50=0.000; p95=0.000; max=0.000 |
| rag_retrieval_sop_check | retrieval_only | local_rag | 40/40 (100.0%) | 0 | 0 | 0 | 0 | n/a | 1.000 | n/a | p50=0.6ms; p95=0.9ms; max=0.9ms |
| rag_retrieval_stage19_demo | retrieval_only | local_rag | 45/45 (100.0%) | 0 | 0 | 0 | 0 | n/a | 1.000 | n/a | p50=0.8ms; p95=1.1ms; max=2.1ms |

## Enterprise RAG Diagnostics

- The portfolio RAG surface includes `/rag/debug` for retrieval inspection: query normalization, top chunks, source-family counts, stale-source flags, and source-conflict notices.
- `knowledge/legacy_missing_concentration_sop.md` is a synthetic retired fixture used to demonstrate stale SOP handling and policy-vs-SOP precedence without using proprietary lab material.
- Conflict handling is intentionally conservative: when retrieved sources disagree on a policy-critical rule, the answer surfaces the conflict with citations instead of silently picking the convenient source.
- Stage 19 adds downstream QC provenance retrieval cases for synthetic summary metrics, lab-to-analysis lineage, unmatched sample IDs, and no-causal-inference boundaries.
- Stage 20 adds corpus manifests and corpus fingerprints to RAG eval reports, plus a local corpus drift suite for irrelevant additions, source renames, conflicting SOPs, removed sources, updated sources, and stale SOPs.
- Optional Pinecone backend comparison is available for retrieval infrastructure experiments, but local hybrid retrieval remains the default evidence path.

## Interpretation

- Portfolio demo bar: safety-control behavior should be perfect, active-provider safety/provider/schema failures should be zero, and any unsupported answer should be explicit rather than fabricated.
- Production bar: this would need broader adversarial coverage, tenant/auth controls, monitored drift, incident playbooks, and baselines promoted through human approval.
- Latency/cost tradeoff: deterministic paths are fastest and free; live OpenRouter evidence demonstrates model compatibility but has variable latency. Cost is not measured in these artifacts because the tested free model/provider path did not emit reliable cost metadata.
- Deterministic baseline and frozen keyword baseline are comparison evidence. The active provider production gate is reported separately to avoid mistaking baseline failures for current model failures.
- Corpus lifecycle evidence is generated separately with `make corpus-drift-eval`. It should pass before treating answer-quality regressions as model-only issues.

## Residual Risks

- The curated raw artifacts are local generated evidence and are ignored by Git unless intentionally exported.
- Frozen baseline rotation should remain explicit and human-reviewed so eval targets do not drift with implementation changes.
- Live model behavior can vary by provider availability, model version, and latency.
- Hosted vector indexes can drift from the local corpus if metadata, namespace, or fingerprint checks are not enforced.

## Manifest

- Manifest version: `0.1.0`
- Manifest path: `docs/portfolio_artifact_manifest.json`
