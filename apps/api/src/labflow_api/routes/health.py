"""Health routes."""

from __future__ import annotations

from fastapi import APIRouter

from labflow_api.routes._shared import envelope

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    return envelope(data={"status": "ok", "service": "labflow-api"})
