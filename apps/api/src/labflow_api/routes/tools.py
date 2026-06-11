"""Tool execution routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from labflow_agent import ToolCallMode, ToolCallPlan
from labflow_api.routes._shared import envelope, state_from_request

router = APIRouter(prefix="/tools", tags=["tools"])


class ToolExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    tool_name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    mode: ToolCallMode | None = None
    reason: str = "API tool execution request."


@router.post("/execute")
def execute_tool(request: ToolExecuteRequest, fastapi_request: Request) -> dict[str, Any]:
    state = state_from_request(fastapi_request)
    mode = request.mode or _mode_from_arguments(request.arguments)
    executed = state.tool_runtime.execute_tool_call(
        ToolCallPlan(
            tool_name=request.tool_name,
            arguments=request.arguments,
            mode=mode,
            reason=request.reason,
        )
    )
    state.file_artifact_store.persist_many(state.tool_runtime.artifact_records)
    return envelope(data=executed.model_dump(mode="json"))


def _mode_from_arguments(arguments: dict[str, Any]) -> ToolCallMode:
    if arguments.get("dry_run") is True:
        return ToolCallMode.DRY_RUN
    if arguments.get("dry_run") is False:
        return ToolCallMode.COMMIT
    return ToolCallMode.READ_ONLY
