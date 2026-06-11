"""FastAPI entrypoint for LabFlow AI Studio."""

from __future__ import annotations

from fastapi.exceptions import RequestValidationError
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from labflow_api.routes import agent, artifacts, audit, evals, health, rag, tools, workflows
from labflow_api.routes._shared import error_envelope
from labflow_api.settings import ApiSettings, ApiState


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    """Create a local-first LabFlow API application."""

    app = FastAPI(
        title="LabFlow AI Studio API",
        version="0.1.0",
        description="Local API for synthetic LabFlow validation, RAG, agent tools, evals, audit, and artifacts.",
    )
    app.state.labflow_state = ApiState(settings)

    app.include_router(health.router)
    app.include_router(workflows.router)
    app.include_router(rag.router)
    app.include_router(agent.router)
    app.include_router(tools.router)
    app.include_router(evals.router)
    app.include_router(audit.router)
    app.include_router(artifacts.router)

    @app.exception_handler(KeyError)
    async def key_error_handler(_request: Request, exc: KeyError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=error_envelope(code="NOT_FOUND", message=str(exc)),
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=error_envelope(code="BAD_REQUEST", message=str(exc)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_envelope(
                code="VALIDATION_ERROR",
                message="Request validation failed.",
                details={"errors": exc.errors()},
            ),
        )

    @app.exception_handler(Exception)
    async def exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=error_envelope(
                code="INTERNAL_ERROR",
                message="An unexpected API error occurred.",
            ),
        )

    return app


app = create_app()
