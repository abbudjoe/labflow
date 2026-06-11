# Migration Inspection

Stage: `00_preflight_and_plan`

Target repo: `/Users/joseph/labflow`

Reference repo: `/Users/joseph/ngs_lab_automation`

## Stage 0 Status

- Governing docs inspected: `AGENTS.md`, `DOCTRINE.md`, `ENGINEERING.md`, `DECISIONS_LOCKED.md`, `PROJECT_PLAN.md`, `specs/01_architecture.md`, and `specs/02_core_engine_spec.md`.
- Target repository inspected: existing root docs, `.codex_build` prompts, `knowledge/`, `evals/`, `examples/`, and `specs/`.
- Reference repository inspected: deterministic domain, LIMS, quantification, normalization, robot export, throughput, tests, examples, and generated outputs.
- Scope held: planning document only; no implementation code added.
- Source repository mutation: none.

## Source Modules Found

### Units and Constants

- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/domain/units.py`
  - Canonical units: `ng_per_ul`, `ul`, `ng`.
  - Transfer constants: minimum transfer `1.0 uL`, residual dead volume `2.0 uL`, aspiration safety margin `1.0 uL`, destination max working volume `999.0 uL`.
  - `required_source_volume_ul()` encodes transfer plus dead volume plus aspiration margin.
  - `assert_supported_units()` is a simple canonical-unit guard.

### Wells

- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/domain/wells.py`
  - Validates A1-H12 with `WellCoordinate`.
  - Normalizes rows to uppercase.
  - Provides deterministic row-major sorting with `sort_key`.
  - Provides default standards wells `A1` through `H1`.

### Containers

- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/domain/containers.py`
  - Defines `ContainerType` and `Container`.
  - Models Matrix 96 x 1 mL screwtop and septum/rubber-top racks.
  - Enforces `96_well` format and max working volume not exceeding nominal capacity.
- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/lims/registry.py`
  - Resolves container IDs/barcodes to registered container types.
  - Provides defaults for Matrix rack families.
  - Avoids silently defaulting unknown containers during planning if they are not registered.

### Samples, Batches, Statuses, and Exceptions

- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/domain/samples.py`
  - Defines `Sample` and `NormalizationSampleInput`.
  - Requires sample ID, source container, source well, stock concentration, and available volume for normalization rows.
- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/domain/batches.py`
  - Defines `Batch` with deterministic created-at timestamp for repeatable examples.
- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/domain/statuses.py`
  - Defines analytes, workflow types, normalization modes, statuses, exception codes, and ancestry event types.
- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/domain/exceptions.py`
  - Defines structured `ExceptionRecord`.
  - Serializes exception reports with explicit source/destination locations and `blocks_robot_transfer`.

### LIMS Registry, Manifests, and Ancestry

- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/lims/registry.py`
  - Source of truth for container lookup and type resolution.
- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/lims/ancestry.py`
  - Tracks ancestry by sample ID.
  - Records split parent/child relationships and normalized/re-quantified events.
- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/lims/manifests.py`
  - Reads and writes deterministic CSVs.
  - Detects duplicate sample IDs, duplicate source wells, and duplicate destination wells.
  - Enforces mode/location contracts for standard versus in-place normalization.

### Varioskan TSV Parsing

- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/quant/varioskan.py`
  - Defines configurable TSV column mapping.
  - Parses Varioskan readings into typed records.
  - Sorts readings deterministically by plate and well.

### Standard Curves

- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/quant/standards.py`
  - Fits a linear batch-level standard curve.
  - Requires configured standard wells, including the zero standard when present.
  - Blank-corrects standards by subtracting the zero-standard reading.
  - Rejects non-positive slopes.
  - Tracks standard curve min/max corrected reading and concentration range.

### Quant Processors

- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/quant/processors.py`
  - Loads quantification config.
  - Parses standards and sample plates.
  - Requires each sample plate blank.
  - Applies blank correction, linear curve concentration, dilution factor, and stock concentration.
  - Flags out-of-range readings.
  - Writes quant results, stock concentration manifest, exception report, ancestry, and curve summary.

### Normalization Targets and Planners

- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/norm/targets.py`
  - Supports exactly one target mode: final concentration plus volume, or final mass plus volume.
  - Rejects molar/molecule-size fields such as `nM`, `fmol`, `pmol`, `molarity`, and `molecular_weight`.
- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/norm/planner.py`
  - Loads normalization config and sample CSVs.
  - Parses row-level errors into structured blocking exceptions.
  - Plans standard new-container normalization with sample and diluent volumes.
  - Blocks low concentration, invalid concentration, insufficient source volume, destination overflow, unknown container, duplicate locations, and invalid mode/location combinations.
  - Selects in-place normalization when available source volume is less than or equal to the standard transfer and no destination is supplied.
  - Creates split workflow rows when calculated direct transfer is below `1 uL`.
  - Writes normalization plans, exception reports, ancestry, and audit manifests.

