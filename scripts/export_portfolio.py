#!/usr/bin/env python3
"""Export a reviewer-friendly LabFlow portfolio packet."""

from __future__ import annotations

from pathlib import Path
import shutil


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = REPO_ROOT / "artifacts" / "portfolio_export"
EXPORT_FILES = (
    ("docs/portfolio_brief.md", "portfolio_brief.md"),
    ("docs/role_alignment_starlims.md", "role_alignment_starlims.md"),
    ("docs/case_study.md", "case_study.md"),
    ("docs/eval_summary.md", "eval_summary.md"),
    ("docs/corpus_lifecycle_reliability.md", "corpus_lifecycle_reliability.md"),
    ("docs/pinecone_vector_backend.md", "pinecone_vector_backend.md"),
    ("docs/retrieval_backend_comparison.md", "retrieval_backend_comparison.md"),
    ("docs/production_gap_analysis.md", "production_gap_analysis.md"),
    ("docs/demo_script_starlims_role.md", "demo_script_starlims_role.md"),
    ("examples/expected/audit_report.md", "expected_audit_report.md"),
    ("examples/expected/eval_report.json", "expected_eval_report.json"),
    ("examples/expected/lab_to_analysis_lineage_report.md", "expected_lab_to_analysis_lineage_report.md"),
)


def main() -> int:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    copied = []
    for source, destination in EXPORT_FILES:
        source_path = REPO_ROOT / source
        if not source_path.exists():
            continue
        target = EXPORT_DIR / destination
        shutil.copyfile(source_path, target)
        copied.append(destination)
    manifest = EXPORT_DIR / "README.md"
    manifest.write_text(
        "# LabFlow Portfolio Export\n\n"
        "This folder contains a reviewer-friendly export of public, synthetic "
        "LabFlow AI Studio materials. It excludes secrets, local eval artifacts, "
        "and live-provider credentials.\n\n"
        + "\n".join(f"- `{item}`" for item in copied)
        + "\n",
    )
    print(f"Wrote portfolio export: {EXPORT_DIR}")
    print(f"files={len(copied) + 1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
