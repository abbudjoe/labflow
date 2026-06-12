"""Controlled LabFlow agent runtime."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from labflow_agent.answer_composer import AnswerComposer
from labflow_agent.answer_model import (
    AnswerModelAdapter,
    GroundedAnswerContext,
    GroundedAnswerDraft,
    GroundedAnswerDraftValidation,
    GroundedAnswerDraftValidator,
    build_grounded_answer_context,
    source_families_for_profiles,
    source_family_profiles_for_context,
)
from labflow_agent.model_factory import answer_model_from_env, model_from_env
from labflow_agent.intent_router import apply_tool_intent_overlay, decide_tool_intent
from labflow_agent.models import (
    AgentPlan,
    AgentRequest,
    AgentResponse,
    AgentTask,
    ExecutedToolCall,
    ModelAdapter,
    ModelExecutionMetadata,
    ModelExecutionMetadataProvider,
    PlanDiagnostic,
    SourceChunk,
)
from labflow_agent.openrouter import OpenRouterError
from labflow_agent.prompts import PromptMetadata, PromptRegistry
from labflow_agent.tracing import TraceTimer, create_agent_trace, new_request_id
from labflow_agent.tool_runtime import AgentToolRuntime
from labflow_rag import HybridRetriever, RagIndex, answer_query
from labflow_rag.retrieval import Retriever

_ANSWER_MODEL_FROM_ENV = object()


class LabFlowAgentRuntime:
    """Coordinate deterministic planning, RAG retrieval, tools, and composition."""

    def __init__(
        self,
        *,
        corpus_dir: str | Path = "knowledge",
        index: RagIndex | None = None,
        retriever: Retriever | None = None,
        model: ModelAdapter | None = None,
        answer_model: AnswerModelAdapter | None | object = _ANSWER_MODEL_FROM_ENV,
        tool_runtime: AgentToolRuntime | None = None,
        composer: AnswerComposer | None = None,
        draft_validator: GroundedAnswerDraftValidator | None = None,
        prompt_registry: PromptRegistry | None = None,
        top_k: int = 6,
    ) -> None:
        self._index = index or RagIndex.from_corpus(corpus_dir)
        self._retriever = retriever or HybridRetriever(self._index)
        self._model = model or model_from_env()
        self._answer_model = (
            answer_model_from_env()
            if answer_model is _ANSWER_MODEL_FROM_ENV
            else cast(AnswerModelAdapter | None, answer_model)
        )
        self._tool_runtime = tool_runtime or AgentToolRuntime()
        self._composer = composer or AnswerComposer()
        self._draft_validator = draft_validator or GroundedAnswerDraftValidator()
        self._prompt_registry = prompt_registry or PromptRegistry()
        self._top_k = top_k

    def run(self, request: AgentRequest) -> AgentResponse:
        timer = TraceTimer()
        request_id = new_request_id()
        plan = apply_tool_intent_overlay(self._model.plan(request), request)
        intent_decision = decide_tool_intent(request, plan.retrieval_query)
        plan = _with_routed_retrieval_query(plan, request.question, intent_decision.required_source_families)
        model_execution = _last_model_execution_metadata(self._model)
        rag_answer = answer_query(
            plan.retrieval_query,
            self._index,
            retriever=self._retriever,
            top_k=self._top_k,
            minimum_supported_score=0.25,
        )
        plan = _with_required_source_diagnostic(
            plan,
            required_source_families=intent_decision.required_source_families,
            retrieved_source_paths=tuple(citation.source_path for citation in rag_answer.citations),
        )
        tool_calls = self._tool_runtime.execute_plan(plan.tool_calls)
        response = self._composer.compose(
            plan=plan,
            rag_answer=rag_answer,
            tool_calls=tool_calls,
        )
        response = _with_supplemented_sources(
            response=response,
            question=request.question,
            plan=plan,
            tool_calls=tool_calls,
            retriever=self._retriever,
            required_source_families=intent_decision.required_source_families,
        )
        answer_composer_diagnostic: PlanDiagnostic | None = None
        answer_composer_execution: ModelExecutionMetadata | None = None
        answer_composer_fallback = False
        answer_composer_final_answer_source = "deterministic_baseline"
        if self._answer_model is not None and not response.unsupported:
            context = build_grounded_answer_context(
                question=request.question,
                plan=plan,
                rag_answer=rag_answer,
                source_chunks=response.sources,
                source_text_by_id=self._source_text_by_id(response.sources),
                tool_calls=tool_calls,
                baseline_response=response,
                has_workflow_yaml=request.workflow_yaml is not None,
                has_batch_id=request.batch_id is not None,
                has_diagnostic_code=request.diagnostic_code is not None,
                batch_id=request.batch_id,
            )
            try:
                draft = self._answer_model.draft(context)
                answer_composer_execution = _last_model_execution_metadata(self._answer_model)
                response, validation = self._draft_validator.apply(context, draft)
                if not validation.accepted:
                    response, validation, answer_composer_final_answer_source = (
                        self._repair_or_fallback_answer(context, draft, validation)
                    )
                    answer_composer_execution = (
                        _last_model_execution_metadata(self._answer_model)
                        or answer_composer_execution
                    )
                    answer_composer_fallback = not validation.accepted
                    answer_composer_diagnostic = _answer_composer_lifecycle_diagnostic(
                        provider=self._answer_model.metadata.provider,
                        final_answer_source=answer_composer_final_answer_source,
                        validation=validation,
                    )
                else:
                    answer_composer_final_answer_source = "live_draft_accepted"
                    answer_composer_diagnostic = PlanDiagnostic(
                        code="answer_composer_draft_accepted",
                        message="Answer composer draft passed deterministic validation.",
                        provider=self._answer_model.metadata.provider,
                    )
            except OpenRouterError as exc:
                answer_composer_execution = _last_model_execution_metadata(self._answer_model)
                answer_composer_fallback = True
                answer_composer_final_answer_source = "deterministic_fallback"
                answer_composer_diagnostic = exc.to_diagnostic().model_copy(
                    update={"provider": self._answer_model.metadata.provider}
                )
            except Exception as exc:
                answer_composer_execution = _last_model_execution_metadata(self._answer_model)
                answer_composer_fallback = True
                answer_composer_final_answer_source = "deterministic_fallback"
                answer_composer_diagnostic = PlanDiagnostic(
                    code="answer_composer_error",
                    message=f"Answer composer failed closed ({type(exc).__name__}).",
                    provider=self._answer_model.metadata.provider,
                )
        trace = create_agent_trace(
            request_id=request_id,
            prompt=self._prompt_for_plan(plan.task),
            model=self._model.metadata,
            retrieved_chunk_ids=_trace_retrieved_chunk_ids(rag_answer.retrieved_chunk_ids, response),
            tool_calls=tool_calls,
            latency_ms=timer.elapsed_ms(),
            outcome_status=_outcome_status(tool_calls, response.unsupported or rag_answer.unsupported),
            model_diagnostic=plan.diagnostic,
            answer_composer_diagnostic=answer_composer_diagnostic,
            model_execution=model_execution,
            answer_composer_execution=answer_composer_execution,
            answer_composer_fallback=answer_composer_fallback,
            answer_composer_final_answer_source=answer_composer_final_answer_source,
        )
        return response.model_copy(update={"trace": trace})

    def _repair_or_fallback_answer(
        self,
        context: GroundedAnswerContext,
        rejected_draft: GroundedAnswerDraft,
        rejected_validation: GroundedAnswerDraftValidation,
    ) -> tuple[AgentResponse, GroundedAnswerDraftValidation, str]:
        repair = getattr(self._answer_model, "repair", None)
        if not callable(repair):
            response, _ = self._draft_validator.apply(context, rejected_draft)
            return response, rejected_validation, "deterministic_fallback"
        try:
            repaired_draft = repair(
                context,
                rejected_draft=rejected_draft,
                validation_reasons=rejected_validation.reasons,
            )
            repaired_response, repaired_validation = self._draft_validator.apply(
                context,
                repaired_draft,
            )
        except OpenRouterError:
            raise
        except Exception:
            response, _ = self._draft_validator.apply(context, rejected_draft)
            return response, rejected_validation, "deterministic_fallback"
        if repaired_validation.accepted:
            return repaired_response, repaired_validation, "live_draft_repaired"
        response, _ = self._draft_validator.apply(context, rejected_draft)
        return response, repaired_validation, "deterministic_fallback"

    def _source_text_by_id(self, sources: tuple[SourceChunk, ...]) -> dict[str, str]:
        wanted = {source.chunk_id for source in sources}
        return {chunk.chunk_id: chunk.text for chunk in self._index.chunks if chunk.chunk_id in wanted}

    def _prompt_for_plan(self, task: AgentTask) -> PromptMetadata:
        if task is AgentTask.EXPLAIN_DIAGNOSTIC:
            return self._prompt_registry.get("diagnostic_explainer")
        if task is AgentTask.ANSWER_WORKFLOW_QUESTION:
            return self._prompt_registry.get("rag_answer")
        return self._prompt_registry.get("agent_planner")

    def ask(
        self,
        question: str,
        *,
        workflow_yaml: str | None = None,
        batch_id: str | None = None,
        diagnostic_code: str | None = None,
        qc_csv: str | None = None,
        lineage_csv: str | None = None,
        sample_id: str | None = None,
    ) -> AgentResponse:
        return self.run(
            AgentRequest(
                question=question,
                workflow_yaml=workflow_yaml,
                batch_id=batch_id,
                diagnostic_code=diagnostic_code,
                qc_csv=qc_csv,
                lineage_csv=lineage_csv,
                sample_id=sample_id,
            )
        )


def _outcome_status(tool_calls: tuple[ExecutedToolCall, ...], unsupported: bool) -> str:
    if unsupported:
        return "unsupported"
    statuses = {
        str(call.result.get("status"))
        for call in tool_calls
        if call.result.get("status") is not None
    }
    if {"blocked", "invalid", "error"} & statuses:
        return "blocked"
    return "ok"


def _last_model_execution_metadata(model: object) -> ModelExecutionMetadata | None:
    provider = cast(ModelExecutionMetadataProvider | None, model)
    last_metadata = getattr(provider, "last_execution_metadata", None)
    if not callable(last_metadata):
        return None
    return cast(ModelExecutionMetadata | None, last_metadata())


def _with_routed_retrieval_query(
    plan: AgentPlan,
    question: str,
    required_source_families: tuple[str, ...],
) -> AgentPlan:
    if not required_source_families:
        return plan
    existing = str(getattr(plan, "retrieval_query", ""))
    family_terms = " ".join(required_source_families)
    routed_query = f"{question} {existing} {family_terms}".strip()
    if routed_query == existing:
        return plan
    return plan.model_copy(update={"retrieval_query": routed_query})


def _with_required_source_diagnostic(
    plan: AgentPlan,
    *,
    required_source_families: tuple[str, ...],
    retrieved_source_paths: tuple[str, ...],
) -> AgentPlan:
    if not required_source_families:
        return plan
    retrieved_paths = " ".join(retrieved_source_paths)
    missing = tuple(family for family in required_source_families if family not in retrieved_paths)
    details: dict[str, str | int | float | bool | None] = {
        "required_source_families": ",".join(required_source_families),
        "initial_missing_source_families": ",".join(missing),
    }
    diagnostic = getattr(plan, "diagnostic", None)
    if diagnostic is not None:
        details.update(diagnostic.details)
        details["required_source_families"] = ",".join(required_source_families)
        details["initial_missing_source_families"] = ",".join(missing)
        code = diagnostic.code
        message = diagnostic.message
        provider = diagnostic.provider
        http_status = diagnostic.http_status
    else:
        code = "required_source_family_routing"
        message = "Required source families were added to retrieval routing."
        provider = None
        http_status = None
    if missing:
        details["missing_source_family_diagnostic"] = "required_source_not_retrieved"
    return plan.model_copy(
        update={
            "diagnostic": PlanDiagnostic(
                code=code,
                message=message,
                provider=provider,
                http_status=http_status,
                details=details,
            )
        }
    )


def _answer_composer_lifecycle_diagnostic(
    *,
    provider: str,
    final_answer_source: str,
    validation: GroundedAnswerDraftValidation,
) -> PlanDiagnostic:
    if final_answer_source == "live_draft_repaired":
        code = "answer_composer_draft_repaired"
        message = "Answer composer draft was repaired once and accepted."
    elif final_answer_source == "deterministic_fallback":
        code = "answer_composer_draft_rejected"
        message = "Answer composer draft was rejected and deterministic fallback was used."
    else:
        code = "answer_composer_draft_accepted"
        message = "Answer composer draft passed deterministic validation."
    return PlanDiagnostic(
        code=code,
        message=message,
        provider=provider,
        details={
            "final_answer_source": final_answer_source,
            "validation_reasons": ",".join(validation.reasons),
            "quality_flags": ",".join(validation.quality_flags),
        },
    )


def _trace_retrieved_chunk_ids(
    rag_chunk_ids: tuple[str, ...],
    response: AgentResponse,
) -> tuple[str, ...]:
    """Return trace-visible retrieval ids after deterministic source supplementation."""

    return tuple(
        dict.fromkeys(
            (
                *rag_chunk_ids,
                *(source.chunk_id for source in response.sources),
            )
        )
    )


def _with_supplemented_sources(
    *,
    response: AgentResponse,
    question: str,
    plan: object,
    tool_calls: tuple[ExecutedToolCall, ...],
    retriever: Retriever,
    required_source_families: tuple[str, ...] = (),
) -> AgentResponse:
    """Supplement response citations from deterministic domain profiles."""

    if response.unsupported:
        return response
    tool_text = " ".join(str(call.result) for call in tool_calls)
    profiles = source_family_profiles_for_context(
        question=question,
        retrieval_query=str(getattr(plan, "retrieval_query", "")),
        tool_text=tool_text,
    )
    families = tuple(
        dict.fromkeys(
            (
                *source_families_for_profiles(profiles),
                *_source_families_from_plan_diagnostic(plan),
                *required_source_families,
            )
        )
    )
    if not families:
        return response
    existing_paths = " ".join(source.source_path for source in response.sources)
    missing = [family for family in families if family not in existing_paths]
    if not missing:
        return response
    sources = list(response.sources)
    seen = {source.chunk_id for source in sources}
    retrieved = retriever.retrieve(f"{question} {getattr(plan, 'retrieval_query', '')}", top_k=24)
    for family in missing:
        for result in retrieved:
            chunk = result.chunk
            if family not in chunk.source_path or chunk.chunk_id in seen:
                continue
            sources.append(
                SourceChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    source_path=chunk.source_path,
                    title=chunk.title,
                    section_path=chunk.section_path,
                )
            )
            seen.add(chunk.chunk_id)
            break
    return response.model_copy(update={"sources": tuple(sources)})


def _source_families_from_plan_diagnostic(plan: object) -> tuple[str, ...]:
    diagnostic = getattr(plan, "diagnostic", None)
    if diagnostic is None:
        return ()
    details = getattr(diagnostic, "details", {})
    raw = details.get("corpus_expansion_source_documents")
    if raw is None:
        return ()
    if isinstance(raw, str):
        return tuple(item.strip() for item in raw.split(",") if item.strip())
    return ()
