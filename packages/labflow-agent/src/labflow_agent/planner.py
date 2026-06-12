"""Deterministic Stage 9 planning for LabFlow agent tasks."""

from __future__ import annotations

from labflow_agent.models import (
    AgentPlan,
    AgentRequest,
    AgentTask,
    ModelMetadata,
)
from labflow_agent.intent_router import base_plan_for_request

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

        trusted_context_plan = base_plan_for_request(request)
        if trusted_context_plan is not None:
            return trusted_context_plan

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
    return "next" in terms or "recommend" in terms
def _terms(text: str) -> set[str]:
    normalized = text.casefold().replace("-", " ").replace("_", " ")
    return {term.strip("?:.,;!()[]{}\"'") for term in normalized.split() if term.strip()}
