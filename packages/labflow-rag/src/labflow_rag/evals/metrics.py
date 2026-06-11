"""Metrics for LabFlow RAG eval runs."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from statistics import median
from typing import Any


@dataclass(frozen=True)
class CaseEvalResult:
    """Per-case eval result."""

    case_id: str
    category: str
    question: str
    passed: bool
    required_sources: tuple[str, ...]
    retrieved_sources: tuple[str, ...]
    cited_sources: tuple[str, ...]
    missing_required_sources: tuple[str, ...]
    missing_required_citations: tuple[str, ...]
    retrieval_recall_at_k: float
    citation_precision_proxy: float
    required_answer_matches: tuple[str, ...]
    missing_answer_terms: tuple[str, ...]
    answer_contains_match: float
    disallowed_answer_violations: tuple[str, ...]
    unsupported_claim_count: int
    required_tool_calls: tuple[str, ...]
    recommended_tool_calls: tuple[str, ...]
    missing_required_tool_calls: tuple[str, ...]
    latency_ms: float
    answer: str
    retrieved_chunk_ids: tuple[str, ...]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "question": self.question,
            "passed": self.passed,
            "required_sources": list(self.required_sources),
            "retrieved_sources": list(self.retrieved_sources),
            "cited_sources": list(self.cited_sources),
            "missing_required_sources": list(self.missing_required_sources),
            "missing_required_citations": list(self.missing_required_citations),
            "retrieval_recall_at_k": self.retrieval_recall_at_k,
            "citation_precision_proxy": self.citation_precision_proxy,
            "required_answer_matches": list(self.required_answer_matches),
            "missing_answer_terms": list(self.missing_answer_terms),
            "answer_contains_match": self.answer_contains_match,
            "disallowed_answer_violations": list(self.disallowed_answer_violations),
            "unsupported_claim_count": self.unsupported_claim_count,
            "required_tool_calls": list(self.required_tool_calls),
            "recommended_tool_calls": list(self.recommended_tool_calls),
            "missing_required_tool_calls": list(self.missing_required_tool_calls),
            "latency_ms": self.latency_ms,
            "answer": self.answer,
            "retrieved_chunk_ids": list(self.retrieved_chunk_ids),
        }


@dataclass(frozen=True)
class EvalMetrics:
    """Aggregate metrics for an eval run."""

    case_count: int
    passed_count: int
    failed_count: int
    retrieval_recall_at_k: float
    citation_precision_proxy: float
    required_answer_contains_match: float
    disallowed_answer_violations: int
    unsupported_claim_count: int
    tool_call_expectation_match: float
    latency_ms_avg: float
    latency_ms_p50: float
    latency_ms_p95: float

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "case_count": self.case_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "retrieval_recall_at_k": self.retrieval_recall_at_k,
            "citation_precision_proxy": self.citation_precision_proxy,
            "required_answer_contains_match": self.required_answer_contains_match,
            "disallowed_answer_violations": self.disallowed_answer_violations,
            "unsupported_claim_count": self.unsupported_claim_count,
            "tool_call_expectation_match": self.tool_call_expectation_match,
            "latency_ms_avg": self.latency_ms_avg,
            "latency_ms_p50": self.latency_ms_p50,
            "latency_ms_p95": self.latency_ms_p95,
        }


def calculate_metrics(results: tuple[CaseEvalResult, ...]) -> EvalMetrics:
    """Calculate aggregate metrics from per-case results."""

    case_count = len(results)
    if case_count == 0:
        return EvalMetrics(
            case_count=0,
            passed_count=0,
            failed_count=0,
            retrieval_recall_at_k=0.0,
            citation_precision_proxy=0.0,
            required_answer_contains_match=0.0,
            disallowed_answer_violations=0,
            unsupported_claim_count=0,
            tool_call_expectation_match=0.0,
            latency_ms_avg=0.0,
            latency_ms_p50=0.0,
            latency_ms_p95=0.0,
        )

    latencies = tuple(result.latency_ms for result in results)
    return EvalMetrics(
        case_count=case_count,
        passed_count=sum(1 for result in results if result.passed),
        failed_count=sum(1 for result in results if not result.passed),
        retrieval_recall_at_k=_average(result.retrieval_recall_at_k for result in results),
        citation_precision_proxy=_average(result.citation_precision_proxy for result in results),
        required_answer_contains_match=_average(
            result.answer_contains_match for result in results
        ),
        disallowed_answer_violations=sum(
            len(result.disallowed_answer_violations) for result in results
        ),
        unsupported_claim_count=sum(result.unsupported_claim_count for result in results),
        tool_call_expectation_match=_average(_tool_call_match(result) for result in results),
        latency_ms_avg=_average(latencies),
        latency_ms_p50=median(latencies),
        latency_ms_p95=_percentile(latencies, 0.95),
    )


def _average(values: Iterable[float]) -> float:
    materialized = tuple(values)
    if not materialized:
        return 0.0
    return sum(materialized) / len(materialized)


def _tool_call_match(result: CaseEvalResult) -> float:
    if not result.required_tool_calls:
        return 1.0
    matched = len(set(result.required_tool_calls) & set(result.recommended_tool_calls))
    return matched / len(result.required_tool_calls)


def _percentile(values: tuple[float, ...], percentile: float) -> float:
    sorted_values = sorted(values)
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    index = round((len(sorted_values) - 1) * percentile)
    return sorted_values[index]
