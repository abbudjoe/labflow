# LabFlow Demo Walkthrough

This walkthrough uses synthetic data only. It does not connect to AWS, clinical systems, production LIMS data, or robot hardware.

For the broader portfolio narrative, see `docs/case_study.md`. For system boundaries and diagrams, see `docs/architecture.md`.

## Run The Demo

From the repository root:

```text
python3 scripts/run_demo.py
```

The script writes deterministic demo artifacts to:

```text
examples/expected/
```

To run without changing the checked-in expected artifacts:

```text
python3 scripts/run_demo.py --output-dir /tmp/labflow-demo
```

The script bootstraps missing Python package dependencies through `uv` when needed.

## What The Demo Exercises

The invalid workflow is:

```text
examples/workflows/invalid_rna_norm_requant.workflow.yaml
```

It intentionally includes:

- missing sample-plate blank;
- missing stock concentration;
- invalid standards layout;
- JANUS output requested for an invalid batch.

The fixed workflow is:

```text
examples/workflows/fixed_rna_norm_requant.workflow.yaml
```

It includes:

- 3 containers per batch;
- standards in A1-H1;
- a standard new-container RNA normalization sample;
- a high-concentration sample that requires split workflow;
- an in-place normalization sample with no destination container;
- a JANUS-style dry-run preview.

## Expected Artifacts

The main generated files are:

```text
examples/expected/validation_report.json
examples/expected/janus_rna_preview.csv
examples/expected/eval_report.json
examples/expected/exception_report.csv
examples/expected/audit_report.md
```

`validation_report.json` is the fastest human review entry point. Its `demo_cases` object should show `true` for:

- `missing_blank`;
- `missing_concentration`;
- `high_concentration_split_required`;
- `in_place_normalization_selected`;
- `janus_generation_blocked_until_errors_resolved`;
- `fixed_workflow_generates_janus_preview`.

`janus_rna_preview.csv` is generated only from the fixed workflow path. It is a dry-run preview, not a robot-ready production artifact.

`eval_report.json` is a retrieval-focused demo eval report over `evals/golden_questions.yaml` and `knowledge/`. It verifies that required sources are retrievable for the demo corpus without introducing live model inference.

## Optional VS Code Review

Open either workflow file in the VS Code extension workspace:

```text
examples/workflows/invalid_rna_norm_requant.workflow.yaml
examples/workflows/fixed_rna_norm_requant.workflow.yaml
```

The extension skeleton is designed to surface LabFlow diagnostics through the local API, then offer commands for explanation, JANUS dry-run, evals, and audit events. The command-line demo remains the most repeatable Stage 17 evidence path.

## Interpreting The JANUS Preview

The fixed RNA demo preview should include four rows:

- a standard transfer row;
- a split workflow row using 1 uL sample and 49 uL diluent;
- an in-place normalization row using 0 uL sample transfer and source-well diluent addition;
- a second standard transfer row.

The invalid workflow is separately checked through deterministic validation and JANUS generation is blocked until errors are resolved.

## Why This Is Safe For A Portfolio Demo

- The data is synthetic.
- Deterministic validators own lab truth.
- The demo uses dry-run artifact generation.
- Invalid batches do not produce JANUS previews.
- Audit events are written for tool calls.
- RAG evals run locally over checked-in knowledge files.
