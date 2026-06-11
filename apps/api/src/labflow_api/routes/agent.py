"""Agent routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from labflow_agent import AgentRequest
from labflow_api.routes._shared import envelope, state_from_request

router = APIRouter(prefix="/agent", tags=["agent"])


class ExplainDiagnosticRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    question: str = Field(default="Explain this LabFlow diagnostic.", min_length=1)
    diagnostic_code: str = Field(min_length=1)
    workflow_yaml: str | None = None
    batch_id: str | None = None


@router.post("/explain-diagnostic")
def explain_diagnostic(
    request: ExplainDiagnosticRequest,
    fastapi_request: Request,
) -> dict[str, Any]:
    state = state_from_request(fastapi_request)
    response = state.agent_runtime.run(
        AgentRequest(
            question=request.question,
            diagnostic_code=request.diagnostic_code,
            workflow_yaml=request.workflow_yaml,
            batch_id=request.batch_id,
        )
    )
    return envelope(data=response.to_json_dict())
