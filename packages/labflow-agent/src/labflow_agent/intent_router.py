"""Deterministic evidence-intent routing for LabFlow agent plans."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from labflow_agent.answer_model import (
    domain_concepts_for_text,
    source_families_for_profiles,
    source_family_profiles_for_context,
)
from labflow_agent.models import (
    AgentPlan,
    AgentRequest,
    AgentTask,
    PlanDiagnostic,
    ToolCallMode,
    ToolCallPlan,
)


class EvidenceIntent(StrEnum):
    """Stable evidence families selected from intent plus trusted context."""

    KNOWLEDGE_ONLY = "knowledge_only"
    WORKFLOW_VALIDATE_BATCH = "workflow_validate_batch"
    DIAGNOSTIC_EXPLAIN = "diagnostic_explain"
    QC_INGEST_ONLY = "qc_ingest_only"
    QC_VALIDATE_PROVENANCE = "qc_validate_provenance"
    QC_EXPLAIN_SAMPLE_FAILURE = "qc_explain_sample_failure"
    QC_LINEAGE_PREVIEW = "qc_lineage_preview"


@dataclass(frozen=True)
class ToolIntentDecision:
    """Routing decision with separated untrusted and trusted inputs."""

    intent: EvidenceIntent
    untrusted_intent_signals: tuple[str, ...]
    trusted_evidence_context: tuple[str, ...]
    retrieval_profiles: tuple[str, ...]
    required_source_families: tuple[str, ...]


_TRUSTED_QC_TOOLS = {
    "ingest_ngs_qc_results",
    "validate_qc_provenance",
    "explain_qc_failure",
    "generate_lab_to_analysis_lineage",
}
_QC_EVIDENCE_INTENTS = {
    EvidenceIntent.QC_INGEST_ONLY,
    EvidenceIntent.QC_VALIDATE_PROVENANCE,
    EvidenceIntent.QC_EXPLAIN_SAMPLE_FAILURE,
    EvidenceIntent.QC_LINEAGE_PREVIEW,
}
_TRUSTED_TOOL_ALLOWLIST = frozenset(
    {
        *_TRUSTED_QC_TOOLS,
        "validate_batch",
        "explain_exception_code",
    }
)


def decide_tool_intent(request: AgentRequest, retrieval_query: str = "") -> ToolIntentDecision:
    """Classify the evidence need without using eval metadata."""

    question = request.question
    haystack = f"{question} {retrieval_query}"
    concepts = set(domain_concepts_for_text(haystack))
    profiles = source_family_profiles_for_context(
        question=question,
        retrieval_query=retrieval_query,
        tool_text="",
    )
    trusted = _trusted_context_fields(request)
    signals = tuple(sorted(concepts))

    if request.workflow_yaml is not None:
        intent = EvidenceIntent.WORKFLOW_VALIDATE_BATCH
    elif request.diagnostic_code is not None:
        intent = EvidenceIntent.DIAGNOSTIC_EXPLAIN
    elif request.qc_csv is not None and request.sample_id is not None and _asks_for_qc_failure_explanation(question):
        intent = EvidenceIntent.QC_EXPLAIN_SAMPLE_FAILURE
    elif request.qc_csv is not None and request.lineage_csv is not None and _asks_for_lineage_preview(question):
        intent = EvidenceIntent.QC_LINEAGE_PREVIEW
    elif request.qc_csv is not None and request.lineage_csv is not None:
        intent = EvidenceIntent.QC_VALIDATE_PROVENANCE
    elif request.qc_csv is not None and _asks_for_qc_ingest(question):
        intent = EvidenceIntent.QC_INGEST_ONLY
    else:
        intent = EvidenceIntent.KNOWLEDGE_ONLY

    if intent in {
        EvidenceIntent.QC_INGEST_ONLY,
        EvidenceIntent.QC_VALIDATE_PROVENANCE,
        EvidenceIntent.QC_EXPLAIN_SAMPLE_FAILURE,
        EvidenceIntent.QC_LINEAGE_PREVIEW,
    }:
        profiles = tuple(dict.fromkeys((*profiles, "downstream_qc")))
        if intent is EvidenceIntent.QC_LINEAGE_PREVIEW:
            profiles = tuple(dict.fromkeys((*profiles, "lab_to_analysis_lineage")))

    return ToolIntentDecision(
        intent=intent,
        untrusted_intent_signals=signals,
        trusted_evidence_context=trusted,
        retrieval_profiles=profiles,
        required_source_families=source_families_for_profiles(profiles),
    )


def base_plan_for_request(request: AgentRequest) -> AgentPlan | None:
    """Return a deterministic plan when trusted context requires a tool."""

    decision = decide_tool_intent(request)
    calls = tool_calls_for_intent(decision.intent, request)
    if not calls:
        return None
    return AgentPlan(
        task=_task_for_intent(decision.intent),
        rationale=_rationale_for_intent(decision.intent),
        retrieval_query=_retrieval_query_for_decision(request, decision),
        tool_calls=calls,
        diagnostic=_overlay_diagnostic(
            decision,
            action="deterministic_base_plan",
            repaired_tools=tuple(call.tool_name for call in calls),
        ),
    )


def apply_tool_intent_overlay(plan: AgentPlan, request: AgentRequest) -> AgentPlan:
    """Bind trusted tool arguments and add mandatory deterministic evidence tools."""

    decision = decide_tool_intent(request, plan.retrieval_query)
    required_calls = tool_calls_for_intent(decision.intent, request)
    allowed_tool_names = {call.tool_name for call in required_calls}
    bound_calls: list[ToolCallPlan] = []
    rejected_tools: list[str] = []
    repaired_tools: list[str] = []

    for call in plan.tool_calls:
        if call.tool_name not in _TRUSTED_TOOL_ALLOWLIST:
            rejected_tools.append(call.tool_name)
            continue
        if call.tool_name in _TRUSTED_QC_TOOLS and decision.intent not in _QC_EVIDENCE_INTENTS:
            rejected_tools.append(call.tool_name)
            continue
        if (
            allowed_tool_names
            and call.tool_name in _TRUSTED_QC_TOOLS
            and call.tool_name not in allowed_tool_names
        ):
            rejected_tools.append(call.tool_name)
            continue
        if call.tool_name in _TRUSTED_TOOL_ALLOWLIST:
            bound = bind_trusted_tool_call(call, request)
            if bound is None:
                rejected_tools.append(call.tool_name)
                continue
            bound_calls.append(bound)

    bound_tool_names = {call.tool_name for call in bound_calls}
    for required_call in required_calls:
        if required_call.tool_name not in bound_tool_names:
            bound_calls.append(required_call)
            bound_tool_names.add(required_call.tool_name)
            repaired_tools.append(required_call.tool_name)

    update: dict[str, Any] = {
        "tool_calls": tuple(bound_calls),
    }
    if required_calls:
        update.update(
            {
                "task": _task_for_intent(decision.intent),
                "rationale": _rationale_for_intent(decision.intent),
                "retrieval_query": _retrieval_query_for_decision(request, decision),
                "unsupported_reason": None,
            }
        )
    if not rejected_tools and not repaired_tools:
        if not required_calls:
            return plan.model_copy(update=update)
        expected_task = _task_for_intent(decision.intent)
        expected_query = _retrieval_query_for_decision(request, decision)
        if plan.task is expected_task and plan.retrieval_query == expected_query:
            return plan.model_copy(update=update)
        update["diagnostic"] = _overlay_diagnostic(
            decision,
            action="normalized_trusted_tool_intent",
            previous=plan.diagnostic,
        )
        return plan.model_copy(update=update)

    update["diagnostic"] = _overlay_diagnostic(
        decision,
        action="repaired_or_rebound_tool_intents",
        repaired_tools=tuple(repaired_tools),
        rejected_tools=tuple(rejected_tools),
        previous=plan.diagnostic,
    )
    return plan.model_copy(
        update=update
    )


def bind_trusted_tool_call(call: ToolCallPlan, request: AgentRequest) -> ToolCallPlan | None:
    """Return a server-bound tool call or None when trusted context is absent/unsafe."""

    if call.tool_name == "validate_batch":
        if request.workflow_yaml is None:
            return None
        return ToolCallPlan(
            tool_name="validate_batch",
            arguments={"batch_id": request.batch_id, "workflow_yaml": request.workflow_yaml},
            mode=ToolCallMode.READ_ONLY,
            reason=call.reason,
        )
    if call.tool_name == "explain_exception_code":
        if request.diagnostic_code is None:
            return None
        return ToolCallPlan(
            tool_name="explain_exception_code",
            arguments={"exception_code": request.diagnostic_code},
            mode=ToolCallMode.READ_ONLY,
            reason=call.reason,
        )
    if call.tool_name == "ingest_ngs_qc_results":
        if request.qc_csv is None:
            return None
        return ToolCallPlan(
            tool_name="ingest_ngs_qc_results",
            arguments={"qc_csv": request.qc_csv},
            mode=ToolCallMode.READ_ONLY,
            reason=call.reason,
        )
    if call.tool_name == "validate_qc_provenance":
        if request.qc_csv is None or request.lineage_csv is None:
            return None
        return ToolCallPlan(
            tool_name="validate_qc_provenance",
            arguments={"qc_csv": request.qc_csv, "lineage_csv": request.lineage_csv},
            mode=ToolCallMode.READ_ONLY,
            reason=call.reason,
        )
    if call.tool_name == "explain_qc_failure":
        if request.qc_csv is None or request.sample_id is None:
            return None
        return ToolCallPlan(
            tool_name="explain_qc_failure",
            arguments={
                "qc_csv": request.qc_csv,
                "lineage_csv": request.lineage_csv,
                "sample_id": request.sample_id,
            },
            mode=ToolCallMode.READ_ONLY,
            reason=call.reason,
        )
    if call.tool_name == "generate_lab_to_analysis_lineage":
        if request.qc_csv is None or request.lineage_csv is None:
            return None
        return ToolCallPlan(
            tool_name="generate_lab_to_analysis_lineage",
            arguments={
                "qc_csv": request.qc_csv,
                "lineage_csv": request.lineage_csv,
                "dry_run": True,
            },
            mode=ToolCallMode.DRY_RUN,
            reason=call.reason,
        )
    return None


def tool_call_for_intent(intent: EvidenceIntent, request: AgentRequest) -> ToolCallPlan | None:
    """Build the mandatory trusted tool call for an evidence intent."""

    calls = tool_calls_for_intent(intent, request)
    return calls[-1] if calls else None


def tool_calls_for_intent(intent: EvidenceIntent, request: AgentRequest) -> tuple[ToolCallPlan, ...]:
    """Build mandatory trusted tool calls for an evidence intent."""

    if intent is EvidenceIntent.WORKFLOW_VALIDATE_BATCH and request.workflow_yaml is not None:
        return (
            ToolCallPlan(
                tool_name="validate_batch",
                arguments={"batch_id": request.batch_id, "workflow_yaml": request.workflow_yaml},
                mode=ToolCallMode.READ_ONLY,
                reason="Validate supplied workflow data before making any claim about it.",
            ),
        )
    if intent is EvidenceIntent.DIAGNOSTIC_EXPLAIN and request.diagnostic_code is not None:
        return (
            ToolCallPlan(
                tool_name="explain_exception_code",
                arguments={"exception_code": request.diagnostic_code},
                mode=ToolCallMode.READ_ONLY,
                reason="Explain the concrete diagnostic code using deterministic core metadata.",
            ),
        )
    if intent is EvidenceIntent.QC_INGEST_ONLY and request.qc_csv is not None:
        return (
            ToolCallPlan(
                tool_name="ingest_ngs_qc_results",
                arguments={"qc_csv": request.qc_csv},
                mode=ToolCallMode.READ_ONLY,
                reason="Parse and threshold the supplied synthetic downstream QC summary metrics.",
            ),
        )
    if (
        intent is EvidenceIntent.QC_VALIDATE_PROVENANCE
        and request.qc_csv is not None
        and request.lineage_csv is not None
    ):
        return (
            ToolCallPlan(
                tool_name="validate_qc_provenance",
                arguments={"qc_csv": request.qc_csv, "lineage_csv": request.lineage_csv},
                mode=ToolCallMode.READ_ONLY,
                reason="Validate QC provenance before answering about downstream analysis linkage.",
            ),
        )
    if (
        intent is EvidenceIntent.QC_EXPLAIN_SAMPLE_FAILURE
        and request.qc_csv is not None
        and request.sample_id is not None
    ):
        calls: list[ToolCallPlan] = []
        if request.lineage_csv is not None:
            calls.extend(tool_calls_for_intent(EvidenceIntent.QC_VALIDATE_PROVENANCE, request))
        calls.append(
            ToolCallPlan(
                tool_name="explain_qc_failure",
                arguments={
                    "qc_csv": request.qc_csv,
                    "lineage_csv": request.lineage_csv,
                    "sample_id": request.sample_id,
                },
                mode=ToolCallMode.READ_ONLY,
                reason="Explain observed QC metrics and provenance without inferring root cause.",
            )
        )
        return tuple(calls)
    if (
        intent is EvidenceIntent.QC_LINEAGE_PREVIEW
        and request.qc_csv is not None
        and request.lineage_csv is not None
    ):
        return (
            *tool_calls_for_intent(EvidenceIntent.QC_VALIDATE_PROVENANCE, request),
            ToolCallPlan(
                tool_name="generate_lab_to_analysis_lineage",
                arguments={
                    "qc_csv": request.qc_csv,
                    "lineage_csv": request.lineage_csv,
                    "dry_run": True,
                },
                mode=ToolCallMode.DRY_RUN,
                reason="Preview lab-to-analysis lineage as a dry-run artifact only.",
            ),
        )
    return ()


def _trusted_context_fields(request: AgentRequest) -> tuple[str, ...]:
    fields: list[str] = []
    for name in (
        "workflow_yaml",
        "batch_id",
        "diagnostic_code",
        "qc_csv",
        "lineage_csv",
        "sample_id",
    ):
        if getattr(request, name) is not None:
            fields.append(name)
    return tuple(fields)


def _task_for_intent(intent: EvidenceIntent) -> AgentTask:
    if intent is EvidenceIntent.WORKFLOW_VALIDATE_BATCH:
        return AgentTask.VALIDATE_BATCH
    if intent is EvidenceIntent.DIAGNOSTIC_EXPLAIN:
        return AgentTask.EXPLAIN_DIAGNOSTIC
    if intent is EvidenceIntent.QC_EXPLAIN_SAMPLE_FAILURE:
        return AgentTask.EXPLAIN_QC_FAILURE
    return AgentTask.ANSWER_WORKFLOW_QUESTION


def _rationale_for_intent(intent: EvidenceIntent) -> str:
    return {
        EvidenceIntent.WORKFLOW_VALIDATE_BATCH: "Trusted workflow YAML was supplied, so deterministic validation is required.",
        EvidenceIntent.DIAGNOSTIC_EXPLAIN: "A trusted diagnostic code was supplied and can be explained deterministically.",
        EvidenceIntent.QC_INGEST_ONLY: "Trusted downstream QC CSV was supplied, so deterministic QC ingestion is required.",
        EvidenceIntent.QC_VALIDATE_PROVENANCE: "Trusted downstream QC and lineage manifests were supplied, so deterministic provenance validation is required.",
        EvidenceIntent.QC_EXPLAIN_SAMPLE_FAILURE: "Trusted downstream QC sample context was supplied, so deterministic QC explanation is required.",
        EvidenceIntent.QC_LINEAGE_PREVIEW: "Trusted QC and lineage context was supplied, so a dry-run lineage preview can be generated.",
        EvidenceIntent.KNOWLEDGE_ONLY: "The request can be answered from retrieved LabFlow knowledge.",
    }[intent]


def _retrieval_query_for_decision(request: AgentRequest, decision: ToolIntentDecision) -> str:
    terms = " ".join(decision.required_source_families)
    if decision.intent in {
        EvidenceIntent.QC_INGEST_ONLY,
        EvidenceIntent.QC_VALIDATE_PROVENANCE,
        EvidenceIntent.QC_EXPLAIN_SAMPLE_FAILURE,
        EvidenceIntent.QC_LINEAGE_PREVIEW,
    }:
        terms = f"downstream QC provenance lineage no causal inference {terms}"
    if decision.intent is EvidenceIntent.QC_LINEAGE_PREVIEW:
        terms = f"lab-to-analysis lineage report preview {terms}"
    return f"{request.question} {terms}".strip()


def _overlay_diagnostic(
    decision: ToolIntentDecision,
    *,
    action: str,
    repaired_tools: tuple[str, ...] = (),
    rejected_tools: tuple[str, ...] = (),
    previous: PlanDiagnostic | None = None,
) -> PlanDiagnostic:
    details: dict[str, str | int | float | bool | None] = {
        "intent": decision.intent.value,
        "overlay_action": action,
        "trusted_evidence_context": ",".join(decision.trusted_evidence_context),
        "untrusted_intent_signals": ",".join(decision.untrusted_intent_signals),
        "required_source_families": ",".join(decision.required_source_families),
        "repaired_tools": ",".join(repaired_tools),
        "rejected_tools": ",".join(rejected_tools),
    }
    if previous is not None:
        details["previous_diagnostic_code"] = previous.code
    return PlanDiagnostic(
        code="deterministic_tool_intent_overlay",
        message="Deterministic trusted-context tool intent overlay was applied.",
        details=details,
    )


def _asks_for_lineage_preview(text: str) -> bool:
    concepts = set(domain_concepts_for_text(text))
    lowered = text.casefold()
    has_lineage_signal = "lineage" in concepts or "lab-to-analysis" in lowered
    has_lab_to_analysis_bundle = (
        any(term in lowered for term in ("quant", "quantification"))
        and any(term in lowered for term in ("normalization", "norm"))
        and any(term in lowered for term in ("re-quant", "requant", "re quant"))
        and any(term in lowered for term in ("qc", "downstream"))
    )
    if not has_lineage_signal and not has_lab_to_analysis_bundle:
        return False
    if any(
        term in lowered
        for term in (
            "check",
            "match",
            "validate",
            "missing",
            "unmatched",
            "manual review",
            "duplicate",
            "no downstream qc",
            "ignore",
        )
    ) and not any(term in lowered for term in ("report", "preview", "generate")):
        return False
    return any(
        term in lowered for term in ("report", "generate", "preview", "connect")
    )


def _asks_for_qc_failure_explanation(text: str) -> bool:
    lowered = text.casefold()
    failure_or_metric_context = any(
        term in lowered
        for term in (
            "fail",
            "failed",
            "failure",
            "downstream qc miss",
            "downstream qc failure",
            "q30",
            "read count",
            "low-read",
            "low read",
            "low-q30",
            "low q30",
        )
    )
    lab_causality_context = any(
        term in lowered
        for term in (
            "root cause",
            "causal",
            "cause",
            "caused",
            "lab step",
            "mess",
            "messed",
        )
    )
    explanatory_prompt = any(term in lowered for term in ("why", "explain", "what can"))
    qc_context = any(term in lowered for term in ("qc", "downstream", "sample"))
    return failure_or_metric_context or lab_causality_context or (
        explanatory_prompt and qc_context
    )


def _asks_for_qc_ingest(text: str) -> bool:
    lowered = text.casefold()
    return any(term in lowered for term in ("ingest", "import", "parse", "read", "load")) and any(
        term in lowered for term in ("qc", "results", "metrics")
    )
