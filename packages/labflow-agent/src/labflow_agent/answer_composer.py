"""Grounded response composition for the controlled LabFlow agent."""

from __future__ import annotations

from labflow_agent.answer_model import source_family_profiles_for_context
from labflow_agent.models import (
    AgentPlan,
    AgentResponse,
    AgentTask,
    ExecutedToolCall,
    SourceChunk,
)
from labflow_rag import RagAnswer
from labflow_rag.answering import UNSUPPORTED_RESPONSE


class AnswerComposer:
    """Compose concise grounded answers from RAG and deterministic tool output."""

    def compose(
        self,
        *,
        plan: AgentPlan,
        rag_answer: RagAnswer,
        tool_calls: tuple[ExecutedToolCall, ...],
    ) -> AgentResponse:
        sources = tuple(
            SourceChunk(
                chunk_id=citation.chunk_id,
                document_id=citation.document_id,
                source_path=citation.source_path,
                title=citation.title,
                section_path=citation.section_path,
            )
            for citation in rag_answer.citations
        )

        if plan.task is AgentTask.UNSUPPORTED:
            return AgentResponse(
                answer=UNSUPPORTED_RESPONSE,
                task=AgentTask.UNSUPPORTED,
                plan=plan,
                sources=(),
                tool_calls=tool_calls,
                next_safe_action="Ask a LabFlow workflow, validation, diagnostic, or guardrail question.",
                blocked_reason=plan.unsupported_reason or "No supporting LabFlow source chunks were retrieved.",
                unsupported=True,
            )
        if rag_answer.unsupported and not tool_calls:
            return AgentResponse(
                answer=rag_answer.answer,
                task=AgentTask.UNSUPPORTED,
                plan=plan,
                sources=sources,
                tool_calls=tool_calls,
                next_safe_action="Ask a LabFlow workflow, validation, diagnostic, or guardrail question.",
                blocked_reason="No supporting LabFlow source chunks were retrieved.",
                unsupported=True,
            )

        if plan.task is AgentTask.EXPLAIN_DIAGNOSTIC:
            return self._compose_diagnostic(plan, rag_answer, tool_calls, sources)
        if plan.task is AgentTask.EXPLAIN_QC_FAILURE:
            return self._compose_qc_failure(plan, rag_answer, tool_calls, sources)
        if plan.task is AgentTask.VALIDATE_BATCH:
            return self._compose_validation(plan, rag_answer, tool_calls, sources)
        return self._compose_knowledge_answer(plan, rag_answer, tool_calls, sources)

    def _compose_diagnostic(
        self,
        plan: AgentPlan,
        rag_answer: RagAnswer,
        tool_calls: tuple[ExecutedToolCall, ...],
        sources: tuple[SourceChunk, ...],
    ) -> AgentResponse:
        tool_summary = _tool_error_summary(tool_calls)
        explanation = _artifact_summary(tool_calls)
        answer = " ".join(
            item
            for item in (
                explanation,
                tool_summary,
                _rag_sentence(rag_answer),
            )
            if item
        )
        return AgentResponse(
            answer=answer or _rag_sentence(rag_answer),
            task=plan.task,
            plan=plan,
            sources=sources,
            tool_calls=tool_calls,
            next_safe_action="Resolve the diagnostic with deterministic workflow data, then rerun validation.",
            blocked_reason=_blocked_reason(tool_calls),
        )

    def _compose_validation(
        self,
        plan: AgentPlan,
        rag_answer: RagAnswer,
        tool_calls: tuple[ExecutedToolCall, ...],
        sources: tuple[SourceChunk, ...],
    ) -> AgentResponse:
        error_summary = _tool_error_summary(tool_calls)
        answer_parts = [
            "I checked deterministic LabFlow tool output before making a readiness claim.",
        ]
        if error_summary:
            answer_parts.append(error_summary)
        answer_parts.append(_rag_sentence(rag_answer))
        return AgentResponse(
            answer=" ".join(answer_parts),
            task=plan.task,
            plan=plan,
            sources=sources,
            tool_calls=tool_calls,
            next_safe_action=_next_action_for_tools(tool_calls),
            blocked_reason=_blocked_reason(tool_calls),
        )

    def _compose_qc_failure(
        self,
        plan: AgentPlan,
        rag_answer: RagAnswer,
        tool_calls: tuple[ExecutedToolCall, ...],
        sources: tuple[SourceChunk, ...],
    ) -> AgentResponse:
        answer_parts = [
            "I checked deterministic downstream QC/provenance tool output before explaining this sample.",
            _artifact_summary(tool_calls),
            _tool_error_summary(tool_calls),
            _rag_sentence(rag_answer),
        ]
        return AgentResponse(
            answer=" ".join(part for part in answer_parts if part),
            task=plan.task,
            plan=plan,
            sources=sources,
            tool_calls=tool_calls,
            next_safe_action="Review QC metrics and LabFlow lineage; do not infer lab root cause from QC alone.",
            blocked_reason=_blocked_reason(tool_calls),
        )

    def _compose_knowledge_answer(
        self,
        plan: AgentPlan,
        rag_answer: RagAnswer,
        tool_calls: tuple[ExecutedToolCall, ...],
        sources: tuple[SourceChunk, ...],
    ) -> AgentResponse:
        answer_parts = [_rag_sentence(rag_answer)]
        profile_sentence = _profile_policy_sentence(plan=plan, tool_calls=tool_calls)
        if profile_sentence:
            answer_parts.append(profile_sentence)
        return AgentResponse(
            answer=" ".join(part for part in answer_parts if part),
            task=plan.task,
            plan=plan,
            sources=sources,
            tool_calls=tool_calls,
            next_safe_action="Use deterministic validation before making claims about a concrete batch.",
            blocked_reason=_blocked_reason(tool_calls),
        )


