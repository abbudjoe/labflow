"""Structured diagnostics for LabFlow workflow DSL validation."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DiagnosticSource(StrEnum):
    YAML_PARSER = "yaml_parser"
    SCHEMA_VALIDATOR = "schema_validator"
    DOMAIN_VALIDATOR = "domain_validator"


class DiagnosticCode(StrEnum):
    YAML_PARSE_ERROR = "YAML_PARSE_ERROR"
    SCHEMA_VALIDATION_ERROR = "SCHEMA_VALIDATION_ERROR"
    MISSING_PLATE_BLANK = "MISSING_PLATE_BLANK"
    MISSING_BATCH_STANDARD_CURVE = "MISSING_BATCH_STANDARD_CURVE"
    INVALID_BATCH_STANDARD_CURVE = "INVALID_BATCH_STANDARD_CURVE"
    INVALID_WELL = "INVALID_WELL"
    MOLAR_TARGET_NOT_SUPPORTED = "MOLAR_TARGET_NOT_SUPPORTED"
    MISSING_CONCENTRATION = "MISSING_CONCENTRATION"
    MISSING_DESTINATION_LOCATION = "MISSING_DESTINATION_LOCATION"
    DUPLICATE_SOURCE_LOCATION = "DUPLICATE_SOURCE_LOCATION"
    DUPLICATE_DESTINATION_LOCATION = "DUPLICATE_DESTINATION_LOCATION"
    INVALID_SAMPLE_PLATE_LAYOUT = "INVALID_SAMPLE_PLATE_LAYOUT"
    REQUIRED_ARTIFACT_MISSING = "REQUIRED_ARTIFACT_MISSING"
    JANUS_BLOCKED_FOR_INVALID_BATCH = "JANUS_BLOCKED_FOR_INVALID_BATCH"


class WorkflowDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=1)
    severity: DiagnosticSeverity
    message: str = Field(min_length=1)
    path: str = Field(min_length=1)
    source: DiagnosticSource
    suggested_action: str = Field(min_length=1)

    @classmethod
    def error(
        cls,
        *,
        code: DiagnosticCode,
        message: str,
        path: str,
        source: DiagnosticSource,
        suggested_action: str,
    ) -> WorkflowDiagnostic:
        return cls(
            code=code.value,
            severity=DiagnosticSeverity.ERROR,
            message=message,
            path=path,
            source=source,
            suggested_action=suggested_action,
        )
