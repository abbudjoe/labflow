# Five-Minute Portfolio Demo Script

This is the recommended hiring-team demo for LabFlow AI Studio. The VS Code path
is the primary story; the CLI path is the fallback when the extension or local
API is not running.

## Demo Goal

Show how an AI-assisted LIMS workflow studio can help a developer understand
why a synthetic NGS batch is not robot-ready without letting the model invent
lab facts or bypass deterministic validation.

The optional closing segment shows a downstream QC provenance handoff. It links
synthetic QC summary rows back to LabFlow lineage, then explains one failed QC
sample without inferring a lab root cause.

## Setup

From the repo root:

```sh
make portfolio-check
```

Optional local API:

```sh
PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src:apps/api/src \
uv run --python python3.12 --with fastapi --with pydantic --with pyyaml --with httpx \
  uvicorn labflow_api.main:app --reload
```

## VS Code Demo Path

1. Open the repo in VS Code.
2. Open:

   ```text
   examples/workflows/invalid_rna_norm_requant.workflow.yaml
   ```

3. Show deterministic diagnostics for missing blank, missing concentration, and
   invalid readiness.
4. Run the extension command for workflow validation.
5. Run the diagnostic explanation command and ask:

   ```text
   Why is this batch not robot-ready?
   ```

6. Point out the answer shape:
   - cites LabFlow doctrine/SOP/schema sources;
   - includes deterministic `validate_batch` output;
   - does not invent a concentration or sample location;
   - says JANUS-style output remains blocked for invalid batches.
7. Run the dry-run patch proposal command.
8. Show that proposed changes are previewed rather than silently applied.
9. Explain the commit boundary:
   - dry-run is allowed;
   - commit requires explicit approval;
   - invalid validation blocks robot-facing artifacts.
10. Open:

    ```text
    examples/workflows/fixed_rna_norm_requant.workflow.yaml
    ```

11. Run validation again and show the JANUS-style dry-run preview path:

    ```text
    examples/expected/janus_rna_preview.csv
    ```

12. Show audit evidence:

    ```text
    examples/expected/audit_report.md
    ```

13. Show the downstream QC provenance artifacts:

    ```text
    examples/expected/qc_summary_report.json
    examples/expected/lab_to_analysis_lineage_report.md
    examples/expected/qc_failure_agent_response.json
    ```

    Point out that failed QC metrics require review, unmatched sample IDs are
    flagged, and the explanation cites QC/lineage policy without assigning a
    lab root cause.

14. Close with:

    ```text
    docs/eval_summary.md
    ```

    Explain that the eval ladder checks retrieval, grounding, tool-call
    correctness, provider failures, safety violations, and repair planning.

## CLI Fallback

Run the synthetic demo without modifying checked-in expected artifacts:

```sh
python3 scripts/run_demo.py --output-dir /tmp/labflow-portfolio-demo
```

Expected summary:

```text
invalid_errors=<nonzero> fixed_janus=ok qc_lineage=ok eval_passed=<passed>/<cases>
```

Run the interactive RAG demo:

```sh
python3 scripts/rag_demo.py
```

Ask:

```text
Why is this batch not robot-ready?
```

Run curated eval summary generation:

```sh
make eval-summary
```

Run the corpus lifecycle drift check:

```sh
make corpus-drift-eval
```

Open:

```text
docs/corpus_lifecycle_reliability.md
```

Explain that eval reports are fingerprinted to the corpus and the drift suite
checks renamed, removed, stale, and conflicting source scenarios.

## Optional Live Model Evidence

Live inference is not required for the default portfolio demo. If an
OpenRouter key is present, use a bounded smoke run only:

```sh
set -a
source .env
set +a

PYTHONPATH=packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src:apps/api/src \
uv run --python /Users/joseph/.local/bin/python3.12 \
  --with pytest --with pydantic --with pyyaml --with fastapi --with httpx \
  python scripts/run_inference_eval_ladder.py \
  --suite semantic_generalization \
  --live-openrouter \
  --confirm-live-openrouter \
  --verbose \
  --openrouter-timeout-seconds 20
```

Do not require this path for reviewers.

## Talk Track

The key design point is deterministic-before-generative. The model can explain,
retrieve, propose, and call controlled tools, but validation and artifact gates
stay in deterministic code.

The project is intentionally synthetic and local-first. It is not a clinical
system, production LIMS, robot controller, or proprietary platform clone.