def _rag_sentence(rag_answer: RagAnswer) -> str:
    return rag_answer.answer


def _profile_policy_sentence(
    *,
    plan: AgentPlan,
    tool_calls: tuple[ExecutedToolCall, ...],
) -> str:
    tool_text = " ".join(str(call.result) for call in tool_calls)
    profiles = source_family_profiles_for_context(
        question=plan.retrieval_query,
        retrieval_query=plan.retrieval_query,
        tool_text=tool_text,
    )
    sentences: list[str] = []
    if "missing_lab_fact" in profiles:
        sentences.append(
            "The assistant must not invent or infer missing concentration values; "
            "use measured trusted data and rerun deterministic validation."
        )
    if "invalid_transfers" in profiles:
        sentences.append(
            "Invalid samples are blocked from robot-ready artifacts and generate no transfer rows."
        )
    if "split_workflow" in profiles:
        sentences.append(
            "Below-minimum transfer volume requires split workflow; rounding is not allowed."
        )
    if "dry_run_commit" in profiles:
        sentences.append(
            "A dry-run preview is not a commit; commit requires approval after validation passes."
        )
    if "rna_requant" in profiles:
        sentences.append(
            "The measured RNA re-quant result becomes the downstream concentration for normalization."
        )
    if "downstream_qc" in profiles or "lab_to_analysis_lineage" in profiles:
        sentences.append(
            "Downstream QC can be explained from observed summary metrics and lineage only; "
            "it must not be used to invent a lab root cause."
        )
    return " ".join(sentences)


def _tool_error_summary(tool_calls: tuple[ExecutedToolCall, ...]) -> str:
    errors: list[str] = []
    for call in tool_calls:
        for error in call.result.get("errors", []):
            if isinstance(error, dict):
                code = str(error.get("code", "UNKNOWN_ERROR"))
                message = str(error.get("message", ""))
                errors.append(f"{code}: {message}".strip())
    if not errors:
        return "The deterministic tool calls did not report blocking errors."
    return "Deterministic validation reported: " + "; ".join(errors) + "."


def _artifact_summary(tool_calls: tuple[ExecutedToolCall, ...]) -> str:
    for call in tool_calls:
        for artifact in call.result.get("artifacts", []):
            if isinstance(artifact, dict) and artifact.get("artifact_type") == "exception_explanation":
                data = artifact.get("data", {})
                if isinstance(data, dict):
                    meaning = data.get("meaning")
                    action = data.get("suggested_action")
                    if meaning and action:
                        return f"{meaning} Suggested action: {action}"
            if isinstance(artifact, dict) and artifact.get("artifact_type") == "qc_failure_explanation":
                data = artifact.get("data", {})
                if isinstance(data, dict):
                    interpretation = data.get("safe_interpretation")
                    boundary = data.get("root_cause_boundary")
                    if interpretation and boundary:
                        return f"{interpretation} {boundary}"
    return ""


def _blocked_reason(tool_calls: tuple[ExecutedToolCall, ...]) -> str | None:
    blocking_statuses = {"invalid", "blocked", "error"}
    for call in tool_calls:
        status = call.result.get("status")
        if isinstance(status, str) and status in blocking_statuses:
            return f"{call.tool_name} returned status {status}."
    return None


def _next_action_for_tools(tool_calls: tuple[ExecutedToolCall, ...]) -> str:
    if _blocked_reason(tool_calls):
        return "Fix the reported deterministic errors, then rerun validation before generating artifacts."
    return "Proceed only with deterministic dry-run previews for artifact-generating actions."
