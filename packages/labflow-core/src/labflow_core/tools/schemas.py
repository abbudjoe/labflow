"""Structured JSON-compatible tool result schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

JsonDict: TypeAlias = dict[str, Any]


class ToolStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    OK = "ok"
    BLOCKED = "blocked"
    ERROR = "error"


class ToolError(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    path: str | None = None
    suggested_action: str | None = None


class ToolArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    name: str = Field(min_length=1)
    content_type: str = "application/json"
    data: JsonDict | list[JsonDict] | list[str] | str


class ToolAuditEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    audit_event_id: str = Field(min_length=1)
    timestamp: str = Field(min_length=1)
    actor_type: str = "tool_wrapper"
    actor_id: str = "labflow-core"
    action: str = Field(min_length=1)
    mode: str = "read_only"
    workflow_id: str | None = None
    tool_name: str = Field(min_length=1)
    input_hash: str = Field(min_length=1)
    result_status: str = Field(min_length=1)
    exception_codes: list[str] = Field(default_factory=list)
    approval_token_id: str | None = None
    artifact_ids: list[str] = Field(default_factory=list)


class ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    tool_name: str = Field(min_length=1)
    status: ToolStatus
    errors: list[ToolError] = Field(default_factory=list)
    warnings: list[ToolError] = Field(default_factory=list)
    artifacts: list[ToolArtifact] = Field(default_factory=list)
    audit_event_id: str
    audit_event: ToolAuditEvent

    def to_json_dict(self) -> JsonDict:
        return self.model_dump(mode="json")
