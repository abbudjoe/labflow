"""Agent-level audit event recording for deterministic tool calls."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from labflow_agent.approvals import approval_token_id
from labflow_agent.models import JsonDict, ToolCallMode, ToolCallPlan


class AuditEvent(BaseModel):
    """Audit record for an agent-visible tool call attempt."""

    model_config = ConfigDict(frozen=True)

    audit_event_id: str = Field(min_length=1)
    timestamp: str = Field(min_length=1)
    actor_type: str = "agent"
    actor_id: str = "labflow-agent"
    action: str = Field(min_length=1)
    mode: ToolCallMode
    workflow_id: str | None = None
    tool_name: str = Field(min_length=1)
    input_hash: str = Field(min_length=1)
    result_status: str = Field(min_length=1)
    exception_codes: tuple[str, ...] = ()
    approval_token_id: str | None = None
    dry_run_audit_event_id: str | None = None
    artifact_ids: tuple[str, ...] = ()
    core_audit_event_id: str | None = None

    def to_json_dict(self) -> JsonDict:
        return self.model_dump(mode="json")


class AuditStore:
    """In-memory audit event registry for local-first agent tests and demos."""

    def __init__(self) -> None:
        self._events: dict[str, AuditEvent] = {}
        self._tool_results: dict[str, JsonDict] = {}

    def record_tool_result(
        self,
        *,
        planned: ToolCallPlan,
        result: JsonDict,
        result_status: str | None = None,
        artifact_ids: tuple[str, ...] | None = None,
        approval_token: str | None = None,
        dry_run_audit_event_id: str | None = None,
    ) -> AuditEvent:
        status = result_status or _result_status(result)
        event = self._new_event(
            planned=planned,
            result_status=status,
            workflow_id=_workflow_id(result),
            exception_codes=_exception_codes(result),
            approval_token=approval_token,
            dry_run_audit_event_id=dry_run_audit_event_id,
            artifact_ids=artifact_ids or _artifact_ids(result),
            core_audit_event_id=_core_audit_event_id(result),
        )
        self._events[event.audit_event_id] = event
        self._tool_results[event.audit_event_id] = dict(result)
        return event

    def record_policy_block(
        self,
        *,
        planned: ToolCallPlan,
        result_status: str,
        exception_code: str,
        approval_token: str | None = None,
        dry_run_audit_event_id: str | None = None,
    ) -> AuditEvent:
        event = self._new_event(
            planned=planned,
            result_status=result_status,
            workflow_id=None,
            exception_codes=(exception_code,),
            approval_token=approval_token,
            dry_run_audit_event_id=dry_run_audit_event_id,
            artifact_ids=(),
            core_audit_event_id=None,
        )
        self._events[event.audit_event_id] = event
        return event

    def get(self, audit_event_id: str) -> AuditEvent | None:
        return self._events.get(audit_event_id)

    def require(self, audit_event_id: str) -> AuditEvent:
        event = self.get(audit_event_id)
        if event is None:
            msg = f"Unknown dry-run audit event: {audit_event_id}"
            raise KeyError(msg)
        return event

    def require_tool_result(self, audit_event_id: str) -> JsonDict:
        result = self._tool_results.get(audit_event_id)
        if result is None:
            msg = f"Unknown tool result for audit event: {audit_event_id}"
            raise KeyError(msg)
        return dict(result)

    def list_events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events.values())

    def attach_artifact_ids(
        self,
        *,
        audit_event_id: str,
        artifact_ids: tuple[str, ...],
    ) -> AuditEvent:
        event = self.require(audit_event_id)
        updated = event.model_copy(update={"artifact_ids": artifact_ids})
        self._events[audit_event_id] = updated
        return updated

    def _new_event(
        self,
        *,
        planned: ToolCallPlan,
        result_status: str,
        workflow_id: str | None,
        exception_codes: tuple[str, ...],
        approval_token: str | None,
        dry_run_audit_event_id: str | None,
        artifact_ids: tuple[str, ...],
        core_audit_event_id: str | None,
    ) -> AuditEvent:
        input_hash = hash_payload(planned.arguments)
        digest = sha256(f"{planned.tool_name}:{input_hash}:{uuid4().hex}".encode()).hexdigest()[:12]
        return AuditEvent(
            audit_event_id=f"audit_agent_{uuid4().hex}_{digest}",
            timestamp=datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z"),
            action=planned.tool_name,
            mode=planned.mode,
            workflow_id=workflow_id,
            tool_name=planned.tool_name,
            input_hash=input_hash,
            result_status=result_status,
            exception_codes=exception_codes,
            approval_token_id=approval_token_id(approval_token) if approval_token else None,
            dry_run_audit_event_id=dry_run_audit_event_id,
            artifact_ids=artifact_ids,
            core_audit_event_id=core_audit_event_id,
        )


def hash_payload(payload: JsonDict) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode()
    return f"sha256:{sha256(encoded).hexdigest()}"


def _result_status(result: JsonDict) -> str:
    status = result.get("status")
    return status if isinstance(status, str) else "error"


def _workflow_id(result: JsonDict) -> str | None:
    audit = result.get("audit_event")
    if isinstance(audit, dict):
        workflow_id = audit.get("workflow_id")
        if isinstance(workflow_id, str):
            return workflow_id
    return None


def _exception_codes(result: JsonDict) -> tuple[str, ...]:
    errors = result.get("errors")
    if not isinstance(errors, list):
        return ()
    codes: list[str] = []
    for item in errors:
        if isinstance(item, dict) and isinstance(item.get("code"), str):
            codes.append(item["code"])
    return tuple(codes)


def _artifact_ids(result: JsonDict) -> tuple[str, ...]:
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, list):
        return ()
    artifact_ids: list[str] = []
    for artifact in artifacts:
        if isinstance(artifact, dict) and isinstance(artifact.get("artifact_id"), str):
            artifact_ids.append(artifact["artifact_id"])
    return tuple(artifact_ids)


def _core_audit_event_id(result: JsonDict) -> str | None:
    value = result.get("audit_event_id")
    return value if isinstance(value, str) else None


def error_result(*, tool_name: str, status: str, code: str, message: str) -> JsonDict:
    """Build a JSON-compatible blocked/error tool result for policy failures."""

    return {
        "ok": False,
        "tool_name": tool_name,
        "status": status,
        "errors": [{"code": code, "message": message, "path": None, "suggested_action": None}],
        "warnings": [],
        "artifacts": [],
        "audit_event_id": "",
        "audit_event": None,
    }