### Split Workflow

- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/norm/split.py`
  - Enforces exactly `1 uL` split source transfer.
  - Calculates split diluent volume and expected child concentration.
- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/norm/planner.py`
  - Creates child ID suffix `-SPLIT1`.
  - Adds split-required and split-requant-required exceptions.
  - Records parent/child ancestry and marks follow-up re-quant requirement.

### RNA Re-quant

- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/norm/planner.py`
  - `RnaRequantPolicy`, `RequantResultRow`, `RnaWorkflowResult`, `load_rna_requant_config()`, and `process_rna_workflow()` implement RNA re-quant behavior.
  - Expected re-quant IDs come from normalized rows or split child IDs.
  - Valid re-quant concentration becomes downstream concentration.
  - Missing, invalid, unexpected, out-of-assay-range, or downstream-impossible results enter manual review.

### JANUS Export and Protocol IR

- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/robots/janus.py`
  - Emits minimal JANUS-style CSV rows: `well`, `diluent_volume_ul`, `sample_volume_ul`.
  - Emits audit worklist rows with batch/sample/source/destination/status/mode.
  - Filters rows where `generates_robot_transfer` is false.
- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/robots/protocol_ir.py`
  - Builds robot-agnostic protocol steps.
  - Orders standard destination transfers as diluent, sample, mix.
  - Treats in-place as diluent-only to source well with no mix.
  - Treats split as diluent plus split transfer.

### Batch Readiness and Throughput Simulation

- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/throughput/simulator.py`
  - Evaluates named readiness gates.
  - Simulates elapsed time, robot busy/idle time, utilization, and samples per hour.
  - Compares single-container baseline to optimized multi-container scenarios.
- `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/throughput/metrics.py`
  - Defines throughput metric and comparison models.

### Tests and Synthetic Examples

- `/Users/joseph/ngs_lab_automation/tests/unit/test_domain.py`
  - Well parsing/order, container volume validation, sample ID requirement, enum serialization, exception reporting.
- `/Users/joseph/ngs_lab_automation/tests/unit/test_lims.py`
  - Registry resolution, split ancestry, duplicate sample/source/destination blocking.
- `/Users/joseph/ngs_lab_automation/tests/unit/test_quantification.py`
  - Standard curve fitting, missing standard, blank correction, dilution factor, missing blank, out-of-range readings.
- `/Users/joseph/ngs_lab_automation/tests/unit/test_normalization.py`
  - Target modes, standard normalization math, low concentration, destination overflow, source volume with dead volume and margin, unknown containers, invalid manifest rows, in-place, split, split volume limits.
- `/Users/joseph/ngs_lab_automation/tests/unit/test_robot_exports.py`
  - JANUS excludes invalid rows, duplicate participants generate no transfers, in-place and split export semantics.
- `/Users/joseph/ngs_lab_automation/tests/unit/test_rna_requant.py`
  - RNA re-quant downstream update and missing/invalid/out-of-range/downstream-impossible handling.
- `/Users/joseph/ngs_lab_automation/tests/unit/test_throughput.py`
  - Throughput improvement, partial final batch, readiness gate blocking.
- `/Users/joseph/ngs_lab_automation/tests/integration/test_cli_examples.py`
  - End-to-end CLI examples over synthetic inputs and outputs.
- `/Users/joseph/ngs_lab_automation/examples/`
  - Synthetic CSV/TSV/YAML examples for quantification, normalization, RNA re-quant, and throughput.

## Recommended Migration Map

### `packages/labflow-core`

Target package namespace: `labflow_core`.

Port behavior, not old package names. Preserve deterministic contracts and tests while reshaping the modules around the new architecture.

