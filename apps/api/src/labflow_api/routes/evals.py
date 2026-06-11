"""RAG eval routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from labflow_api.routes._shared import envelope, state_from_request
from labflow_rag.evals.runner import EvalRunConfig, run_eval

router = APIRouter(prefix="/evals", tags=["evals"])


class EvalRunRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    retrieval_only: bool = False
    top_k: int = Field(default=6, ge=1)


@router.post("/run")
def run_evals(request: EvalRunRequest, fastapi_request: Request) -> dict[str, Any]:
    state = state_from_request(fastapi_request)
    report = run_eval(
        EvalRunConfig(
            cases_path=state.settings.eval_cases_path,
            corpus_dir=state.settings.corpus_dir,
            top_k=request.top_k,
            retrieval_only=request.retrieval_only,
        ),
        index=state.index,
        retriever=state.retriever,
    )
    state.eval_reports[report.eval_run_id] = report
    return envelope(data=report.to_json_dict())


@router.get("/runs/{eval_run_id}")
def get_eval_run(eval_run_id: str, fastapi_request: Request) -> dict[str, Any]:
    state = state_from_request(fastapi_request)
    try:
        report = state.eval_reports[eval_run_id]
    except KeyError as exc:
        msg = f"Unknown eval run: {eval_run_id}"
        raise KeyError(msg) from exc
    return envelope(data=report.to_json_dict())
