"""Deterministic audit event records."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from labflow_core.domain.identifiers import (
    optional_nonblank_identifier,
    require_nonblank_identifier,
)


class AuditAction(StrEnum):
    TOOL_CALLED = "TOOL_CALLED"
    DRY_RUN = "DRY_RUN"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    ARTIFACT_GENERATED = "ARTIFACT_GENERATED"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"


def deterministic_audit_timestamp() -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC)


class AuditEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str = Field(min_length=1)
    action: AuditAction
    actor: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    batch_id: str | None = None
    sample_id: str | None = None
    dry_run: bool = False
    approved: bool = False
    created_at: datetime = Field(default_factory=deterministic_audit_timestamp)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_id", "actor", "entity_type", "entity_id")
    @classmethod
    def required_identifier(cls, value: str, info: ValidationInfo) -> str:
        return require_nonblank_identifier(value, info.field_name)

    @field_validator("batch_id", "sample_id", mode="before")
    @classmethod
    def optional_identifier(cls, value: str | None) -> str | None:
        return optional_nonblank_identifier(value)

    def to_row(self) -> dict[str, str | bool]:
        return {
            "event_id": self.event_id,
            "action": self.action.value,
            "actor": self.actor,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "batch_id": self.batch_id or "",
            "sample_id": self.sample_id or "",
            "dry_run": self.dry_run,
            "approved": self.approved,
            "created_at": self.created_at.isoformat(),
            "metadata_json": json.dumps(self.metadata, sort_keys=True),
        }


AUDIT_EVENT_COLUMNS = [
    "event_id",
    "action",
    "actor",
    "entity_type",
    "entity_id",
    "batch_id",
    "sample_id",
    "dry_run",
    "approved",
    "created_at",
    "metadata_json",
]
