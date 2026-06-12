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
AGENT_SRC = REPO_ROOT / "packages" / "labflow-agent" / "src"
for src in (CORE_SRC, RAG_SRC, AGENT_SRC):
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

try:
    from labflow_agent import LabFlowAgentRuntime  # noqa: E402
    from labflow_core.dsl.parser import parse_workflow_file  # noqa: E402
    from labflow_core.dsl.validator import validate_workflow_file  # noqa: E402
    from labflow_core.tools import (  # noqa: E402
        generate_janus_csv,
        generate_lab_to_analysis_lineage,
        generate_normalization_plan,
        ingest_ngs_qc_results,
        parse_varioskan_tsv,
        validate_qc_provenance,
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
    qc_csv = REPO_ROOT / "examples/qc/synthetic_ngs_qc_results.csv"
    lineage_csv = REPO_ROOT / "examples/qc/synthetic_lab_lineage_manifest.csv"
    qc_ingest = ingest_ngs_qc_results(str(qc_csv))
    qc_validation = validate_qc_provenance(str(qc_csv), str(lineage_csv))
    qc_lineage = generate_lab_to_analysis_lineage(str(qc_csv), str(lineage_csv), dry_run=True)
    qc_agent_response = LabFlowAgentRuntime().ask(
        "Why did RNA_DEMO_FAILED_VALID_UPSTREAM_001 fail downstream QC?",
        qc_csv=str(qc_csv),
        lineage_csv=str(lineage_csv),
        sample_id="RNA_DEMO_FAILED_VALID_UPSTREAM_001",
    ).to_json_dict()
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
    _write_qc_demo_artifacts(output_dir, qc_validation, qc_lineage, qc_agent_response)
    audited_results = [
        invalid_batch,
        fixed_batch,
        invalid_janus,
        fixed_janus,
        fixed_plan,
        qc_ingest,
        qc_validation,
        qc_lineage,
        *parsed_tsvs.values(),
    ]
    _write_audit_log(
        output_dir / "audit_log.jsonl",
        audited_results,
    )
    _write_audit_report(output_dir / "audit_report.md", audited_results)

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
            "qc_results_ingested": qc_ingest["status"] == "ok",
            "qc_provenance_flags_manual_review": qc_validation["status"] == "invalid",
            "lineage_report_generated": qc_lineage["status"] == "ok",
            "qc_failure_explanation_no_root_cause": (
                "does not infer causal lab failure"
                in qc_agent_response["answer"].casefold()
                or "does not infer a lab root cause" in qc_agent_response["answer"].casefold()
            ),
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
        "qc": {
            "ingest_status": qc_ingest["status"],
            "validation_status": qc_validation["status"],
            "lineage_status": qc_lineage["status"],
            "summary_path": str(output_dir / "qc_summary_report.json"),
            "lineage_report_path": str(output_dir / "lab_to_analysis_lineage_report.md"),
            "agent_response_path": str(output_dir / "qc_failure_agent_response.json"),
        },
    }
    _write_json(output_dir / "validation_report.json", validation_report)

    print(f"Wrote demo artifacts to {output_dir}")
    print(
        "invalid_errors={invalid_errors} fixed_janus={fixed_janus} qc_lineage={qc_lineage} eval_passed={passed}/{cases}".format(
            invalid_errors=len(invalid_validation["diagnostics"]),
            fixed_janus=fixed_janus["status"],
            qc_lineage=qc_lineage["status"],
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
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
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
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_exception_report(path: Path, report: dict[str, Any]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["code", "severity", "path", "source", "message", "suggested_action"],
            lineterminator="\n",
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


def _write_audit_report(path: Path, tool_results: list[dict[str, Any]]) -> None:
    lines = [
        "# Demo Audit Report",
        "",
        "This report summarizes the synthetic audit evidence generated by the LabFlow demo.",
        "",
        "## Scope",
        "",
        "- Demo workflow: RNA normalization, re-quantification, and downstream QC provenance.",
        "- Data type: synthetic only.",
        "- Commit actions: none.",
        "- Robot execution: none.",
        "- JANUS-style and lineage files: dry-run previews only.",
        "",
        "## Audit Chain",
        "",
        "| Step | Tool | Mode | Workflow | Result | Exception Codes |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for index, result in enumerate(tool_results, start=1):
        event = result.get("audit_event") or {}
        errors = result.get("errors") or []
        warnings = result.get("warnings") or []
        codes = [
            str(item.get("code"))
            for item in [*errors, *warnings]
            if isinstance(item, dict) and item.get("code")
        ]
        lines.append(
            "| {index} | `{tool}` | `{mode}` | `{workflow}` | `{status}` | {codes} |".format(
                index=index,
                tool=result.get("tool_name", event.get("tool_name", "unknown")),
                mode=event.get("mode", "read_only"),
                workflow=event.get("workflow_id") or "synthetic inputs",
                status=result.get("status", event.get("result_status", "unknown")),
                codes=", ".join(f"`{code}`" for code in codes) or "none",
            )
        )
    lines.extend(
        [
            "",
            "## Guardrail Evidence",
            "",
            "- Invalid workflows are validated before artifact generation.",
            "- Missing concentrations remain blocking facts; the system does not invent them.",
            "- The invalid JANUS dry-run is blocked with `JANUS_BLOCKED_FOR_INVALID_BATCH`.",
            "- The fixed JANUS output is still a dry-run preview, not a robot command.",
            "- Downstream QC provenance is linked by sample ID and batch IDs.",
            "- Failed QC metrics, unmatched sample IDs, missing QC rows, and provenance gaps require review.",
            "- QC results do not retroactively validate invalid upstream workflows or prove lab root cause.",
            "- No approval token appears in this demo because no commit action is performed.",
            "",
            "## Reviewer Notes",
            "",
            "The ignored raw file `examples/expected/audit_log.jsonl` can be regenerated locally by running:",
            "",
            "```sh",
            "python3 scripts/run_demo.py",
            "```",
            "",
            "For the public portfolio path, this markdown report is the canonical audit evidence.",
        ]
    )
    path.write_text("\n".join(lines) + "\n")


def _write_qc_demo_artifacts(
    output_dir: Path,
    qc_validation: dict[str, Any],
    qc_lineage: dict[str, Any],
    qc_agent_response: dict[str, Any],
) -> None:
    summary = _artifact_data(qc_validation, "downstream_qc_summary")
    if isinstance(summary, dict):
        _write_json(output_dir / "qc_summary_report.json", summary)
    markdown = _artifact_data(qc_lineage, "lab_to_analysis_lineage_markdown")
    if isinstance(markdown, str):
        (output_dir / "lab_to_analysis_lineage_report.md").write_text(markdown)
    _write_json(output_dir / "qc_failure_agent_response.json", qc_agent_response)


def _artifact_data(result: dict[str, Any], artifact_type: str) -> Any:
    for artifact in result.get("artifacts", []):
        if isinstance(artifact, dict) and artifact.get("artifact_type") == artifact_type:
            return artifact.get("data")
    return None


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
