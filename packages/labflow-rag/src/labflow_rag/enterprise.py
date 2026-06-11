"""Enterprise-style retrieval diagnostics for fragmented SOP corpora."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from labflow_rag.index import RagIndex, tokenize
from labflow_rag.retrieval import HybridRetriever, RetrievalResult, Retriever


@dataclass(frozen=True)
class RetrievalDebugReport:
    """Reviewer-friendly retrieval debug surface."""

    question: str
    normalized_terms: tuple[str, ...]
    expanded_query_terms: tuple[str, ...]
    source_family_requirements: tuple[str, ...]
    source_family_counts: dict[str, int]
    supplemented_sources: tuple[str, ...]
    missing_required_source_families: tuple[str, ...]
    top_results: tuple[dict[str, Any], ...]
    stale_sources: tuple[str, ...]
    conflicts: tuple[dict[str, Any], ...]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "normalized_terms": list(self.normalized_terms),
            "expanded_query_terms": list(self.expanded_query_terms),
            "source_family_requirements": list(self.source_family_requirements),
            "source_family_counts": dict(self.source_family_counts),
            "supplemented_sources": list(self.supplemented_sources),
            "missing_required_source_families": list(self.missing_required_source_families),
            "top_results": list(self.top_results),
            "stale_sources": list(self.stale_sources),
            "conflicts": list(self.conflicts),
            "source_conflicts": list(self.conflicts),
        }


def retrieval_debug_report(
    question: str,
    index: RagIndex,
    *,
    retriever: Retriever | None = None,
    top_k: int = 8,
) -> RetrievalDebugReport:
    """Return deterministic retrieval diagnostics for portfolio demos."""

    active_retriever = retriever or HybridRetriever(index)
    results = active_retriever.retrieve(question, top_k=top_k)
    stale_sources = _stale_sources(results)
    conflicts = _source_conflicts(results)
    normalized_terms = tuple(dict.fromkeys(tokenize(question)))
    expanded_query_terms = _expanded_query_terms(question, results)
    family_counts = _source_family_counts(results)
    family_requirements = _source_family_requirements(question, results)
    return RetrievalDebugReport(
        question=question,
        normalized_terms=normalized_terms,
        expanded_query_terms=expanded_query_terms,
        source_family_requirements=family_requirements,
        source_family_counts=family_counts,
        supplemented_sources=_supplemented_sources(results, family_requirements),
        missing_required_source_families=_missing_required_source_families(
            family_counts,
            family_requirements,
        ),
        top_results=tuple(_result_debug(result, rank) for rank, result in enumerate(results, start=1)),
        stale_sources=stale_sources,
        conflicts=conflicts,
    )


def conflict_notice_for_results(results: tuple[RetrievalResult, ...]) -> str | None:
    """Return a concise conflict notice when retrieved source families disagree."""

    conflicts = _source_conflicts(results)
    if not conflicts:
        return None
    first = conflicts[0]
    sources = ", ".join(first["sources"])
    return (
        "Conflict detected in retrieved LabFlow sources. "
        f"{first['description']} Resolution: {first['resolution']} "
        f"Sources: {sources}."
    )


def _result_debug(result: RetrievalResult, rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "document_id": result.document_id,
        "chunk_id": result.chunk_id,
        "score": round(result.score, 4),
        "match_terms": list(result.match_terms),
        "tags": list(result.chunk.tags),
        "section_path": list(result.chunk.section_path),
    }


def _stale_sources(results: tuple[RetrievalResult, ...]) -> tuple[str, ...]:
    stale = []
    for result in results:
        text = result.chunk.text.casefold()
        tags = set(result.chunk.tags)
        if "stale_source" in tags or "retired" in tags or "source status: retired" in text:
            stale.append(result.document_id)
    return tuple(dict.fromkeys(stale))


def _expanded_query_terms(question: str, results: tuple[RetrievalResult, ...]) -> tuple[str, ...]:
    terms = list(dict.fromkeys(tokenize(question)))
    for result in results:
        for term in result.match_terms:
            if term not in terms:
                terms.append(term)
    return tuple(terms)


def _source_family_requirements(
    question: str,
    results: tuple[RetrievalResult, ...],
) -> tuple[str, ...]:
    terms = set(tokenize(question))
    tags = {tag for result in results for tag in result.chunk.tags}
    requirements: list[str] = []
    if {"janus", "worklist", "robot", "ready", "readiness"} & terms:
        requirements.extend(("policy", "synthetic_sop"))
    if {"missing", "concentration", "invent", "infer", "estimate"} & terms:
        requirements.extend(("policy", "exception_manual"))
    if {"sop", "legacy", "retired", "conflict"} & terms or "stale_source" in tags:
        requirements.extend(("retired_sop", "policy"))
    if {"workflow", "yaml", "dsl"} & terms:
        requirements.extend(("knowledge_doc", "policy"))
    return tuple(dict.fromkeys(requirements))


def _supplemented_sources(
    results: tuple[RetrievalResult, ...],
    requirements: tuple[str, ...],
) -> tuple[str, ...]:
    if not requirements:
        return ()
    supplemented = []
    for result in results:
        family = _source_family(result)
        if family in requirements and result.document_id not in supplemented:
            supplemented.append(result.document_id)
    return tuple(supplemented)


def _missing_required_source_families(
    counts: dict[str, int],
    requirements: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(family for family in requirements if counts.get(family, 0) == 0)


def _source_family_counts(results: tuple[RetrievalResult, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        family = _source_family(result)
        counts[family] = counts.get(family, 0) + 1
    return dict(sorted(counts.items()))


def _source_family(result: RetrievalResult) -> str:
    tags = set(result.chunk.tags)
    if "stale_source" in tags or "retired" in tags:
        return "retired_sop"
    if "exceptions" in tags or "diagnostics" in tags:
        return "exception_manual"
    if result.document_id.endswith("_policy.md") or "guardrails" in tags:
        return "policy"
    if "controlled_sop" in tags:
        return "controlled_sop"
    if "sop_alignment" in tags:
        return "sop_alignment"
    if result.document_id.endswith("_sop.md"):
        return "synthetic_sop"
    return "knowledge_doc"


def _source_conflicts(results: tuple[RetrievalResult, ...]) -> tuple[dict[str, Any], ...]:
    documents = {result.document_id for result in results}
    tags = {tag for result in results for tag in result.chunk.tags}
    text = "\n".join(result.chunk.text.casefold() for result in results)
    current_sources = [
        result.document_id
        for result in results
        if result.document_id != "legacy_missing_concentration_sop.md"
        and (
            "no_invention" in result.chunk.tags
            or "trusted_concentration_source" in result.chunk.tags
            or "deterministic_validation" in result.chunk.tags
            or "guardrails" in result.chunk.tags
            or "current guardrail" in result.chunk.text.casefold()
            or "manual review" in result.chunk.text.casefold()
        )
    ]
    conflicts: list[dict[str, Any]] = []
    missing_concentration_conflict = (
        "legacy_missing_concentration_sop.md" in documents
        and bool(current_sources)
        and ("estimate a missing stock concentration" in text or "conflict_missing_concentration" in tags)
    )
    if missing_concentration_conflict:
        sources = ["legacy_missing_concentration_sop.md", *dict.fromkeys(current_sources)]
        conflicts.append(
            {
                "conflict_id": "missing_concentration_no_invention",
                "severity": "policy_conflict",
                "description": (
                    "A retired source permits estimating a missing concentration, "
                    "while current guardrail policy requires measured trusted data."
                ),
                "sources": sources,
                "resolution": "Current guardrail policy and deterministic validation take precedence.",
            }
        )
    return tuple(conflicts)