| Target module | Reference source | Migration recommendation |
| --- | --- | --- |
| `labflow_core.domain.units` | `domain/units.py` | Port constants and required source volume function. Keep molarity absent. Prefer literal canonical unit enums or typed constants so validators can inspect unit support. |
| `labflow_core.domain.wells` | `domain/wells.py` | Port `WellCoordinate`, parsing, deterministic sort, and standards default A1-H1. Add tests for lowercase normalization and invalid wells. |
| `labflow_core.domain.containers` | `domain/containers.py` | Port `ContainerType`, `Container`, Matrix rack factories. Keep 999 uL max working volume. |
| `labflow_core.domain.samples` | `domain/samples.py` | Port sample and normalization input models. Consider splitting external CSV row ingestion from validated internal sample state. |
| `labflow_core.domain.statuses` | `domain/statuses.py` | Port enums, but review names for API stability before use by DSL and agent. |
| `labflow_core.domain.exceptions` | `domain/exceptions.py` | Port structured exception records. Keep explicit `blocks_robot_transfer`. |
| `labflow_core.domain.audit` | no direct reference equivalent | New module. Define deterministic audit event records early because later agent/API stages require every tool call and manual override to be audited. |
| `labflow_core.domain.batches` | `domain/batches.py` | Port batch identity/workflow model; avoid deterministic timestamps outside tests unless explicitly needed for reproducible examples. |
| `labflow_core.lims.registry` | `lims/registry.py` | Port registry with explicit container type resolution. Unknown containers must block, not auto-infer. |
| `labflow_core.lims.ancestry` | `lims/ancestry.py` | Port ancestry records/tracker. Keep split metadata and sample-ID lineage. |
| `labflow_core.lims.manifests` | `lims/manifests.py` | Port CSV helpers and duplicate/mode-location validators. Consider returning typed load results instead of mixing CSV IO with validation. |
| `labflow_core.quant.varioskan` | `quant/varioskan.py` | Port schema mapping, reading model, parser, deterministic ordering. |
| `labflow_core.quant.standards` | `quant/standards.py` | Port linear regression and standard curve result. Add explicit A1-H1 default standard layout contract. |
| `labflow_core.quant.processors` | `quant/processors.py` | Port blank correction, dilution, stock concentration, out-of-range exceptions, and ancestry. Separate pure processing from file writers. |
| `labflow_core.norm.targets` | `norm/targets.py` | Port two target modes only. Keep molar fields rejected. |
| `labflow_core.norm.split` | `norm/split.py` | Port split config and expected child concentration. |
| `labflow_core.norm.planner` | `norm/planner.py` | Port planning behavior, but split the monolith into smaller internal helpers for ingest validation, transfer math, mode selection, and row generation. |
| `labflow_core.norm.requant` | `norm/planner.py` RNA section | Extract RNA re-quant into its own module. Preserve downstream concentration update and manual-review branches. |
| `labflow_core.robots.protocol_ir` | `robots/protocol_ir.py` | Port protocol IR. Keep operation ordering deterministic. |
| `labflow_core.robots.janus` | `robots/janus.py` | Port row formatting, but put robot-ready artifact generation behind batch validation rather than relying only on row filtering. |
| `labflow_core.throughput.readiness` | `throughput/simulator.py` | Extract readiness gates into a separate module. |
| `labflow_core.throughput.simulator` | `throughput/simulator.py` | Port deterministic throughput calculations. |
| `labflow_core.throughput.metrics` | `throughput/metrics.py` | Port metric models. |
| `labflow_core.dsl.models/parser/validator` | new in target specs | Build fresh from `specs/03_workflow_dsl_spec.md` in Stage 4. The reference repo uses workflow config YAMLs but not the final LabFlow DSL. |
| `labflow_core.tools.core_tools` | new in target specs | Build tool wrappers after deterministic APIs exist. Tool wrappers must call core validators and generate audit-ready results. |

### `packages/labflow-rag`

Build fresh from the target knowledge corpus and `specs/04_rag_spec.md` / `specs/05_eval_spec.md`. The reference repo has docs and examples that can inform synthetic content, but the RAG layer should use `knowledge/*.md` in the new repo, preserve citations, and support no-answer behavior.

### `packages/labflow-agent`

Build fresh from `specs/06_agent_tools_spec.md` and `specs/07_guardrails_audit_spec.md`. The agent must wrap `labflow_core.tools` and must not duplicate lab truth. Reference deterministic functions are useful only behind typed tools.

### `apps/api`

Build fresh as a FastAPI boundary. Reference `/Users/joseph/ngs_lab_automation/src/ngs_lab_automation/api/` may be inspected later for demo shape, but the new API should expose the target contracts: validation, tool execution, RAG query, eval run, audit retrieval, and artifact access.

### `apps/vscode-extension`

Build fresh. The reference repo's web app is not the target primary UX. The VS Code extension should stay thin and call the local API for validation, AI explanation, dry-run artifact generation, and eval commands.

## Target Monorepo Structure

Create the target structure in Stage 1:

