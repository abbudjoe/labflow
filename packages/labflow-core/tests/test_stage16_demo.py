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
    validation_report = json.loads((tmp_path / "validation_report.json").read_text())
    assert all(validation_report["demo_cases"].values())
    assert validation_report["janus"]["invalid_status"] == "blocked"
    assert validation_report["janus"]["fixed_status"] == "ok"
    assert (tmp_path / "janus_rna_preview.csv").read_text().splitlines() == [
        "well,diluent_volume_ul,sample_volume_ul",
        "A1,80.00,20.00",
        "A2,49.00,1.00",
        "A3,32.00,0.00",
        "A4,90.00,10.00",
    ]
    eval_report = json.loads((tmp_path / "eval_report.json").read_text())
    assert eval_report["retrieval_only"] is True
    assert eval_report["metrics"]["failed_count"] == 0
