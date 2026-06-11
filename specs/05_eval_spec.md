# Evaluation Specification

## Purpose

The eval harness measures whether the AI/LIMS system retrieves the right documents, cites them, answers according to doctrine, and calls tools correctly.

## Eval categories

1. Retrieval recall.
2. Citation precision.
3. Answer rule matching.
4. Unsupported-claim detection.
5. Tool-call correctness.
6. Guardrail/policy compliance.
7. Regression comparison across prompt/model/retrieval changes.

## Golden eval case shape

```yaml
- id: q_split_001
  category: split_workflow
  question: "What happens when calculated sample transfer volume is below 1 uL?"
  required_sources:
    - rna_norm_requant_sop.md
    - exception_handling_manual.md
  expected_answer_contains:
    - "split workflow"
    - "1 uL"
    - "child sample"
    - "re-quant"
    - "follow-up normalization"
  disallowed_answer_contains:
    - "round silently"
    - "molar"
  required_tool_calls: []
```

## Metrics

```json
{
  "eval_run_id": "eval_2026_06_08_001",
  "retrieval_recall_at_k": 0.92,
  "citation_precision": 0.88,
  "answer_rule_match": 0.94,
  "unsupported_claim_count": 0,
  "tool_call_correctness": 1.0,
  "latency_ms_p50": 420,
  "latency_ms_p95": 900
}
```

## Regression reports

Each eval run should compare against a baseline when available.

Regression thresholds:

- retrieval recall drops > 5 percentage points;
- citation precision drops > 5 percentage points;
- unsupported claims > 0 for safety-critical cases;
- invalid tool call generated for guarded action.
