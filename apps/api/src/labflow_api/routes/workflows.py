"""Workflow validation routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from labflow_api.routes._shared import envelope
from labflow_core.dsl.validator import validate_workflow_text

router = APIRouter(prefix="/workflows", tags=["workflows"])


class ValidateWorkflowRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    workflow_yaml: str = Field(min_length=1)


@router.post("/validate")
def validate_workflow(request: ValidateWorkflowRequest) -> dict[str, Any]:
    validation = validate_workflow_text(request.workflow_yaml)
    diagnostics = [
        {
            "code": diagnostic.code,
            "message": diagnostic.message,
            "severity": diagnostic.severity,
            "path": diagnostic.path,
            "suggested_action": diagnostic.suggested_action,
        }
        for diagnostic in validation.diagnostics
    ]
    return envelope(data={"ok": not diagnostics, "diagnostics": diagnostics})
