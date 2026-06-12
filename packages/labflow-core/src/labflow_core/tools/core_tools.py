"""Deterministic structured wrappers around labflow-core capabilities."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import time_ns
from typing import Any
from uuid import uuid4

import yaml

from labflow_core.domain.exceptions import ExceptionRecord
from labflow_core.domain.statuses import AnalyteType, ExceptionCode, ExceptionSeverity, WorkflowType
from labflow_core.dsl.diagnostics import WorkflowDiagnostic
from labflow_core.dsl.validator import validate_workflow_text
from labflow_core.lims.registry import ContainerRegistry
from labflow_core.norm.planner import (
    NormalizationConfig,
    NormalizationPlanResult,
    process_normalization_config,
)
from labflow_core.norm.requant import RnaRequantPolicy, RnaWorkflowResult, process_rna_workflow
from labflow_core.norm.split import SplitConfig
from labflow_core.norm.targets import NormalizationTarget
from labflow_core.qc import (
    build_qc_summary_report,
    evaluate_qc_results,
    lineage_report_markdown,
    parse_ngs_qc_csv,
    read_lineage_manifest,
    validate_qc_provenance_records,
)
from labflow_core.qc.models import QcProvenanceRecord, QcProvenanceReport
from labflow_core.qc.processor import thresholds_from_config
from labflow_core.quant.processors import (
    QuantificationConfig,
    QuantificationResult,
    SamplePlateConfig,
    process_quantification as process_quantification_core,
)
from labflow_core.quant.varioskan import VarioskanSchemaMapping, parse_varioskan_tsv as parse_tsv
from labflow_core.robots.janus import janus_audit_rows, janus_minimal_rows
from labflow_core.throughput.simulator import (
    ThroughputScenario,
    compare_default_batching,
    compare_scenarios,
)
from labflow_core.tools.schemas import (
    JsonDict,
    ToolArtifact,
    ToolAuditEvent,
    ToolError,
    ToolResult,
    ToolStatus,
)


def validate_workflow(workflow_yaml: str) -> JsonDict:
    payload = {"workflow_yaml": workflow_yaml}
    validation = validate_workflow_text(workflow_yaml)
    errors = [_diagnostic_to_error(diagnostic) for diagnostic in validation.diagnostics]
    artifacts: list[ToolArtifact] = []
    if validation.workflow is not None:
        artifacts.append(
            ToolArtifact(
                artifact_id=_artifact_id("workflow_summary", payload),
                artifact_type="workflow_summary",
                name="workflow_summary.json",
                data={
                    "workflow_type": validation.workflow.workflow.type.value,
                    "batch_id": validation.workflow.batch.batch_id,
                    "sample_count": len(validation.workflow.samples),
                },
            )
        )
    status = ToolStatus.VALID if not errors else ToolStatus.INVALID
    return _result(
        tool_name="validate_workflow",
        status=status,
        errors=errors,
        artifacts=artifacts,
        payload=payload,
        workflow_id=validation.workflow.batch.batch_id if validation.workflow else None,
    )


def validate_batch(batch_id: str | None = None, workflow_yaml: str | None = None) -> JsonDict:
    payload = {"batch_id": batch_id, "workflow_yaml": workflow_yaml}
    if workflow_yaml is None:
        return _result(
            tool_name="validate_batch",
            status=ToolStatus.ERROR,
            errors=[
                ToolError(
                    code="MISSING_WORKFLOW_YAML",
                    message="workflow_yaml is required to validate a batch.",
                    path="workflow_yaml",
                    suggested_action="Provide a LabFlow workflow YAML document.",
                )
            ],
            payload=payload,
            workflow_id=batch_id,
        )
    validation = validate_workflow_text(workflow_yaml)
    errors = [_diagnostic_to_error(diagnostic) for diagnostic in validation.diagnostics]
    workflow_batch_id = validation.workflow.batch.batch_id if validation.workflow else None
    if batch_id is not None and workflow_batch_id is not None and batch_id != workflow_batch_id:
        errors.append(
            ToolError(
                code="BATCH_ID_MISMATCH",
                message=(
                    f"Requested batch_id {batch_id} does not match workflow batch "
                    f"{workflow_batch_id}."
                ),
                path="batch.batch_id",
                suggested_action="Use the workflow batch_id or validate the intended workflow file.",
            )
        )
    status = ToolStatus.VALID if not errors else ToolStatus.INVALID
    artifacts = [
        ToolArtifact(
            artifact_id=_artifact_id("batch_validation", payload),
            artifact_type="batch_validation",
            name="batch_validation.json",
            data={"batch_id": workflow_batch_id or batch_id or "", "status": status.value},
        )
    ]
    return _result(
        tool_name="validate_batch",
        status=status,
        errors=errors,
        artifacts=artifacts,
        payload=payload,
        workflow_id=workflow_batch_id or batch_id,
    )


def parse_varioskan_tsv(
    file_path: str,
    schema_mapping: dict[str, Any] | None = None,
) -> JsonDict:
    payload = {"file_path": file_path, "schema_mapping": schema_mapping or {}}
    tool_name = "parse_varioskan_tsv"
    try:
        mapping = VarioskanSchemaMapping.from_config(schema_mapping)
        readings = parse_tsv(Path(file_path), mapping)
    except Exception as exc:  # noqa: BLE001 - tools must return structured errors.
        return _exception_result(tool_name, payload, exc)
    artifacts = [
        ToolArtifact(
            artifact_id=_artifact_id("varioskan_readings", payload),
            artifact_type="varioskan_readings",
            name="varioskan_readings.json",
            data=[
                {
                    "plate_id": reading.plate_id,
                    "well": str(reading.well),
                    "sample_id": reading.sample_id or "",
                    "reading": reading.reading,
                }
                for reading in readings
            ],
        )
    ]
    return _result(
        tool_name=tool_name,
        status=ToolStatus.OK,
        artifacts=artifacts,
        payload=payload,
    )


def process_quantification(config_path: str) -> JsonDict:
    payload = {"config_path": config_path}
    tool_name = "process_quantification"
    try:
        config = _load_quantification_config(Path(config_path))
        result = process_quantification_core(config)
    except Exception as exc:  # noqa: BLE001 - tools must return structured errors.
        return _exception_result(tool_name, payload, exc)
    errors, warnings = _errors_and_warnings(result.exceptions)
    status = ToolStatus.VALID if not errors else ToolStatus.INVALID
    return _result(
        tool_name=tool_name,
        status=status,
        errors=errors,
        warnings=warnings,
        artifacts=_quantification_artifacts(result, payload),
        payload=payload,
        workflow_id=config.batch_id,
    )


def generate_normalization_plan(config_path: str) -> JsonDict:
    payload = {"config_path": config_path}
    tool_name = "generate_normalization_plan"
    try:
        config = _load_normalization_config(Path(config_path))
        result = process_normalization_config(config)
    except Exception as exc:  # noqa: BLE001 - tools must return structured errors.
        return _exception_result(tool_name, payload, exc)
    errors, warnings = _errors_and_warnings(result.exceptions)
    status = ToolStatus.VALID if not errors else ToolStatus.INVALID
    return _result(
        tool_name=tool_name,
        status=status,
        errors=errors,
        warnings=warnings,
        artifacts=_normalization_artifacts(result, payload),
        payload=payload,
        workflow_id=config.batch_id,
    )


def process_rna_requant(config_path: str) -> JsonDict:
    payload = {"config_path": config_path}
    tool_name = "process_rna_requant"
    try:
        config_path_obj = Path(config_path)
        raw = _load_config_mapping(config_path_obj)
        config = _load_normalization_config(config_path_obj, raw.get("normalization_config", raw))
        requant_csv = _resolve_path(config_path_obj.parent, raw["requant_csv"])
        policy = RnaRequantPolicy.model_validate(raw.get("requant_policy", {}))
        result = process_rna_workflow(config, requant_csv, policy)
    except Exception as exc:  # noqa: BLE001 - tools must return structured errors.
        return _exception_result(tool_name, payload, exc)
    errors, warnings = _errors_and_warnings(result.normalization.exceptions + result.requant_exceptions)
    status = ToolStatus.VALID if not errors else ToolStatus.INVALID
    return _result(
        tool_name=tool_name,
        status=status,
        errors=errors,
        warnings=warnings,
        artifacts=_rna_artifacts(result, payload),
        payload=payload,
        workflow_id=config.batch_id,
    )


def generate_janus_csv(
    plan_id: str,
    dry_run: bool,
    approval_token: str | None = None,
    output_dir: str | None = None,
) -> JsonDict:
    payload = {
        "plan_id": plan_id,
        "dry_run": dry_run,
        "approval_token_present": approval_token is not None,
        "output_dir": output_dir,
    }
    tool_name = "generate_janus_csv"
    try:
        config = _load_normalization_config(Path(plan_id))
        result = process_normalization_config(config)
    except Exception as exc:  # noqa: BLE001 - tools must return structured errors.
        return _exception_result(tool_name, payload, exc)
    errors, warnings = _errors_and_warnings(result.exceptions)
    if errors:
        errors.append(
            ToolError(
                code="JANUS_BLOCKED_FOR_INVALID_BATCH",
                message="JANUS CSV generation is blocked because the batch is invalid.",
                path="plan_id",
                suggested_action="Resolve validation errors before generating robot artifacts.",
            )
        )
        return _result(
            tool_name=tool_name,
            status=ToolStatus.BLOCKED,
            errors=errors,
            warnings=warnings,
            artifacts=_normalization_artifacts(result, payload),
            payload=payload,
            mode="dry_run" if dry_run else "commit",
            workflow_id=config.batch_id,
            approval_token=approval_token,
        )
    if not dry_run:
        return _result(
            tool_name=tool_name,
            status=ToolStatus.BLOCKED,
            errors=[
                ToolError(
                    code="COMMIT_MODE_NOT_AVAILABLE",
                    message=(
                        "Commit-mode JANUS generation requires the durable dry-run and approval "
                        "guardrail store scheduled for a later stage."
                    ),
                    path="dry_run",
                    suggested_action="Run with dry_run=true to preview deterministic JANUS artifacts.",
                )
            ],
            warnings=warnings,
            payload=payload,
            mode="commit",
            workflow_id=config.batch_id,
            approval_token=approval_token,
        )
    artifacts = _janus_preview_artifacts(result, payload)
    return _result(
        tool_name=tool_name,
        status=ToolStatus.OK,
        warnings=warnings,
        artifacts=artifacts,
        payload=payload,
        mode="dry_run" if dry_run else "commit",
        workflow_id=config.batch_id,
        approval_token=approval_token,
    )


def ingest_ngs_qc_results(
    qc_csv: str,
    thresholds: dict[str, Any] | None = None,
) -> JsonDict:
    payload = {"qc_csv": qc_csv, "thresholds": thresholds or {}}
    tool_name = "ingest_ngs_qc_results"
    try:
        parsed_thresholds = thresholds_from_config(thresholds)
        rows = parse_ngs_qc_csv(Path(qc_csv))
        evaluations = evaluate_qc_results(rows, parsed_thresholds)
    except Exception as exc:  # noqa: BLE001 - tools must return structured errors.
        return _exception_result(tool_name, payload, exc)
    warnings = _qc_code_warnings(
        [
            code.value
            for evaluation in evaluations
            for code in evaluation.exception_codes
        ]
    )
    return _result(
        tool_name=tool_name,
        status=ToolStatus.OK,
        warnings=warnings,
        artifacts=[
            ToolArtifact(
                artifact_id=_artifact_id("ngs_qc_evaluations", payload),
                artifact_type="ngs_qc_evaluations",
                name="ngs_qc_evaluations.json",
                data=[evaluation.to_json_dict() for evaluation in evaluations],
            )
        ],
        payload=payload,
    )


def validate_qc_provenance(
    qc_csv: str,
    lineage_csv: str,
    thresholds: dict[str, Any] | None = None,
) -> JsonDict:
    payload = {"qc_csv": qc_csv, "lineage_csv": lineage_csv, "thresholds": thresholds or {}}
    tool_name = "validate_qc_provenance"
    try:
        report = _load_qc_provenance_report(qc_csv, lineage_csv, thresholds)
    except Exception as exc:  # noqa: BLE001 - tools must return structured errors.
        return _exception_result(tool_name, payload, exc)
    errors = _qc_report_errors(report)
    status = ToolStatus.VALID if not errors else ToolStatus.INVALID
    return _result(
        tool_name=tool_name,
        status=status,
        errors=errors,
        artifacts=_qc_report_artifacts(report, payload),
        payload=payload,
    )


def explain_qc_failure(
    qc_csv: str,
    sample_id: str,
    lineage_csv: str | None = None,
    thresholds: dict[str, Any] | None = None,
) -> JsonDict:
    payload = {
        "qc_csv": qc_csv,
        "sample_id": sample_id,
        "lineage_csv": lineage_csv,
        "thresholds": thresholds or {},
    }
    tool_name = "explain_qc_failure"
    try:
        if lineage_csv is None:
            parsed_thresholds = thresholds_from_config(thresholds)
            qc_rows = parse_ngs_qc_csv(Path(qc_csv))
            report = validate_qc_provenance_records(qc_rows, (), parsed_thresholds)
        else:
            report = _load_qc_provenance_report(qc_csv, lineage_csv, thresholds)
    except Exception as exc:  # noqa: BLE001 - tools must return structured errors.
        return _exception_result(tool_name, payload, exc)

    record = next((item for item in report.records if item.sample_id == sample_id), None)
    if record is None:
        return _result(
            tool_name=tool_name,
            status=ToolStatus.INVALID,
            errors=[
                ToolError(
                    code=ExceptionCode.MISSING_QC_RESULT.value,
                    message=f"No downstream QC result or lineage record was found for {sample_id}.",
                    path="sample_id",
                    suggested_action="Verify the sample ID and review the QC/lineage manifests.",
                )
            ],
            payload=payload,
        )
    return _result(
        tool_name=tool_name,
        status=ToolStatus.OK if not record.manual_review_required else ToolStatus.INVALID,
        errors=_qc_record_errors(record) if record.manual_review_required else [],
        artifacts=[
            ToolArtifact(
                artifact_id=_artifact_id("qc_failure_explanation", payload),
                artifact_type="qc_failure_explanation",
                name=f"{sample_id}.qc_explanation.json",
                data={
                    "sample_id": record.sample_id,
                    "read_count": record.qc_result.read_count if record.qc_result else None,
                    "q30_percent": record.qc_result.q30_percent if record.qc_result else None,
                    "thresholds": report.thresholds.model_dump(mode="json"),
                    "qc_status": record.qc_status.value,
                    "provenance_status": record.provenance_status.value,
                    "exception_codes": [code.value for code in record.exception_codes],
                    "safe_interpretation": record.safe_interpretation,
                    "root_cause_boundary": (
                        "LabFlow reports observed downstream QC metrics and lineage gaps only; "
                        "it does not infer a lab root cause or causal lab failure from QC alone."
                    ),
                },
            )
        ],
        payload=payload,
    )


def generate_lab_to_analysis_lineage(
    qc_csv: str,
    lineage_csv: str,
    dry_run: bool,
    thresholds: dict[str, Any] | None = None,
    approval_token: str | None = None,
    output_dir: str | None = None,
) -> JsonDict:
    payload = {
        "qc_csv": qc_csv,
        "lineage_csv": lineage_csv,
        "dry_run": dry_run,
        "thresholds": thresholds or {},
        "approval_token_present": approval_token is not None,
        "output_dir": output_dir,
    }
    tool_name = "generate_lab_to_analysis_lineage"
    try:
        report = _load_qc_provenance_report(qc_csv, lineage_csv, thresholds)
    except Exception as exc:  # noqa: BLE001 - tools must return structured errors.
        return _exception_result(tool_name, payload, exc)
    if not dry_run:
        return _result(
            tool_name=tool_name,
            status=ToolStatus.BLOCKED,
            errors=[
                ToolError(
                    code="COMMIT_MODE_NOT_AVAILABLE",
                    message=(
                        "Commit-mode lineage report generation requires durable artifact "
                        "approval storage outside this optional Stage 19 extension."
                    ),
                    path="dry_run",
                    suggested_action="Run with dry_run=true to preview the lineage report.",
                )
            ],
            payload=payload,
            mode="commit",
            approval_token=approval_token,
        )
    return _result(
        tool_name=tool_name,
        status=ToolStatus.OK,
        warnings=_qc_report_errors(report),
        artifacts=[
            *_qc_report_artifacts(report, payload),
            ToolArtifact(
                artifact_id=_artifact_id("lab_to_analysis_lineage_markdown", payload),
                artifact_type="lab_to_analysis_lineage_markdown",
                name="lab_to_analysis_lineage_report.md",
                content_type="text/markdown",
                data=lineage_report_markdown(report),
            ),
        ],
        payload=payload,
        mode="dry_run",
        approval_token=approval_token,
    )


def compare_throughput(config_path: str) -> JsonDict:
    payload = {"config_path": config_path}
    tool_name = "compare_throughput"
    try:
        raw = _load_config_mapping(Path(config_path))
        if "baseline" in raw and "optimized" in raw:
            comparison = compare_scenarios(
                ThroughputScenario.model_validate(raw["baseline"]),
                ThroughputScenario.model_validate(raw["optimized"]),
            )
        else:
            comparison = compare_default_batching(containers=int(raw.get("containers", 3)))
    except Exception as exc:  # noqa: BLE001 - tools must return structured errors.
        return _exception_result(tool_name, payload, exc)
    return _result(
        tool_name=tool_name,
        status=ToolStatus.OK,
        artifacts=[
            ToolArtifact(
                artifact_id=_artifact_id("throughput_comparison", payload),
                artifact_type="throughput_comparison",
                name="throughput_comparison.json",
                data=comparison.to_json_dict(),
            )
        ],
        payload=payload,
    )


def explain_exception_code(exception_code: str) -> JsonDict:
    payload = {"exception_code": exception_code}
    explanation = _EXCEPTION_EXPLANATIONS.get(exception_code)
    if explanation is None:
        return _result(
            tool_name="explain_exception_code",
            status=ToolStatus.ERROR,
            errors=[
                ToolError(
                    code="UNKNOWN_EXCEPTION_CODE",
                    message=f"No deterministic explanation is registered for {exception_code}.",
                    path="exception_code",
                    suggested_action="Use a known LabFlow exception or diagnostic code.",
                )
            ],
            payload=payload,
        )
    return _result(
        tool_name="explain_exception_code",
        status=ToolStatus.OK,
        artifacts=[
            ToolArtifact(
                artifact_id=_artifact_id("exception_explanation", payload),
                artifact_type="exception_explanation",
                name=f"{exception_code}.json",
                data=explanation,
            )
        ],
        payload=payload,
    )


def _load_quantification_config(path: Path) -> QuantificationConfig:
    raw = _load_config_mapping(path)
    base = path.parent
    return QuantificationConfig(
        batch_id=str(raw["batch_id"]),
        workflow_type=WorkflowType(str(raw.get("workflow_type", WorkflowType.DNA_QUANT.value))),
        assay=str(raw["assay"]),
        instrument=str(raw.get("instrument", "Varioskan")),
        standards_tsv=_resolve_path(base, raw["standards_tsv"]),
        sample_plates=tuple(
            SamplePlateConfig(
                plate_id=str(plate["plate_id"]),
                source_container_id=str(plate["source_container_id"]),
                tsv=_resolve_path(base, plate["tsv"]),
                blank_well=plate["blank_well"],
                dilution_factor=float(plate["dilution_factor"]),
            )
            for plate in raw["sample_plates"]
        ),
        standard_concentrations_ng_per_ul={
            str(well): float(concentration)
            for well, concentration in raw["standard_concentrations_ng_per_ul"].items()
        },
        schema_mapping=VarioskanSchemaMapping.from_config(raw.get("schema_mapping")),
    )


def _load_normalization_config(path: Path, raw: Mapping[str, Any] | None = None) -> NormalizationConfig:
    data = dict(raw or _load_config_mapping(path))
    base = path.parent
    return NormalizationConfig(
        batch_id=str(data["batch_id"]),
        workflow_type=WorkflowType(str(data["workflow_type"])),
        analyte_type=AnalyteType(str(data["analyte_type"])),
        input_csv=_resolve_path(base, data["input_csv"]),
        target=NormalizationTarget.from_config(dict(data["target"])),
        split_config=SplitConfig.model_validate(data.get("split_config", {})),
        registry=_registry_from_config(data),
    )


def _registry_from_config(raw: Mapping[str, Any]) -> ContainerRegistry:
    registry = ContainerRegistry.with_defaults()
    for item in raw.get("containers", []):
        if not isinstance(item, Mapping):
            continue
        registry.ensure_container(
            str(item["container_id"]),
            str(item.get("container_type_id", "matrix_96_1ml_screwtop")),
        )
    return registry


def _load_config_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text()
    if path.suffix == ".json":
        raw = json.loads(text)
    else:
        raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        msg = f"Config file must contain a mapping: {path}"
        raise ValueError(msg)
    return raw


def _resolve_path(base: Path, value: Any) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path
    return base / path


def _diagnostic_to_error(diagnostic: WorkflowDiagnostic) -> ToolError:
    return ToolError(
        code=diagnostic.code,
        message=diagnostic.message,
        path=diagnostic.path,
        suggested_action=diagnostic.suggested_action,
    )


def _exception_to_error(exception: ExceptionRecord) -> ToolError:
    return ToolError(
        code=exception.exception_code.value,
        message=exception.message,
        path=_exception_path(exception),
        suggested_action=exception.suggested_action,
    )


def _exception_path(exception: ExceptionRecord) -> str | None:
    if exception.sample_id:
        return f"samples.{exception.sample_id}"
    if exception.source_well:
        return f"source.{exception.source_well}"
    if exception.destination_well:
        return f"destination.{exception.destination_well}"
    return None


def _errors_and_warnings(
    exceptions: tuple[ExceptionRecord, ...],
) -> tuple[list[ToolError], list[ToolError]]:
    errors: list[ToolError] = []
    warnings: list[ToolError] = []
    for exception in exceptions:
        converted = _exception_to_error(exception)
        if exception.blocks_robot_transfer or exception.severity in {
            ExceptionSeverity.ERROR,
            ExceptionSeverity.BLOCKING,
        }:
            errors.append(converted)
        else:
            warnings.append(converted)
    return errors, warnings


def _quantification_artifacts(result: QuantificationResult, payload: JsonDict) -> list[ToolArtifact]:
    artifacts = [
        ToolArtifact(
            artifact_id=_artifact_id("quantification_rows", payload),
            artifact_type="quantification_rows",
            name="quantification_rows.json",
            data=[row.to_csv_row() for row in result.rows],
        )
    ]
    if result.standard_curve is not None:
        artifacts.append(
            ToolArtifact(
                artifact_id=_artifact_id("standard_curve", payload),
                artifact_type="standard_curve",
                name="standard_curve.json",
                data=result.standard_curve.to_summary(),
            )
        )
    return artifacts


def _normalization_artifacts(
    result: NormalizationPlanResult,
    payload: JsonDict,
) -> list[ToolArtifact]:
    return [
        ToolArtifact(
            artifact_id=_artifact_id("normalization_plan", payload),
            artifact_type="normalization_plan",
            name="normalization_plan.json",
            data=[row.to_csv_row() for row in result.rows],
        )
    ]


def _rna_artifacts(result: RnaWorkflowResult, payload: JsonDict) -> list[ToolArtifact]:
    return _normalization_artifacts(result.normalization, payload) + [
        ToolArtifact(
            artifact_id=_artifact_id("rna_requant_rows", payload),
            artifact_type="rna_requant_rows",
            name="rna_requant_rows.json",
            data=[row.to_requant_row() for row in result.requant_rows],
        ),
        ToolArtifact(
            artifact_id=_artifact_id("rna_downstream_manifest", payload),
            artifact_type="rna_downstream_manifest",
            name="rna_downstream_manifest.json",
            data=[row.to_downstream_row() for row in result.requant_rows],
        ),
    ]


def _janus_preview_artifacts(
    result: NormalizationPlanResult,
    payload: JsonDict,
) -> list[ToolArtifact]:
    rows = list(result.rows)
    return [
        ToolArtifact(
            artifact_id=_artifact_id("janus_worklist_preview", payload),
            artifact_type="janus_worklist_preview",
            name="janus_worklist.csv",
            content_type="text/csv",
            data=janus_minimal_rows(rows),
        ),
        ToolArtifact(
            artifact_id=_artifact_id("janus_audit_preview", payload),
            artifact_type="janus_audit_preview",
            name="janus_audit_worklist.csv",
            content_type="text/csv",
            data=janus_audit_rows(rows),
        ),
    ]


def _load_qc_provenance_report(
    qc_csv: str,
    lineage_csv: str,
    thresholds: dict[str, Any] | None,
) -> QcProvenanceReport:
    parsed_thresholds = thresholds_from_config(thresholds)
    qc_rows = parse_ngs_qc_csv(Path(qc_csv))
    lineage_rows = read_lineage_manifest(Path(lineage_csv))
    return validate_qc_provenance_records(qc_rows, lineage_rows, parsed_thresholds)


def _qc_report_artifacts(report: QcProvenanceReport, payload: JsonDict) -> list[ToolArtifact]:
    return [
        ToolArtifact(
            artifact_id=_artifact_id("downstream_qc_summary", payload),
            artifact_type="downstream_qc_summary",
            name="downstream_qc_summary.json",
            data=build_qc_summary_report(report),
        )
    ]


def _qc_report_errors(report: QcProvenanceReport) -> list[ToolError]:
    errors: list[ToolError] = []
    for record in report.records:
        errors.extend(_qc_record_errors(record))
    return errors


def _qc_record_errors(record: QcProvenanceRecord) -> list[ToolError]:
    return [
        ToolError(
            code=code.value,
            message=f"{record.sample_id}: {record.safe_interpretation}",
            path=f"samples.{record.sample_id}",
            suggested_action="Review QC metrics and LabFlow lineage before analysis use.",
        )
        for code in record.exception_codes
    ]


def _qc_code_warnings(codes: list[str]) -> list[ToolError]:
    return [
        ToolError(
            code=code,
            message=f"Downstream QC review flag observed: {code}.",
            suggested_action="Run validate_qc_provenance with lineage before interpreting QC status.",
        )
        for code in dict.fromkeys(codes)
    ]


def _exception_result(tool_name: str, payload: JsonDict, exc: Exception) -> JsonDict:
    return _result(
        tool_name=tool_name,
        status=ToolStatus.ERROR,
        errors=[
            ToolError(
                code=exc.__class__.__name__,
                message=str(exc),
                suggested_action="Review tool inputs and deterministic config files.",
            )
        ],
        payload=payload,
    )


def _result(
    *,
    tool_name: str,
    status: ToolStatus,
    payload: JsonDict,
    errors: list[ToolError] | None = None,
    warnings: list[ToolError] | None = None,
    artifacts: list[ToolArtifact] | None = None,
    mode: str = "read_only",
    workflow_id: str | None = None,
    approval_token: str | None = None,
) -> JsonDict:
    materialized_errors = errors or []
    materialized_warnings = warnings or []
    materialized_artifacts = artifacts or []
    ok = status not in {ToolStatus.INVALID, ToolStatus.BLOCKED, ToolStatus.ERROR}
    input_hash = _hash_payload(payload)
    audit_event_id, audit_timestamp = _new_audit_identity(tool_name, input_hash)
    audit = ToolAuditEvent(
        audit_event_id=audit_event_id,
        timestamp=audit_timestamp,
        action=tool_name,
        mode=mode,
        workflow_id=workflow_id,
        tool_name=tool_name,
        input_hash=input_hash,
        result_status=status.value,
        exception_codes=[error.code for error in materialized_errors],
        approval_token_id=_approval_token_id(approval_token),
        artifact_ids=[artifact.artifact_id for artifact in materialized_artifacts],
    )
    return ToolResult(
        ok=ok,
        tool_name=tool_name,
        status=status,
        errors=materialized_errors,
        warnings=materialized_warnings,
        artifacts=materialized_artifacts,
        audit_event_id=audit_event_id,
        audit_event=audit,
    ).to_json_dict()


def _new_audit_identity(tool_name: str, input_hash: str) -> tuple[str, str]:
    event_uuid = uuid4().hex
    timestamp_ns = time_ns()
    seconds, nanos = divmod(timestamp_ns, 1_000_000_000)
    timestamp = f"{datetime.fromtimestamp(seconds, UTC):%Y-%m-%dT%H:%M:%S}.{nanos:09d}Z"
    digest = sha256(f"{tool_name}:{input_hash}:{event_uuid}".encode()).hexdigest()[:12]
    return f"audit_{event_uuid}_{digest}", timestamp


def _hash_payload(payload: JsonDict) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode()
    return f"sha256:{sha256(encoded).hexdigest()}"


def _artifact_id(artifact_type: str, payload: JsonDict) -> str:
    digest = sha256((artifact_type + _hash_payload(payload)).encode()).hexdigest()[:16]
    return f"artifact_{digest}"


def _approval_token_id(token: str | None) -> str | None:
    if token is None:
        return None
    return f"approval_{sha256(token.encode()).hexdigest()[:12]}"


_EXCEPTION_EXPLANATIONS: dict[str, JsonDict] = {
    ExceptionCode.MISSING_CONCENTRATION.value: {
        "code": ExceptionCode.MISSING_CONCENTRATION.value,
        "meaning": "A sample has no stock concentration in ng/uL.",
        "blocks_robot_transfer": True,
        "suggested_action": "Run deterministic quantification or exclude the sample.",
    },
    ExceptionCode.MISSING_PLATE_BLANK.value: {
        "code": ExceptionCode.MISSING_PLATE_BLANK.value,
        "meaning": "A sample plate lacks the required blank well reading.",
        "blocks_robot_transfer": True,
        "suggested_action": "Provide one blank well per sample plate before quantification.",
    },
    ExceptionCode.DUPLICATE_SOURCE_LOCATION.value: {
        "code": ExceptionCode.DUPLICATE_SOURCE_LOCATION.value,
        "meaning": "More than one sample claims the same source container and well.",
        "blocks_robot_transfer": True,
        "suggested_action": "Resolve LIMS source locations before planning transfers.",
    },
    ExceptionCode.DUPLICATE_DESTINATION_LOCATION.value: {
        "code": ExceptionCode.DUPLICATE_DESTINATION_LOCATION.value,
        "meaning": "More than one sample targets the same destination container and well.",
        "blocks_robot_transfer": True,
        "suggested_action": "Assign each destination well to at most one transfer.",
    },
    "JANUS_BLOCKED_FOR_INVALID_BATCH": {
        "code": "JANUS_BLOCKED_FOR_INVALID_BATCH",
        "meaning": "Robot worklist generation was requested for an invalid batch.",
        "blocks_robot_transfer": True,
        "suggested_action": "Resolve deterministic validation errors and rerun dry-run.",
    },
    ExceptionCode.UNMATCHED_QC_SAMPLE_ID.value: {
        "code": ExceptionCode.UNMATCHED_QC_SAMPLE_ID.value,
        "meaning": "A downstream QC row does not match a known LabFlow sample ID.",
        "blocks_robot_transfer": False,
        "suggested_action": "Review sample identity and lineage before using the QC result.",
    },
    ExceptionCode.MISSING_QC_RESULT.value: {
        "code": ExceptionCode.MISSING_QC_RESULT.value,
        "meaning": "An expected downstream QC result is absent or missing required metrics.",
        "blocks_robot_transfer": False,
        "suggested_action": "Repeat or review downstream QC summary generation.",
    },
    ExceptionCode.QC_RESULT_FAILED.value: {
        "code": ExceptionCode.QC_RESULT_FAILED.value,
        "meaning": "Downstream QC summary metrics failed configured synthetic thresholds.",
        "blocks_robot_transfer": False,
        "suggested_action": "Review downstream QC metrics and do not infer lab root cause from QC alone.",
    },
    ExceptionCode.QC_PROVENANCE_GAP.value: {
        "code": ExceptionCode.QC_PROVENANCE_GAP.value,
        "meaning": "QC data cannot be fully linked to quantification, normalization, and re-quant lineage.",
        "blocks_robot_transfer": False,
        "suggested_action": "Resolve lineage records before using downstream QC in analysis summaries.",
    },
    ExceptionCode.DOWNSTREAM_QC_REVIEW_REQUIRED.value: {
        "code": ExceptionCode.DOWNSTREAM_QC_REVIEW_REQUIRED.value,
        "meaning": "Downstream QC or provenance evidence requires manual review.",
        "blocks_robot_transfer": False,
        "suggested_action": "Review metrics, sample identity, and lineage before analysis use.",
    },
}
