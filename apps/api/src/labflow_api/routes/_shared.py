"""Shared FastAPI response helpers."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field

from labflow_api.settings import ApiState


class ApiError(BaseModel):
    """Structured API error payload."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


def trace_id() -> str:
    return f"trace_{uuid4().hex}"


def envelope(*, data: Any, trace: str | None = None) -> dict[str, Any]:
    return {"ok": True, "trace_id": trace or trace_id(), "data": data}


def error_envelope(
    *,
    code: str,
    message: str,
    trace: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "trace_id": trace or trace_id(),
        "error": ApiError(
            code=code,
            message=message,
            details=details or {},
        ).model_dump(mode="json"),
    }


def state_from_request(request: Request) -> ApiState:
    state = getattr(request.app.state, "labflow_state", None)
    if not isinstance(state, ApiState):
        msg = "LabFlow API state is not initialized."
        raise RuntimeError(msg)
    return state