```text
labflow/
  README.md
  AGENTS.md
  ENGINEERING.md
  DOCTRINE.md
  PRODUCT_REQUIREMENTS.md
  PROJECT_PLAN.md
  DECISIONS_LOCKED.md
  PLANS.md
  docs/
    migration_inspection.md
    case_study.md
  packages/
    labflow-core/
      pyproject.toml
      src/labflow_core/
      tests/
    labflow-rag/
      pyproject.toml
      src/labflow_rag/
      tests/
    labflow-agent/
      pyproject.toml
      src/labflow_agent/
      tests/
  apps/
    api/
      pyproject.toml
      src/labflow_api/
      tests/
    vscode-extension/
      package.json
      tsconfig.json
      src/
      test/
  knowledge/
  evals/
  examples/
  infra/
  scripts/
```

Root package tooling should support local-first development with Python 3.12, pytest, ruff, and no cloud credentials. Each Python package should be importable independently, with `labflow-core` free of RAG, agent, API, model, and LLM dependencies.

## Risks and Assumptions

- The reference `norm/planner.py` is behavior-rich but too monolithic for the new architecture. Migration should extract explicit primitives rather than copy the whole file shape.
- JANUS export in the reference filters invalid rows, but the target doctrine requires deterministic validation before robot-ready artifact generation. Stage 5 and later should enforce this at a validation/tool boundary.
- CSV file IO and pure deterministic logic are mixed in the reference. The target should separate parser/loaders, validators, planners, and writers so the API/agent/DSL can call deterministic functions without filesystem coupling.
- RNA re-quant currently lives inside the normalization planner. The target should make re-quant a first-class module because downstream concentration replacement is a core contract.
- The reference supports synthetic examples and outputs; only synthetic data should be migrated. Do not imply real SOPs or proprietary LIMS behavior.
- The target DSL is new. Reference YAML config files are useful examples, not the final schema.
- Readiness gates are generic booleans in the reference. The target should connect readiness directly to validation artifacts and exception state.
- Numeric formatting is part of artifact determinism. JANUS/protocol/manifest writers should retain stable precision and column order.
- Standard curve behavior depends on configured standards. The target should make the A1-H1 default explicit and test missing standard wells.
- No molarity support should be proposed or scaffolded. Any molar fields should remain rejected.
- The reference repository is read-only. All implementation and tests belong in `/Users/joseph/labflow`.

## First 5 Implementation Commits

1. **Bootstrap monorepo skeleton**
   - Create `packages/`, `apps/`, `infra/`, `docs/`, and `scripts/` directories.
   - Add package-level `pyproject.toml` files for `labflow-core`, `labflow-rag`, `labflow-agent`, and `apps/api`.
   - Add TypeScript package skeleton for `apps/vscode-extension`.
   - Add root developer commands or documentation for local tests/lints.
   - Evidence: package imports or placeholder tests run locally.

2. **Port deterministic domain and LIMS primitives**
   - Add units, wells, containers, samples, batches, statuses, exceptions, audit event models, registry, ancestry, and manifest validators to `labflow-core`.
   - Port and update domain/LIMS tests.
   - Evidence: `labflow-core` tests for wells, standards layout, container volume, duplicates, registry, sample identity, and exceptions pass.

3. **Port quantification primitives**
   - Add Varioskan TSV parser, standard curve fitting, quantification processing, and quant output models.
   - Keep standards plate once per batch and sample plate blank behavior explicit.
   - Port quantification tests and synthetic fixtures.
   - Evidence: tests for standard curve, blank correction, dilution factor, stock concentration, missing blank, missing standard, and out-of-range readings pass.

4. **Port normalization, split, RNA re-quant, JANUS, and readiness**
   - Add target modes, normalization planner, split workflow, RNA re-quant module, protocol IR, JANUS export, and readiness/throughput modules.
   - Preserve invalid-sample transfer exclusion and source-volume formula.
   - Port normalization, RNA, robot export, and throughput tests.
   - Evidence: tests for standard/in-place/split planning, insufficient source volume, destination overflow, re-quant downstream concentration, JANUS gating, and throughput comparison pass.

5. **Add LabFlow workflow DSL foundation**
   - Build YAML models, parser, validator, and JSON schema from target specs.
   - Map DSL validation errors onto core exception/readiness contracts.
   - Add valid and invalid workflow examples.
   - Evidence: DSL tests catch missing blank, missing concentration, split-required scenario, invalid well, duplicate destinations, and invalid destination state.

## Stage 1 Starting Contract

Stage 1 should start from this migration map and create only the repo bootstrap/skeleton requested by `prompts/01_bootstrap_repo.md`. It should not begin porting deterministic domain behavior until Stage 2.
