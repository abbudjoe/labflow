# Stage 18.11 Execution Interpretation

Status: implemented; clean assembly review complete

## Evidence Artifacts

No-live full ladder:

- JSON:
  `artifacts/inference_eval_ladders/inference_eval_ladder_20260611T051135393404Z.json`
- SHA-256:
  `dba149ddd4df914d0b5018f9906dea966a7fdea4774a67ba73542b34af01925b`

Live repair-planning opt-in suite:

- JSON:
  `artifacts/inference_eval_ladders/inference_eval_ladder_20260611T051248025696Z.json`
- SHA-256:
  `04e0331871cdc9c13d4f28b0a368be1fb8d9d8517d66d97985df91664d4319bf`

Full live ladder:

- JSON:
  `artifacts/inference_eval_ladders/inference_eval_ladder_20260611T052645113668Z.json`
- SHA-256:
  `a48b8f94dceddbf3806fee4a26eec09b557a45ebf5bca792d4e08a8e5a361e00`

## What Changed

- Control parity now separates raw diagnostics from gate-failure diagnostics.
  `model_retrieval_query_sanitized` remains visible but no longer fails the
  control gate.
- Unknown or unclassified diagnostics fail closed as gate failures.
- Semantic cases now support typed retrieval intent atoms and trace fields:
  final retrieval query, model retrieval-query preview, policy action,
  accepted/rejected terms, corpus expansion families, answer, intent matches,
  and required-source ranks.
- OpenRouter retrieval expansion can use a corpus-backed deterministic synonym
  map with provenance in diagnostic details.
- Grounded answer validation now distinguishes positive readiness claims from
  safe blocked artifact statements such as robot-ready artifacts remaining
  blocked.
- Grounded fallback artifacts include sanitized rejected-draft debug previews.
- Grounded answer quality uses claim-level citation recall as the primary
  citation signal and reports broader source-family recall separately.
- Fixed grounded contexts can supplement declared required source families from
  local retrieval, removing the permanent split-workflow context-unwinnable
  exclusion.
- Repair planning has first-class schema-failure reporting and an explicit
  `--confirm-live-repair-planning` gate for live repair runs.
- Semantic provider diagnostics are now aggregated at provider level and
  separated into raw counts, gate-failure counts, and severity counts.
- Repair acceptance now rejects fixture providers and computes the acceptance
  gate only on paired blind repair cases.
- Corpus-backed semantic expansion diagnostics now include doctrine-rule IDs
  and exact supporting corpus phrases.
- Missing-fact answer validation accepts safe negative statements such as
  `cannot invent` while still rejecting positive inference or invention.
- Claim/answer rule matching accepts safe negative paraphrases such as
  `prohibits inferring`.
- Added fresh blind acceptance cases:
  - 10 semantic/generalization cases;
  - 10 grounded-answer cases;
  - 5 repair-planning cases.

## Result Summary

### No-Live Full Ladder

The no-live run completed without provider calls.

- Aggregate: `87` pass, `12` fail across `99` suite executions.
- Provider failures: `0`.
- Schema failures: `0`.
- Safety violations: `0`.
- Context-unwinnable cases: `0`.
- Live inference cases: `0`.

Interpretation: local/offline plumbing is intact. Fixture providers are still
reported separately and are not treated as live acceptance evidence.

### Full Live Ladder

OpenRouter model:

```text
nvidia/nemotron-nano-9b-v2:free
```

Aggregate:

- `94` pass, `5` fail across `99` suite executions.
- Provider failures: `0`.
- Schema failures: `0`.
- Safety violations: `0`.
- Unsupported claims: `0`.
- Context-unwinnable cases: `0`.
- Live inference cases: `29`.
- Acceptance-eligible cases: `25`.

Suite results:

| Suite | Result | Interpretation |
| --- | ---: | --- |
| `control_parity` | OpenRouter `62/62`, gate `true` | Safety-critical planner parity passed. Sanitized retrieval diagnostics did not fail the gate. |
| `semantic_generalization` | OpenRouter `16/16`, mean `0.956` vs deterministic `0.884` | Inference shows real semantic lift, including blind semantic cases. The overall mean margin was `+0.072`; the blind acceptance margin was `+0.095`, below the configured `+0.10` gate. Planner diagnostics were `info=16`, `gate_failure=0`. |
| `grounded_answer_quality` | OpenRouter `8/13`, mean `0.788` vs deterministic `0.667` | Inference improved answer quality but still failed the gate because one groundedness failure and one fallback remain. |
| `repair_planning` | Fixture only in full ladder | Live repair is measured separately by the opt-in repair artifact. |

### Live Repair Planning

The separate opt-in live repair suite passed:

- OpenRouter `8/8`.
- Mean score: `1.0`.
- Paired blind repair acceptance gate: `true`.
- Provider failures: `0`.
- Schema failures: `0`.
- Safety violations: `0`.
- Blind repair acceptance cases: `5`.

Interpretation: after tightening the schema prompt and reporting schema
failures separately, the live repair proposer can produce safe dry-run patches
or safe refusals for this repair suite. Deterministic validation still decides
whether a patch improves a workflow.

## What This Proves

- The eval ladder now has cleaner control-plane semantics: benign provenance
  diagnostics are visible but do not fail safety gates, while unknown
  diagnostics fail closed.
- The project now has a fresh blind acceptance surface instead of relying only
  on inspected diagnostic cases.
- The live model can beat the deterministic baseline on semantic/generalization
  and grounded-answer mean scores in this run.
- The live model can satisfy the repair-planning suite when constrained by the
  typed dry-run proposal schema.

## What This Does Not Prove

- It does not prove broad inference superiority yet. Semantic and grounded
  blind margins improved but did not meet the configured `+0.10` acceptance
  gate.
- It does not prove grounded answer quality is solved. OpenRouter still had
  groundedness/fallback failures in grounded answer quality.
- It does not make model output authoritative over lab truth. All lab decisions
  remain owned by deterministic validators.
- It does not authorize production, clinical, or robot execution use.

## Next Fix Targets

- Inspect grounded cases with groundedness failures:
  - `grounded_robot_ready_001`;
  - `grounded_blind_robot_ready_001`.
- Inspect grounded cases with low score despite no hard failure:
  - split rounding explanation;
  - invalid transfer rows;
  - JANUS blocked blind case.
- Decide whether the semantic margin gate should remain `+0.10` or whether a
  larger blind suite should be added before changing thresholds.
- Keep blind cases frozen; do not tune prompts or expansion maps against them.
