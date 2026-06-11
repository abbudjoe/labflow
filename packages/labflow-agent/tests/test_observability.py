from __future__ import annotations

from pathlib import Path

from labflow_agent import (
    AgentPlan,
    AgentRequest,
    AgentTask,
    AgentToolRuntime,
    LabFlowAgentRuntime,
    ModelMetadata,
    PlanDiagnostic,
    PromptRegistry,
)
from labflow_agent.prompts import hash_prompt_text
from labflow_agent.models import ToolCallMode, ToolCallPlan


class DiagnosticModel:
    metadata = ModelMetadata(
        model_id="diagnostic_model",
        version="0.0.1",
        provider="test-provider",
    )

    def plan(self, request: AgentRequest) -> AgentPlan:
        return AgentPlan(
            task=AgentTask.UNSUPPORTED,
            rationale="Provider timed out.",
            retrieval_query=request.question,
            unsupported_reason="Provider timed out.",
            diagnostic=PlanDiagnostic(
                code="provider_timeout",
                message="Provider timed out.",
                provider="test-provider",
            ),
        )


def test_prompt_hash_is_stable() -> None:
    prompt_path = Path("prompts/runtime/diagnostic_explainer.md")
    prompt_text = prompt_path.read_text()
    registry = PromptRegistry()

    metadata = registry.get("diagnostic_explainer")

    assert metadata.version == "0.1.0"
    assert metadata.sha256 == hash_prompt_text(prompt_text)
    assert metadata.sha256 == hash_prompt_text(prompt_text)


def test_prompt_registry_loads_from_non_repo_cwd(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    registry = PromptRegistry()

    assert registry.get("rag_answer").prompt_id == "rag_answer"
    assert len(registry.list_prompts()) == 4


def test_agent_response_includes_trace_metadata() -> None:
    runtime = LabFlowAgentRuntime()

    response = runtime.ask(
        "Explain MISSING_CONCENTRATION.",
        diagnostic_code="MISSING_CONCENTRATION",
    )

    assert response.trace is not None
    assert response.trace.trace_id.startswith("trace_agent_")
    assert response.trace.request_id.startswith("request_")
    assert response.trace.prompt_id == "diagnostic_explainer"
    assert response.trace.prompt_version == "0.1.0"
    assert response.trace.prompt_sha256.startswith("sha256:")
    assert response.trace.model_id == "deterministic_fake_planner"
    assert response.trace.model_version == "0.1.0"
    assert response.trace.model_provider == "labflow-local"
    assert "explain_exception_code" in response.trace.tool_calls
    assert response.trace.latency_ms >= 0


def test_rag_answer_response_uses_rag_prompt_metadata() -> None:
    runtime = LabFlowAgentRuntime()

    response = runtime.ask("What happens when calculated sample transfer volume is below 1 uL?")

    assert response.task is AgentTask.ANSWER_WORKFLOW_QUESTION
    assert response.trace is not None
    assert response.trace.prompt_id == "rag_answer"
    assert response.trace.retrieved_chunk_ids


def test_agent_trace_includes_model_diagnostic_and_unsupported_status() -> None:
    runtime = LabFlowAgentRuntime(model=DiagnosticModel())

    response = runtime.ask("Can this batch run?")

    assert response.trace is not None
    assert response.trace.outcome_status == "unsupported"
    assert response.trace.model_provider == "test-provider"
    assert response.trace.model_diagnostic is not None
    assert response.trace.model_diagnostic.code == "provider_timeout"


def test_tool_output_includes_observability_payload() -> None:
    runtime = AgentToolRuntime()

    executed = runtime.execute_tool_call(
        ToolCallPlan(
            tool_name="explain_exception_code",
            arguments={"exception_code": "MISSING_CONCENTRATION"},
            mode=ToolCallMode.READ_ONLY,
            reason="Observe deterministic tool execution.",
        )
    )

    observability = executed.result["observability"]
    assert observability["trace_id"].startswith("trace_tool_")
    assert observability["tool_name"] == "explain_exception_code"
    assert observability["outcome_status"] == "ok"
    assert observability["latency_ms"] >= 0
