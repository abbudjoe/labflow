# Stage 2 Assembly Review

Review date: 2026-06-08

Stage: `02_core_domain_migration`

Authoritative spec: `.codex_build/prompts/02_core_domain_migration.md`

Status: `successful`

## Target Contract

Stage 2 migrates the deterministic domain foundation into `packages/labflow-core`: units, wells, containers, samples, statuses, exceptions, audit records, LIMS registry, ancestry, and manifest validation. It must add behavior tests and keep `labflow-core` free of LLM, RAG, and agent dependencies.

## Extracted DoD Checklist

| DoD item | Status | Evidence |
| --- | --- | --- |
| Inspect reference domain/LIMS modules | met | Read reference units, wells, containers, samples, statuses, exceptions, batches, registry, ancestry, and manifests under `/Users/joseph/ngs_lab_automation`. |
| Implement `domain/units.py` | met | Added canonical units and liquid-handling constants plus `required_source_volume_ul()`. |
| Implement `domain/wells.py` | met | Added `WellCoordinate`, `parse_well()`, `default_standard_wells()`, deterministic ordering, and plate well helper. |
| Implement `domain/containers.py` | met | Added Matrix 96 x 1 mL screwtop and rubber/septum container type models. |
| Implement `domain/samples.py` | met | Added typed sample and normalization sample input records with well parsing and sample ID validation. |
| Implement `domain/statuses.py` | met | Added analyte, workflow, status, normalization mode, exception code, severity, and ancestry event enums. |
| Implement `domain/exceptions.py` | met | Added structured exception record with code, severity, message, batch, sample, source/destination, suggested action, and robot-transfer blocking flag. |
| Implement `domain/audit.py` | met | Added deterministic audit event model and actions for later tool/approval stages. |
| Implement `lims/registry.py` | met | Added container type/container registry with default Matrix types, barcode resolution, and unknown-container failures. |
| Implement `lims/ancestry.py` | met | Added ancestry records, tracker, split parent/child recording, metadata serialization, and row output. |
| Implement `lims/manifests.py` | met | Added CSV helpers, exception report writer, duplicate manifest validation, and mode/location contract validation. |
| Valid wells A1-H12 | met | `test_valid_wells_parse_normalize_and_sort` and invalid-well parameterized test passed. |
| Default standards A1-H1 | met | `test_default_standard_well_order_is_a1_through_h1` passed. |
| Matrix screwtop and rubber/septum container types | met | `test_matrix_container_types_and_max_volume` passed. |
| Max working volume 999 uL | met | Container test verifies `999.0` and max-not-over-nominal validation. |
| Minimum transfer 1 uL, residual 2 uL, aspiration margin 1 uL | met | `test_required_source_volume_formula_uses_transfer_dead_volume_and_margin` passed. |
| Sample ancestry by sample ID | met | `test_ancestry_parent_child_record_by_sample_id` passed. |
| Duplicate sample/source/destination policies | met | `test_duplicate_manifest_validation_flags_all_duplicate_policies` passed. |
| Exception records include code, severity, message, sample, batch, source/destination, suggested action | met | `test_exception_record_serializes_batch_sample_locations_and_action` passed. |
| Domain tests pass | met | `make test`: 44 passed on the current tree; Stage 2 domain tests include whitespace identifier/location regressions. |
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

- `make test`: 44 passed.
- `make lint`: all checks passed.
- `make type-python`: no issues found in 33 source files.
- `make type`: Python mypy plus VS Code compile passed.
- `labflow-core` runtime dependency added: `pydantic>=2.8`.
- Reference repo was not modified by this stage; status showed only an untracked `.DS_Store`, which was not touched.

## Review Findings

Reviewer: Hegel (`019ea8f9-ec3e-7f83-99d9-79644a786bdd`).

Initial retroactive review found one valid Stage 2 contract issue:

- Whitespace-only identifiers satisfied required identity/location contracts. `NormalizationSampleInput`, `Container`, and `AncestryRecord` accepted blank-looking IDs, and `validate_mode_location_contract()` treated whitespace destination container IDs as present.

Fixes applied:

- Added shared identifier normalization in `labflow_core.domain.identifiers`.
- Required container IDs, barcodes, sample IDs, source container IDs, ancestry child sample IDs, ancestry batch IDs, exception text, and audit identifiers now reject whitespace-only values.
- Optional destination/provenance IDs now canonicalize whitespace-only values to missing values.
- Added regressions for whitespace container IDs/barcodes, whitespace source container IDs, whitespace destination container IDs treated as missing, and whitespace ancestry child/batch IDs.

Final reviewer outcome: clean. No blocking findings remain.

## Notes

- The new exception model intentionally includes optional `batch_id` and `suggested_action` because Stage 2 requires batch context and suggested action. A read-only `recommended_action` property is provided for compatibility with reference-style terminology.
- The audit module is deterministic and minimal in this stage. Later agent/tool stages can expand event ownership and persistence without changing the Stage 2 domain contract.

## Subagent Review

Retroactive subagent review requested by the user on 2026-06-08.

Reviewer:

- Tooling: `multi_agent_v1`
- Reviewer: Hegel
- Agent id: `019ea8f9-ec3e-7f83-99d9-79644a786bdd`
- First pass verdict: `review-failed` / `partial`
- Final pass verdict: clean / approve

Reviewer classification:

| Mapped Stage 2 DoD item | Reviewer status |
| --- | --- |
| Inspect reference domain/LIMS modules without modifying reference repo | met |
| Implement domain units, wells, containers, samples, statuses, exceptions, audit | met |
| Implement LIMS registry, ancestry, manifests | met |
| Enforce valid wells A1-H12 and default standards A1-H1 | met |
| Model Matrix 96 x 1 mL screwtop and rubber/septum types with 999 uL max working volume | met |
| Enforce liquid-handling constants and required source volume formula | met |
| Support sample ancestry by sample ID | met |
| Support duplicate sample/source/destination manifest validation policies | met |
| Exception records include code, severity, message, sample, batch, source/destination, suggested action | met |
| Add tests for required Stage 2 behavior | met |
| Domain tests pass | met |
| No LLM/RAG/agent/API dependency exists in `labflow-core` | met |

Reviewer findings:

- No blocking findings.
- Residual risk: review is retrospective and lacks a frozen Stage 2 commit snapshot, so conclusions rely on the current tree plus provided evidence.

Post-review evidence:

- `make test`: 44 passed on the current tree.
- `make lint`: all checks passed.
- `make type-python`: no issues found in 33 source files.
- `make type`: Python mypy success and VS Code extension compile success.
- `rg -n "openai|langchain|llm|labflow_rag|labflow_agent|labflow_api" packages/labflow-core`: no matches.
- `git -C /Users/joseph/ngs_lab_automation status --short`: only `?? .DS_Store`; reference repo was not modified.

## Final Classification

Stage 2 status: `successful`

All required Stage 2 DoD items are `met`; no items are `partial`, `blocked`, or `not-started`.
