"""Grounded extractive answer helpers for local LabFlow RAG."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from labflow_rag.citations import Citation, citations_for_results, format_citation
from labflow_rag.conflict_detection import conflict_notice_for_results
from labflow_rag.index import RagIndex, tokenize
from labflow_rag.retrieval import KeywordRetriever, RetrievalResult, Retriever

UNSUPPORTED_RESPONSE = "I do not have enough support in the LabFlow knowledge corpus to answer that."
MINIMUM_SUPPORTED_SCORE = 0.75


@dataclass(frozen=True)
class RagAnswer:
    """A grounded local answer with citations and support status."""

    answer: str
    citations: tuple[Citation, ...]
    retrieved_chunk_ids: tuple[str, ...]
    unsupported: bool
    unsupported_notes: tuple[str, ...] = ()
    tool_call_recommendations: tuple[str, ...] = ()

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "citations": [citation.to_json_dict() for citation in self.citations],
            "retrieved_chunk_ids": list(self.retrieved_chunk_ids),
            "unsupported": self.unsupported,
            "unsupported_notes": list(self.unsupported_notes),
            "tool_call_recommendations": list(self.tool_call_recommendations),
        }


def answer_query(
    query: str,
    index: RagIndex,
    *,
    retriever: Retriever | None = None,
    top_k: int = 4,
    minimum_supported_score: float = MINIMUM_SUPPORTED_SCORE,
) -> RagAnswer:
    """Return an extractive answer or the canonical unsupported response."""

    active_retriever = retriever or KeywordRetriever(index)
    results = active_retriever.retrieve(query, top_k=top_k)
    supported_results = tuple(
        result
        for result in results
        if result.match_terms and result.score >= minimum_supported_score
    )
    if not supported_results:
        return RagAnswer(
            answer=UNSUPPORTED_RESPONSE,
            citations=(),
            retrieved_chunk_ids=(),
            unsupported=True,
            unsupported_notes=("No relevant source chunk was retrieved from the LabFlow corpus.",),
        )

    citations = citations_for_results(supported_results)
    conflict_notice = conflict_notice_for_results(supported_results)
    if conflict_notice is not None:
        return RagAnswer(
            answer=conflict_notice,
            citations=citations,
            retrieved_chunk_ids=tuple(result.chunk_id for result in supported_results),
            unsupported=False,
            unsupported_notes=("Retrieved sources contain a policy-critical conflict.",),
            tool_call_recommendations=_recommend_tools(query),
        )

    snippets = [_extract_snippet(result) for result in supported_results[:2]]
    cited_sources = "; ".join(format_citation(citation) for citation in citations[:2])
    answer = (
        "The LabFlow knowledge corpus supports this from cited sources: "
        f"{' '.join(snippets)} Sources: {cited_sources}."
    )
    return RagAnswer(
        answer=answer,
        citations=citations,
        retrieved_chunk_ids=tuple(result.chunk_id for result in supported_results),
        unsupported=False,
        tool_call_recommendations=_recommend_tools(query),
    )


def _extract_snippet(result: RetrievalResult) -> str:
    sentences = [sentence.strip() for sentence in result.chunk.text.replace("\n", " ").split(".")]
    for sentence in sentences:
        if sentence:
            return f"{sentence}."
    return result.chunk.text.strip()


def _recommend_tools(query: str) -> tuple[str, ...]:
    terms = set(tokenize(query))
    tools: list[str] = []
    if {"ready", "readiness", "janus", "worklist"} & terms:
        tools.append("validate_batch")
    if {"janus", "worklist"} & terms:
        tools.append("generate_janus_csv")
    if {"workflow", "yaml", "dsl"} & terms:
        tools.append("validate_workflow")
    if {"throughput", "batching"} & terms:
        tools.append("compare_throughput")
    if {"qc", "ngs", "analysis", "lineage", "provenance"} & terms:
        tools.append("validate_qc_provenance")
    if {"failure", "failed"} & terms and {"qc", "ngs"} & terms:
        tools.append("explain_qc_failure")
    if {"lineage", "analysis"} & terms:
        tools.append("generate_lab_to_analysis_lineage")
    return tuple(dict.fromkeys(tools))
