from __future__ import annotations

from pathlib import Path

import pytest

from labflow_agent import (
    AgentPlan,
    AgentRequest,
    AgentTask,
    AgentToolRuntime,
    GroundedAnswerContext,
    GroundedAnswerDraft,
    LabFlowAgentRuntime,
    ModelMetadata,
    PlanDiagnostic,
    ToolCallMode,
    ToolCallPlan,
)


class FailingAnswerModel:
    metadata = ModelMetadata(
        model_id="failing-answer-model",
        version="test",
        provider="test-answer",
    )

    def draft(self, context: GroundedAnswerContext) -> GroundedAnswerDraft:
        del context
        raise RuntimeError("provider payload should not be exposed")


class DiagnosticSourceFamilyModel:
    metadata = ModelMetadata(
        model_id="diagnostic-source-family-model",
        version="test",
        provider="test",
    )

    def plan(self, request: AgentRequest) -> AgentPlan:
        return AgentPlan(
            task=AgentTask.ANSWER_WORKFLOW_QUESTION,
            rationale="Test plan with corpus expansion metadata.",
            retrieval_query=f"{request.question} infer missing concentration",
            diagnostic=PlanDiagnostic(
                code="model_retrieval_query_sanitized",
                message="Test diagnostic.",
                details={
                    "corpus_expansion_source_documents": (
                        "ai_guardrails_policy.md,batch_readiness_doctrine.md"
                    )
                },
            ),
        )


def _workflow_text(name: str) -> str:
    return Path("examples/workflows", name).read_text()


def test_agent_explains_missing_blank_using_rag_and_validate_tool() -> None:
    runtime = LabFlowAgentRuntime()

    response = runtime.ask(
        "Why is this DNA quant batch not robot-ready because of the missing blank?",
        workflow_yaml=_workflow_text("invalid_missing_blank.workflow.yaml"),
        batch_id="DNA_QUANT_BAD_BLANK",
    )

    assert response.task is AgentTask.VALIDATE_BATCH
    assert response.tool_calls
    assert response.tool_calls[0].tool_name == "validate_batch"
    error_codes = {
        error["code"]
        for call in response.tool_calls
        for error in call.result.get("errors", [])
    }
    assert "MISSING_PLATE_BLANK" in error_codes
    assert "MISSING_PLATE_BLANK" in response.answer
    assert "batch_readiness_doctrine.md" in {source.document_id for source in response.sources}
    assert "validate_batch" in {call.tool_name for call in response.tool_calls}
    assert response.blocked_reason == "validate_batch returned status invalid."


def test_agent_explains_split_workflow_with_required_sources() -> None:
    runtime = LabFlowAgentRuntime()

    response = runtime.ask("What happens when calculated sample transfer volume is below 1 uL?")

    document_ids = {source.document_id for source in response.sources}
    assert response.task is AgentTask.ANSWER_WORKFLOW_QUESTION
    assert response.tool_calls == ()
    assert "dna_normalization_sop.md" in document_ids
    assert "exception_handling_manual.md" in document_ids
    assert "sample_ancestry_policy.md" in document_ids
    assert "split" in response.answer.casefold()


def test_agent_refuses_unsupported_question() -> None:
    runtime = LabFlowAgentRuntime()

    response = runtime.ask("Who won the ice hockey championship on Europa in 2035?")

    assert response.task is AgentTask.UNSUPPORTED
    assert response.unsupported is True
    assert response.sources == ()
    assert response.tool_calls == ()
    assert "do not have enough support" in response.answer
    assert response.blocked_reason is not None


def test_agent_refuses_mixed_off_domain_question_even_when_rag_could_match() -> None:
    runtime = LabFlowAgentRuntime()

    response = runtime.ask("Can pizza fix the missing blank in this batch?")

    assert response.task is AgentTask.UNSUPPORTED
    assert response.unsupported is True
    assert response.sources == ()
    assert response.tool_calls == ()
    assert response.answer == "I do not have enough support in the LabFlow knowledge corpus to answer that."


