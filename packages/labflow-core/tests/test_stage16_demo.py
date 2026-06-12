from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_stage16_demo_script_generates_expected_artifacts(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = ":".join(
        [
            str(REPO_ROOT / "packages/labflow-core/src"),
            str(REPO_ROOT / "packages/labflow-rag/src"),
        ]
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/run_demo.py"),
            "--output-dir",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "fixed_janus=ok" in completed.stdout
    assert "qc_lineage=ok" in completed.stdout
    validation_report = json.loads((tmp_path / "validation_report.json").read_text())
    assert all(validation_report["demo_cases"].values())
    assert validation_report["janus"]["invalid_status"] == "blocked"
    assert validation_report["janus"]["fixed_status"] == "ok"
    assert validation_report["qc"]["validation_status"] == "invalid"
    assert validation_report["qc"]["lineage_status"] == "ok"
    assert (tmp_path / "janus_rna_preview.csv").read_text().splitlines() == [
        "well,diluent_volume_ul,sample_volume_ul",
        "A1,80.00,20.00",
        "A2,49.00,1.00",
        "A3,32.00,0.00",
        "A4,90.00,10.00",
    ]
    qc_summary = json.loads((tmp_path / "qc_summary_report.json").read_text())
    assert qc_summary["pipeline_scope"] == "summary_metrics_only"
    assert qc_summary["summary"]["manual_review_count"] >= 5
    assert "RNA_DEMO_FAILED_VALID_UPSTREAM_001" in (
        tmp_path / "lab_to_analysis_lineage_report.md"
    ).read_text()
    qc_agent_response = json.loads((tmp_path / "qc_failure_agent_response.json").read_text())
    assert qc_agent_response["task"] == "explain_qc_failure"
    assert "does not infer a lab root cause" in qc_agent_response["answer"]
    eval_report = json.loads((tmp_path / "eval_report.json").read_text())
    assert eval_report["retrieval_only"] is True
    assert eval_report["metrics"]["failed_count"] == 0
