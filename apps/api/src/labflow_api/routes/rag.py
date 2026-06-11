"""RAG query routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from labflow_api.routes._shared import envelope, state_from_request

router = APIRouter(prefix="/rag", tags=["rag"])


class RagQueryRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    question: str = Field(min_length=1)


@router.post("/query")
def query_rag(request: RagQueryRequest, fastapi_request: Request) -> dict[str, Any]:
    state = state_from_request(fastapi_request)
    return envelope(data=state.rag_query(request.question))


@router.post("/debug")
def debug_rag(request: RagQueryRequest, fastapi_request: Request) -> dict[str, Any]:
    state = state_from_request(fastapi_request)
    return envelope(data=state.rag_debug(request.question))
