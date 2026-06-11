"""Structured exception records for deterministic workflow reports."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from labflow_core.domain.identifiers import (
    optional_nonblank_identifier,
    require_nonblank_identifier,
)
from labflow_core.domain.statuses import ExceptionCode, ExceptionSeverity
from labflow_core.domain.wells import WellCoordinate


class ExceptionRecord(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    exception_code: ExceptionCode
    severity: ExceptionSeverity
    message: str = Field(min_length=1)
    suggested_action: str = Field(
        min_length=1,
        validation_alias=AliasChoices("suggested_action", "recommended_action"),
    )
    blocks_robot_transfer: bool
    sample_id: str | None = None
    batch_id: str | None = None
    source_container_id: str | None = None
    source_well: WellCoordinate | None = None
    destination_container_id: str | None = None
    destination_well: WellCoordinate | None = None

    @field_validator("source_well", "destination_well", mode="before")
    @classmethod
    def parse_optional_well(cls, value: Any) -> Any:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return WellCoordinate.model_validate(value)

    @field_validator("message", "suggested_action")
    @classmethod
    def required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_nonblank_identifier(value, info.field_name)

    @field_validator(
        "sample_id",
        "batch_id",
        "source_container_id",
        "destination_container_id",
        mode="before",
    )
    @classmethod
    def optional_identifier(cls, value: str | None) -> str | None:
        return optional_nonblank_identifier(value)

    @property
    def recommended_action(self) -> str:
        return self.suggested_action

    def to_report_row(self) -> dict[str, str | bool]:
        return {
            "exception_code": self.exception_code.value,
            "severity": self.severity.value,
            "batch_id": self.batch_id or "",
            "sample_id": self.sample_id or "",
            "source_container_id": self.source_container_id or "",
            "source_well": str(self.source_well) if self.source_well else "",
            "destination_container_id": self.destination_container_id or "",
            "destination_well": str(self.destination_well) if self.destination_well else "",
            "message": self.message,
            "suggested_action": self.suggested_action,
            "blocks_robot_transfer": self.blocks_robot_transfer,
        }


EXCEPTION_REPORT_COLUMNS = [
    "exception_code",
    "severity",
    "batch_id",
    "sample_id",
    "source_container_id",
    "source_well",
    "destination_container_id",
    "destination_well",
    "message",
    "suggested_action",
    "blocks_robot_transfer",
]
