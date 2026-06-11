"""YAML parser for LabFlow workflow DSL files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from labflow_core.dsl.diagnostics import (
    DiagnosticCode,
    DiagnosticSource,
    WorkflowDiagnostic,
)
from labflow_core.dsl.models import LabFlowWorkflow


@dataclass(frozen=True)
class ParseResult:
    workflow: LabFlowWorkflow | None
    diagnostics: tuple[WorkflowDiagnostic, ...]

    @property
    def ok(self) -> bool:
        return self.workflow is not None and not self.diagnostics


def parse_workflow_file(path: Path) -> ParseResult:
    return parse_workflow_text(path.read_text(), source_path=path)


def parse_workflow_text(text: str, *, source_path: Path | None = None) -> ParseResult:
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return ParseResult(
            workflow=None,
            diagnostics=(
                WorkflowDiagnostic.error(
                    code=DiagnosticCode.YAML_PARSE_ERROR,
                    message=f"Workflow YAML could not be parsed: {exc}",
                    path=str(source_path or "<string>"),
                    source=DiagnosticSource.YAML_PARSER,
                    suggested_action="Fix YAML syntax before running LabFlow validation.",
                ),
            ),
        )

    if not isinstance(raw, dict):
        return ParseResult(
            workflow=None,
            diagnostics=(
                WorkflowDiagnostic.error(
                    code=DiagnosticCode.SCHEMA_VALIDATION_ERROR,
                    message="Workflow YAML must contain a mapping at the document root.",
                    path="$",
                    source=DiagnosticSource.SCHEMA_VALIDATOR,
                    suggested_action="Provide workflow, batch, containers, and related mappings.",
                ),
            ),
        )

    try:
        return ParseResult(
            workflow=LabFlowWorkflow.model_validate(raw),
            diagnostics=(),
        )
    except ValidationError as exc:
        return ParseResult(
            workflow=None,
            diagnostics=_diagnostics_from_validation_error(exc),
        )


def _diagnostics_from_validation_error(exc: ValidationError) -> tuple[WorkflowDiagnostic, ...]:
    diagnostics: list[WorkflowDiagnostic] = []
    for error in exc.errors():
        diagnostics.append(
            WorkflowDiagnostic.error(
                code=DiagnosticCode.SCHEMA_VALIDATION_ERROR,
                message=str(error["msg"]),
                path=_format_error_path(error.get("loc", ())),
                source=DiagnosticSource.SCHEMA_VALIDATOR,
                suggested_action="Update the workflow YAML to match the LabFlow DSL schema.",
            )
        )
    return tuple(diagnostics)


def _format_error_path(location: Any) -> str:
    if not location:
        return "$"
    if isinstance(location, tuple):
        return ".".join(str(part) for part in location)
    return str(location)
