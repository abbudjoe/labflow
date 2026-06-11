"""JSON report writing for LabFlow RAG evals."""

from __future__ import annotations

import json
from pathlib import Path

from labflow_rag.evals.runner import EvalRunReport


def write_eval_report(
    report: EvalRunReport,
    output_dir: str | Path = "artifacts/eval_reports",
) -> Path:
    """Write an eval report to `<output_dir>/<eval_run_id>.json`."""

    destination_dir = Path(output_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{report.eval_run_id}.json"
    destination.write_text(json.dumps(report.to_json_dict(), indent=2, sort_keys=True) + "\n")
    return destination
