"""Artifact routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from labflow_api.routes._shared import envelope, state_from_request

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("/{artifact_id}")
def get_artifact(artifact_id: str, fastapi_request: Request) -> dict[str, Any]:
    state = state_from_request(fastapi_request)
    record = state.file_artifact_store.get(artifact_id)
    if record is None:
        in_memory_record = state.tool_runtime.artifact_store.get(artifact_id)
        if in_memory_record is not None:
            state.file_artifact_store.persist(in_memory_record)
            record = in_memory_record.to_json_dict()
    if record is None:
        msg = f"Unknown artifact: {artifact_id}"
        raise KeyError(msg)
    return envelope(data=record)
