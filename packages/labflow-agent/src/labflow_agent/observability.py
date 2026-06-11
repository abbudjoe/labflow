"""Observability payload helpers for LabFlow agent outputs."""

from __future__ import annotations

from labflow_agent.models import AgentTrace, JsonDict
from labflow_agent.prompts import PromptMetadata


def agent_observability_payload(trace: AgentTrace, prompt: PromptMetadata) -> JsonDict:
    """Return a compact observability payload for API/tool surfaces."""

    return {
        "trace_id": trace.trace_id,
        "request_id": trace.request_id,
        "prompt": prompt.to_json_dict(),
        "model_id": trace.model_id,
        "model_version": trace.model_version,
        "model_provider": trace.model_provider,
        "model_diagnostic": (
            trace.model_diagnostic.model_dump(mode="json") if trace.model_diagnostic else None
        ),
        "retrieved_chunk_ids": list(trace.retrieved_chunk_ids),
        "tool_calls": list(trace.tool_calls),
        "latency_ms": trace.latency_ms,
        "outcome_status": trace.outcome_status,
        "input_tokens": trace.input_tokens,
        "output_tokens": trace.output_tokens,
        "cost_usd": trace.cost_usd,
    }


def tool_observability_payload(*, trace_id: str, tool_name: str, latency_ms: float, status: str) -> JsonDict:
    """Return a minimal observability payload for deterministic tool execution."""

    return {
        "trace_id": trace_id,
        "tool_name": tool_name,
        "latency_ms": latency_ms,
        "outcome_status": status,
    }
