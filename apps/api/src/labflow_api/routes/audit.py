"""Audit event routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from labflow_api.routes._shared import envelope, state_from_request

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events")
def list_audit_events(fastapi_request: Request) -> dict[str, Any]:
    state = state_from_request(fastapi_request)
    return envelope(
        data={
            "events": [
                event.to_json_dict()
                for event in state.tool_runtime.audit_events
            ]
        }
    )


@router.get("/events/{audit_event_id}")
def get_audit_event(audit_event_id: str, fastapi_request: Request) -> dict[str, Any]:
    state = state_from_request(fastapi_request)
    event = state.tool_runtime.audit_store.get(audit_event_id)
    if event is None:
        msg = f"Unknown audit event: {audit_event_id}"
        raise KeyError(msg)
    return envelope(data=event.to_json_dict())
