"""Trace creation helpers for LabFlow agent and tool execution."""

from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from labflow_agent.models import (
    AgentTrace,
    ExecutedToolCall,
    ModelExecutionMetadata,
    ModelMetadata,
    PlanDiagnostic,
)
from labflow_agent.prompts import PromptMetadata


class TraceTimer:
    """Small monotonic timer for request latency."""

    def __init__(self) -> None:
        self._start = perf_counter()

    def elapsed_ms(self) -> float:
        return (perf_counter() - self._start) * 1000


def new_trace_id(prefix: str = "trace") -> str:
    return f"{prefix}_{uuid4().hex}"


def new_request_id() -> str:
    return f"request_{uuid4().hex}"


def create_agent_trace(
    *,
    request_id: str,
    prompt: PromptMetadata,
    model: ModelMetadata,
    retrieved_chunk_ids: tuple[str, ...],
    tool_calls: tuple[ExecutedToolCall, ...],
    latency_ms: float,
    outcome_status: str,
    model_diagnostic: PlanDiagnostic | None = None,
    answer_composer_diagnostic: PlanDiagnostic | None = None,
    model_execution: ModelExecutionMetadata | None = None,
    answer_composer_execution: ModelExecutionMetadata | None = None,
    answer_composer_fallback: bool = False,
    answer_composer_final_answer_source: str = "deterministic_baseline",
) -> AgentTrace:
    """Create a serializable trace for an agent response."""

    return AgentTrace(
        trace_id=new_trace_id("trace_agent"),
        request_id=request_id,
        prompt_id=prompt.prompt_id,
        prompt_version=prompt.version,
        prompt_sha256=prompt.sha256,
        model_id=model.model_id,
        model_version=model.version,
        model_provider=model.provider,
        model_diagnostic=model_diagnostic,
        answer_composer_diagnostic=answer_composer_diagnostic,
        model_execution=model_execution,
        answer_composer_execution=answer_composer_execution,
        answer_composer_fallback=answer_composer_fallback,
        answer_composer_final_answer_source=answer_composer_final_answer_source,
        retrieved_chunk_ids=retrieved_chunk_ids,
        tool_calls=tuple(call.tool_name for call in tool_calls),
        latency_ms=latency_ms,
        input_tokens=_sum_optional_ints(
            model_execution.input_tokens if model_execution else None,
            answer_composer_execution.input_tokens if answer_composer_execution else None,
        ),
        output_tokens=_sum_optional_ints(
            model_execution.output_tokens if model_execution else None,
            answer_composer_execution.output_tokens if answer_composer_execution else None,
        ),
        outcome_status=outcome_status,
    )


def _sum_optional_ints(*values: int | None) -> int | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)