def test_agent_does_not_invent_missing_concentration() -> None:
    runtime = LabFlowAgentRuntime()

    response = runtime.ask(
        "Can the AI fill in the missing concentration so this RNA batch validates?",
        workflow_yaml=_workflow_text("invalid_rna_norm_requant.workflow.yaml"),
        batch_id="RNA_BATCH_BAD_001",
    )

    error_codes = {
        error["code"]
        for call in response.tool_calls
        for error in call.result.get("errors", [])
    }
    assert response.task is AgentTask.VALIDATE_BATCH
    assert "MISSING_CONCENTRATION" in error_codes
    assert "MISSING_CONCENTRATION" in response.answer
    assert "infer" not in response.answer.casefold()
    assert "estimate" not in response.answer.casefold()
    assert response.blocked_reason == "validate_batch returned status invalid."
    assert response.next_safe_action.startswith("Fix the reported deterministic errors")


def test_agent_validates_any_supplied_workflow_yaml() -> None:
    runtime = LabFlowAgentRuntime()

    response = runtime.ask(
        "Is this ok?",
        workflow_yaml=_workflow_text("invalid_missing_blank.workflow.yaml"),
        batch_id="DNA_QUANT_BAD_BLANK",
    )

    assert response.task is AgentTask.VALIDATE_BATCH
    assert "validate_batch" in {call.tool_name for call in response.tool_calls}
    assert "MISSING_PLATE_BLANK" in response.answer


def test_runtime_supplements_sources_for_blocked_csv_policy() -> None:
    runtime = LabFlowAgentRuntime()

    response = runtime.ask(
        "Why won't the CSV export?",
        workflow_yaml=_workflow_text("invalid_rna_norm_requant.workflow.yaml"),
        batch_id="RNA_BATCH_BAD_001",
    )

    document_ids = {source.document_id for source in response.sources}
    assert "janus_csv_worklist_spec.md" in document_ids
    assert "batch_readiness_doctrine.md" in document_ids


def test_runtime_supplements_sources_from_plan_diagnostic_without_rubric() -> None:
    runtime = LabFlowAgentRuntime(model=DiagnosticSourceFamilyModel())

    response = runtime.ask("Can we just guess the missing value and move on?")

    document_ids = {source.document_id for source in response.sources}
    assert "ai_guardrails_policy.md" in document_ids
    assert "batch_readiness_doctrine.md" in document_ids
    assert response.trace is not None
    assert {source.chunk_id for source in response.sources} <= set(response.trace.retrieved_chunk_ids)


def test_runtime_records_sanitized_answer_composer_fallback_diagnostic() -> None:
    runtime = LabFlowAgentRuntime(answer_model=FailingAnswerModel())

    response = runtime.ask("What gates must pass before a batch is robot-ready?")

    assert response.trace is not None
    assert response.trace.answer_composer_fallback is True
    assert response.trace.answer_composer_diagnostic is not None
    assert response.trace.answer_composer_diagnostic.code == "answer_composer_error"
    assert "provider payload" not in response.trace.answer_composer_diagnostic.message


def test_tool_runtime_blocks_non_dry_run_artifact_generation() -> None:
    runtime = AgentToolRuntime()

    executed = runtime.execute_tool_call(
        ToolCallPlan(
            tool_name="generate_janus_csv",
            arguments={
                "plan_id": "examples/configs/not_used.yaml",
                "dry_run": False,
                "approval_token": None,
                "output_dir": None,
            },
            reason="Artifact generation without an explicit mode must be blocked.",
        )
    )

    assert executed.result["status"] == "blocked"
    assert executed.result["audit_event_id"] == executed.audit_event_id
    assert {error["code"] for error in executed.result["errors"]} == {"POLICY_VIOLATION"}


def test_tool_runtime_default_denies_non_read_only_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = AgentToolRuntime()
    monkeypatch.setattr(
        runtime,
        "_tool_definitions",
        {
            "future_commit_tool": {
                "name": "future_commit_tool",
                "description": "Future state-changing tool.",
                "read_only": False,
                "parameters": {},
            }
        },
    )

    executed = runtime.execute_tool_call(
        ToolCallPlan(
            tool_name="future_commit_tool",
            arguments={},
            mode=ToolCallMode.DRY_RUN,
            reason="Unknown future mutation must be denied by default.",
        )
    )

    assert executed.result["status"] == "blocked"
    assert executed.result["audit_event_id"] == executed.audit_event_id
    assert {error["code"] for error in executed.result["errors"]} == {"POLICY_VIOLATION"}
