"""Deterministic Stage 9 planning for LabFlow agent tasks."""

from __future__ import annotations

from labflow_agent.models import AgentPlan, AgentRequest, AgentTask, ModelMetadata, ToolCallPlan

UNSUPPORTED_TERMS = frozenset(
    {
        "weather",
        "sports",
        "recipe",
        "pizza",
        "sourdough",
        "championship",
        "europa",
    }
)


class DeterministicFakeModel:
    """Tiny deterministic model substitute used by tests and local demos."""

    metadata = ModelMetadata(
        model_id="deterministic_fake_planner",
        version="0.1.0",
        provider="labflow-local",
    )

    def plan(self, request: AgentRequest) -> AgentPlan:
        question = request.question.strip()
        terms = _terms(question)

        if terms & UNSUPPORTED_TERMS:
            return AgentPlan(
                task=AgentTask.UNSUPPORTED,
                rationale="Question is outside the LabFlow knowledge domain.",
                retrieval_query=question,
                unsupported_reason="The request is not supported by the LabFlow corpus.",
            )

        if request.diagnostic_code is not None:
            return AgentPlan(
                task=AgentTask.EXPLAIN_DIAGNOSTIC,
                rationale="A diagnostic code was supplied and can be explained deterministically.",
                retrieval_query=f"{question} {request.diagnostic_code}",
                tool_calls=(
                    ToolCallPlan(
                        tool_name="explain_exception_code",
                        arguments={"exception_code": request.diagnostic_code},
                        reason="Explain the concrete diagnostic code using deterministic core metadata.",
                    ),
                ),
            )

        if request.workflow_yaml is not None:
            return AgentPlan(
                task=AgentTask.VALIDATE_BATCH,
                rationale="Concrete workflow YAML was supplied, so deterministic validation is required.",
                retrieval_query=question,
                tool_calls=(
                    ToolCallPlan(
                        tool_name="validate_batch",
                        arguments={
                            "batch_id": request.batch_id,
                            "workflow_yaml": request.workflow_yaml,
                        },
                        reason="Validate supplied workflow data before making any claim about it.",
                    ),
                ),
            )

        if _asks_for_next_action(terms):
            return AgentPlan(
                task=AgentTask.RECOMMEND_SAFE_NEXT_ACTION,
                rationale="The request asks for a safe next action grounded in policy.",
                retrieval_query=question,
            )

        return AgentPlan(
            task=AgentTask.ANSWER_WORKFLOW_QUESTION,
            rationale="The request can be answered from retrieved LabFlow knowledge.",
            retrieval_query=question,
        )


def _asks_for_next_action(terms: set[str]) -> bool:
    return "next" in terms or "recommend" in terms or "should" in terms


def _terms(text: str) -> set[str]:
    normalized = text.casefold().replace("-", " ").replace("_", " ")
    return {term.strip("?:.,;!()[]{}\"'") for term in normalized.split() if term.strip()}
