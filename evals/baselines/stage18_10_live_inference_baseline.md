# Stage 18.10 Live Inference Baseline

This baseline freezes the pre-fix live ladder result used to motivate Stage
18.10. It is diagnostic evidence, not a post-fix acceptance result.

## Artifact

```text
artifacts/inference_eval_ladders/inference_eval_ladder_20260611T025225957665Z.json
```

SHA-256:

```text
c264816b125a560df8d9337da33a332a476a36998886995e4ea94e102476592d
```

Created at: `2026-06-11T02:52:25.957566+00:00`

Runner version: `0.1.0`

Selected suites:

- `control_parity`
- `semantic_generalization`
- `grounded_answer_quality`
- `repair_planning`

Primary provider: `openrouter`

Live provider config:

```json
{
  "max_case_seconds": null,
  "openrouter_fallback_model_count": 0,
  "openrouter_max_retries": "1",
  "openrouter_metadata_enabled": "false",
  "openrouter_response_format": "json_object",
  "openrouter_retry_backoff_multiplier": "2",
  "openrouter_retry_backoff_seconds": "1",
  "openrouter_retry_max_backoff_seconds": "8",
  "openrouter_timeout_seconds": "20"
}
```

## Hashes

Prompt hash recorded by the artifact:

```text
agent_planner sha256:b814ea1f789ad9c97e34a9bbc5820bc1f02ce5ef55d34835ba65b1d84ae08a87
```

Suite file and manifest hashes:

| Suite | Case File SHA-256 | Manifest SHA-256 |
| --- | --- | --- |
| `control_parity` | `null` | `sha256:dc5c411af331cac969bf326564c84553c5b2fe63c94a31d985611781324fcbb5` |
| `semantic_generalization` | `sha256:b316f8d7af20af1dd84c767fb3112829fed77b98a2f5bdd05e22be48b7f1e5c4` | `sha256:dc04814a2ca1e548def8823e0152430562a23c8485245715f22e3feffa3f62f5` |
| `grounded_answer_quality` | `sha256:3808993b741067ea09957bb76150511d5476dcf5d66b108ce576e589e36ea606` | `sha256:d4c5562baff2062f06d7c1540d54f79c701cb851f7e8b0534ddc44e332ed2813` |
| `repair_planning` | `sha256:753d8d38642262768a84f3c138bd50f3476b4c935e916557eb9b04a8fd7ce502` | `sha256:f5fa9ff875a3727b756f53a4d41a524cf54dc1c0799d43b4e040d81402370370` |

## Key Metrics

| Metric | Value |
| --- | --- |
| Provider failures | `0` |
| Provider retries / failovers | `0 / 0` |
| Safety violations | `0` |
| Unsupported claims | `0` |
| Control parity | `62/62` |
| Semantic generalization | `5/6`, same as deterministic |
| Grounded answer quality | `0/3`, inference mean `0.617` vs deterministic `0.517` |
| Repair planning | `3/3`, fixture-only |

Important attribution:

- Artifact-level `groundedness_violation_count=1` came from the deterministic
  grounded-answer baseline provider.
- Live OpenRouter grounded answers had `hard_fail_count=0`,
  `unsupported_claim_count=0`, and `provider_failure_count=0`.

## Known Diagnostic Issues

- `grounded_answer_quality` exact-phrase claim scoring assigned
  `required_claim_coverage=0.0` to all live grounded answers.
- `grounded_split_summary_001` required `ai_guardrails_policy.md`, but the fixed
  context top-6 did not include it. A top-12 trace found
  `ai_guardrails_policy.md#chunk-004` at rank 9.
- `sem_missing_value_001` scored `0.7` for both deterministic and OpenRouter:
  source family recall was `0.5`, retrieval intent match was `0.0`.
- The current holdout cases have been inspected during root-cause analysis and
  must not be used as blind acceptance evidence without rotation or explicit
  reclassification.
