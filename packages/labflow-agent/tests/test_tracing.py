from __future__ import annotations

from labflow_agent.models import ModelExecutionMetadata, ModelMetadata
from labflow_agent.prompts import PromptMetadata
from labflow_agent.tracing import create_agent_trace


def test_agent_trace_aggregates_provider_token_usage() -> None:
    trace = create_agent_trace(
        request_id="request_test",
        prompt=PromptMetadata(
            prompt_id="agent_planner",
            version="0.1.0",
            sha256="sha256:test",
            created_at="2026-01-01",
            notes="test",
            path="prompts/runtime/agent_planner.md",
        ),
        model=ModelMetadata(
            model_id="planner-model",
            version="adapter-test",
            provider="openrouter",
        ),
        retrieved_chunk_ids=(),
        tool_calls=(),
        latency_ms=1.0,
        outcome_status="ok",
        model_execution=ModelExecutionMetadata(
            requested_model_id="planner-model",
            final_requested_model_id="planner-model",
            input_tokens=100,
            output_tokens=20,
            total_tokens=120,
        ),
        answer_composer_execution=ModelExecutionMetadata(
            requested_model_id="answer-model",
            final_requested_model_id="answer-model",
            input_tokens=50,
            output_tokens=10,
            total_tokens=60,
        ),
    )

    assert trace.input_tokens == 150
    assert trace.output_tokens == 30


def test_agent_trace_keeps_token_usage_null_when_provider_does_not_report_usage() -> None:
    trace = create_agent_trace(
        request_id="request_test",
        prompt=PromptMetadata(
            prompt_id="agent_planner",
            version="0.1.0",
            sha256="sha256:test",
            created_at="2026-01-01",
            notes="test",
            path="prompts/runtime/agent_planner.md",
        ),
        model=ModelMetadata(
            model_id="planner-model",
            version="adapter-test",
            provider="deterministic",
        ),
        retrieved_chunk_ids=(),
        tool_calls=(),
        latency_ms=1.0,
        outcome_status="ok",
    )

    assert trace.input_tokens is None
    assert trace.output_tokens is None
