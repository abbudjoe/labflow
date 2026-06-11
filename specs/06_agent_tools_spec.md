# Agent Tool Specification

## Tool registry

Tools should be deterministic wrappers around core functions. The LLM selects tools, but tool behavior is deterministic.

## Required tools

```python
validate_workflow(workflow_yaml: str) -> ValidationResult
validate_batch(batch_id: str | None, workflow_yaml: str | None) -> BatchValidationResult
parse_varioskan_tsv(file_path: str, schema_mapping: dict) -> ParsedVarioskanResult
process_quantification(config_path: str) -> QuantificationResult
generate_normalization_plan(config_path: str) -> NormalizationPlanResult
process_rna_requant(config_path: str) -> RnaRequantResult
generate_janus_csv(plan_id: str, dry_run: bool, approval_token: str | None) -> ArtifactResult
compare_throughput(config_path: str) -> ThroughputComparisonResult
explain_exception_code(exception_code: str) -> ExceptionExplanation
run_eval_suite(suite_id: str) -> EvalRunResult
```

## Tool result shape

Every tool returns structured JSON:

```json
{
  "ok": false,
  "tool_name": "generate_janus_csv",
  "status": "blocked",
  "errors": [
    {
      "code": "MISSING_CONCENTRATION",
      "message": "Sample RNA_004 has no concentration."
    }
  ],
  "artifacts": [],
  "audit_event_id": "audit_123"
}
```

## Tool policies

- `validate_*` tools are read-only.
- `parse_*` tools are read-only unless writing parsed artifacts, in which case dry-run policy applies.
- `generate_janus_csv` requires deterministic valid batch.
- State-changing tools require `dry_run=true` first.
- Commit mode requires valid approval token.
- Every call writes audit event.

## Agent response structure

Agent responses should include:

- concise answer;
- structured tool results when tools were called;
- cited knowledge sources when claims are made;
- next safe action;
- blocked action reason if applicable.
