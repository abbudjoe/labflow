#!/usr/bin/env python3
"""Run the synthetic LabFlow v0.1 demo and write expected artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import sys
from typing import Any


def _bootstrap_with_uv() -> None:
    if os.environ.get("LABFLOW_DEMO_UV_BOOTSTRAPPED") == "1":
        return
    os.environ["LABFLOW_DEMO_UV_BOOTSTRAPPED"] = "1"
    os.execvp(
        "uv",
        [
            "uv",
            "run",
            "--python",
            sys.executable,
            "--with",
            "pyyaml",
            "--with",
            "pydantic",
            "python",
            *sys.argv,
        ],
    )


try:
    import yaml
except ModuleNotFoundError:
    _bootstrap_with_uv()
    raise

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = REPO_ROOT / "packages" / "labflow-core" / "src"
RAG_SRC = REPO_ROOT / "packages" / "labflow-rag" / "src"
for src in (CORE_SRC, RAG_SRC):
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

try:
    from labflow_core.dsl.parser import parse_workflow_file  # noqa: E402
    from labflow_core.dsl.validator import validate_workflow_file  # noqa: E402
    from labflow_core.tools import (  # noqa: E402
        generate_janus_csv,
        generate_normalization_plan,
        parse_varioskan_tsv,
        validate_batch,
    )
    from labflow_rag.evals import EvalRunConfig, run_eval  # noqa: E402
except ModuleNotFoundError:
    _bootstrap_with_uv()
    raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="examples/expected",
        help="Directory for validation_report.json, janus_rna_preview.csv, and eval_report.json.",
    )
    args = parser.parse_args()

    output_dir = _resolve_repo_path(args.output_dir)
    generated_dir = output_dir / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_dir.mkdir(parents=True, exist_ok=True)

    invalid_workflow = REPO_ROOT / "examples/workflows/invalid_rna_norm_requant.workflow.yaml"
    fixed_workflow = REPO_ROOT / "examples/workflows/fixed_rna_norm_requant.workflow.yaml"

    invalid_config = _write_normalization_inputs(invalid_workflow, generated_dir)
    fixed_config = _write_normalization_inputs(fixed_workflow, generated_dir)

    invalid_validation = _workflow_report(invalid_workflow)
    fixed_validation = _workflow_report(fixed_workflow)
    invalid_batch = validate_batch(workflow_yaml=invalid_workflow.read_text())
    fixed_batch = validate_batch(workflow_yaml=fixed_workflow.read_text())
    invalid_janus = generate_janus_csv(str(invalid_config), dry_run=True)
    fixed_janus = generate_janus_csv(str(fixed_config), dry_run=True)
    fixed_plan = generate_normalization_plan(str(fixed_config))
    parsed_tsvs = _parse_demo_tsvs()
    eval_report = run_eval(
        EvalRunConfig(
            cases_path=REPO_ROOT / "evals/golden_questions.yaml",
            corpus_dir=REPO_ROOT / "knowledge",
            eval_run_id="demo_eval_stage16",
            retrieval_only=True,
        )
    ).to_json_dict()

    _write_janus_preview(output_dir / "janus_rna_preview.csv", fixed_janus)
    _write_json(output_dir / "eval_report.json", eval_report)
    _write_exception_report(output_dir / "exception_report.csv", invalid_validation)
    _write_audit_log(
        output_dir / "audit_log.jsonl",
        [
            invalid_batch,
            fixed_batch,
            invalid_janus,
            fixed_janus,
            fixed_plan,
            *parsed_tsvs.values(),
        ],
    )

    validation_report = {
        "demo_id": "stage16_rna_norm_requant",
        "synthetic": True,
        "workflows": {
            "invalid": invalid_validation,
            "fixed": fixed_validation,
        },
        "demo_cases": {
            "missing_blank": _has_code(invalid_validation, "MISSING_PLATE_BLANK"),
            "missing_concentration": _has_code(invalid_validation, "MISSING_CONCENTRATION"),
            "high_concentration_split_required": _artifact_has_status(
                fixed_plan,
                "SPLIT_CREATED",
            ),
            "in_place_normalization_selected": _artifact_has_status(
                fixed_plan,
                "IN_PLACE_NORMALIZATION_SELECTED",
            ),
            "janus_generation_blocked_until_errors_resolved": invalid_janus["status"] == "blocked",
            "fixed_workflow_generates_janus_preview": fixed_janus["status"] == "ok",
        },
        "janus": {
            "invalid_status": invalid_janus["status"],
            "invalid_error_codes": [error["code"] for error in invalid_janus["errors"]],
            "fixed_status": fixed_janus["status"],
            "preview_path": str(output_dir / "janus_rna_preview.csv"),
        },
        "varioskan": {
            name: {
                "status": result["status"],
                "reading_count": len(result["artifacts"][0]["data"]) if result["artifacts"] else 0,
            }
            for name, result in parsed_tsvs.items()
        },
        "eval": {
            "eval_run_id": eval_report["eval_run_id"],
            "metrics": eval_report["metrics"],
            "report_path": str(output_dir / "eval_report.json"),
        },
    }
    _write_json(output_dir / "validation_report.json", validation_report)

    print(f"Wrote demo artifacts to {output_dir}")
    print(
        "invalid_errors={invalid_errors} fixed_janus={fixed_janus} eval_passed={passed}/{cases}".format(
            invalid_errors=len(invalid_validation["diagnostics"]),
            fixed_janus=fixed_janus["status"],
            passed=eval_report["metrics"]["passed_count"],
            cases=eval_report["metrics"]["case_count"],
        )
    )
    return 0


def _resolve_repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _workflow_report(path: Path) -> dict[str, Any]:
    result = validate_workflow_file(path)
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "valid": result.valid,
        "diagnostics": [
            diagnostic.model_dump(mode="json") for diagnostic in result.diagnostics
        ],
    }


def _write_normalization_inputs(workflow_path: Path, output_dir: Path) -> Path:
    parsed = parse_workflow_file(workflow_path)
    if parsed.workflow is None:
        msg = f"Cannot derive normalization inputs from invalid schema: {workflow_path}"
        raise RuntimeError(msg)
    workflow = parsed.workflow
    stem = workflow_path.name.replace(".workflow.yaml", "")
    sample_csv = output_dir / f"{stem}.samples.csv"
    config_path = output_dir / f"{stem}.normalization.yaml"
    fieldnames = [
        "sample_id",
        "source_container_id",
        "source_well",
        "stock_concentration_ng_per_ul",
        "available_volume_ul",
        "destination_container_id",
        "destination_well",
    ]
    with sample_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for sample in workflow.samples:
            writer.writerow(
                {
                    "sample_id": sample.sample_id,
                    "source_container_id": sample.source_container_id,
                    "source_well": sample.source_well,
                    "stock_concentration_ng_per_ul": sample.stock_concentration_ng_per_ul or "",
                    "available_volume_ul": sample.available_volume_ul or "",
                    "destination_container_id": sample.destination_container_id or "",
                    "destination_well": sample.destination_well or "",
                }
            )
    containers = _containers_for_workflow(workflow_path)
    assert workflow.normalization is not None
    config = {
        "batch_id": workflow.batch.batch_id,
        "workflow_type": "RNA_NORMALIZATION_REQUANT",
        "analyte_type": "total_RNA",
        "input_csv": sample_csv.name,
        "target": {
            "target_concentration_ng_per_ul": workflow.normalization.target_concentration_ng_per_ul,
            "target_final_volume_ul": workflow.normalization.target_final_volume_ul,
        },
        "containers": containers,
    }
    config_path.write_text(yaml.safe_dump(config, sort_keys=True))
    return config_path


def _containers_for_workflow(workflow_path: Path) -> list[dict[str, str]]:
    parsed = parse_workflow_file(workflow_path)
    assert parsed.workflow is not None
    workflow = parsed.workflow
    containers: dict[str, str] = {}
    for sample in workflow.samples:
        containers[sample.source_container_id] = workflow.containers.source.registry_container_type
        if sample.destination_container_id is not None and workflow.containers.destination is not None:
            containers[sample.destination_container_id] = (
                workflow.containers.destination.registry_container_type
            )
    return [
        {"container_id": container_id, "container_type_id": container_type}
        for container_id, container_type in sorted(containers.items())
    ]


def _parse_demo_tsvs() -> dict[str, dict[str, Any]]:
    paths = {
        "rna_standards": REPO_ROOT / "examples/varioskan/rna_standards.tsv",
        "rna_plate_001": REPO_ROOT / "examples/varioskan/rna_plate_001.tsv",
        "dna_standards": REPO_ROOT / "examples/varioskan/dna_standards.tsv",
        "dna_plate_001": REPO_ROOT / "examples/varioskan/dna_plate_001.tsv",
    }
    return {name: parse_varioskan_tsv(str(path)) for name, path in paths.items()}


def _write_janus_preview(path: Path, result: dict[str, Any]) -> None:
    worklist = next(
        artifact
        for artifact in result["artifacts"]
        if artifact["artifact_type"] == "janus_worklist_preview"
    )
    rows = worklist["data"]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["well", "diluent_volume_ul", "sample_volume_ul"],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_exception_report(path: Path, report: dict[str, Any]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["code", "severity", "path", "source", "message", "suggested_action"],
        )
        writer.writeheader()
        for diagnostic in report["diagnostics"]:
            writer.writerow(
                {
                    "code": diagnostic["code"],
                    "severity": diagnostic["severity"],
                    "path": diagnostic["path"],
                    "source": diagnostic["source"],
                    "message": diagnostic["message"],
                    "suggested_action": diagnostic["suggested_action"],
                }
            )


def _write_audit_log(path: Path, tool_results: list[dict[str, Any]]) -> None:
    with path.open("w") as handle:
        for result in tool_results:
            event = result.get("audit_event")
            if event is not None:
                handle.write(json.dumps(event, sort_keys=True) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _has_code(report: dict[str, Any], code: str) -> bool:
    return any(diagnostic["code"] == code for diagnostic in report["diagnostics"])


def _artifact_has_status(result: dict[str, Any], status: str) -> bool:
    for artifact in result["artifacts"]:
        if artifact["artifact_type"] != "normalization_plan":
            continue
        return any(row["status"] == status for row in artifact["data"])
    return False


if __name__ == "__main__":
    raise SystemExit(main())
