"""Local RAG eval runner."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any

from labflow_rag.answering import UNSUPPORTED_RESPONSE, RagAnswer, answer_query
from labflow_rag.citations import citations_for_results
from labflow_rag.evals.cases import EvalCase, load_golden_cases
from labflow_rag.evals.metrics import CaseEvalResult, EvalMetrics, calculate_metrics
from labflow_rag.index import RagIndex
from labflow_rag.retrieval import HybridRetriever, RetrievalResult, Retriever


@dataclass(frozen=True)
class EvalRunConfig:
    """Configuration for a local RAG eval run."""

    cases_path: str | Path = "evals/golden_questions.yaml"
    corpus_dir: str | Path = "knowledge"
    top_k: int = 6
    retrieval_only: bool = False
    eval_run_id: str | None = None
    prompt_id: str = "rag_answer"
    prompt_version: str = "0.1.0"
    prompt_path: str | Path = "prompts/runtime/rag_answer.md"
    model_id: str = "deterministic_rag_eval"
    model_version: str = "0.1.0"
    baseline_report_path: str | Path | None = None


@dataclass(frozen=True)
class EvalPromptModelMetadata:
    """Prompt/model metadata embedded in an eval report."""

    prompt_id: str
    prompt_version: str
    prompt_sha256: str
    model_id: str
    model_version: str

    def to_json_dict(self) -> dict[str, str]:
        return {
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "prompt_sha256": self.prompt_sha256,
            "model_id": self.model_id,
            "model_version": self.model_version,
        }


@dataclass(frozen=True)
class EvalRunReport:
    """JSON-serializable eval report."""

    eval_run_id: str
    generated_at: str
    cases_path: str
    corpus_dir: str
    top_k: int
    retrieval_only: bool
    metrics: EvalMetrics
    cases: tuple[CaseEvalResult, ...]
    prompt_model: EvalPromptModelMetadata
    baseline_comparison: dict[str, Any]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "eval_run_id": self.eval_run_id,
            "generated_at": self.generated_at,
            "cases_path": self.cases_path,
            "corpus_dir": self.corpus_dir,
            "top_k": self.top_k,
            "retrieval_only": self.retrieval_only,
            "prompt_model": self.prompt_model.to_json_dict(),
            "baseline_comparison": self.baseline_comparison,
            "metrics": self.metrics.to_json_dict(),
            "cases": [case.to_json_dict() for case in self.cases],
        }


def run_eval(
    config: EvalRunConfig | None = None,
    *,
    cases: tuple[EvalCase, ...] | None = None,
    index: RagIndex | None = None,
    retriever: Retriever | None = None,
) -> EvalRunReport:
    """Run a local RAG eval and return a report object."""

    active_config = config or EvalRunConfig()
    active_cases = load_golden_cases(active_config.cases_path) if cases is None else cases
    active_index = index or RagIndex.from_corpus(active_config.corpus_dir)
    active_retriever = retriever or HybridRetriever(active_index)
    case_results = tuple(
        _run_case(
            case,
            active_index,
            active_retriever,
            top_k=active_config.top_k,
            retrieval_only=active_config.retrieval_only,
        )
        for case in active_cases
    )
    now = datetime.now(UTC)
    metrics = calculate_metrics(case_results)
    return EvalRunReport(
        eval_run_id=active_config.eval_run_id or f"eval_{now:%Y%m%dT%H%M%SZ}",
        generated_at=now.isoformat().replace("+00:00", "Z"),
        cases_path=str(active_config.cases_path),
        corpus_dir=str(active_config.corpus_dir),
        top_k=active_config.top_k,
        retrieval_only=active_config.retrieval_only,
        metrics=metrics,
        cases=case_results,
        prompt_model=EvalPromptModelMetadata(
            prompt_id=active_config.prompt_id,
            prompt_version=active_config.prompt_version,
            prompt_sha256=_prompt_hash(active_config.prompt_path),
            model_id=active_config.model_id,
            model_version=active_config.model_version,
        ),
        baseline_comparison=_baseline_comparison(metrics, active_config.baseline_report_path),
    )


def _run_case(
    case: EvalCase,
    index: RagIndex,
    retriever: Retriever,
    *,
    top_k: int,
    retrieval_only: bool,
) -> CaseEvalResult:
    start = perf_counter()
    retrieval_results = retriever.retrieve(case.question, top_k=top_k)
    answer = (
        _retrieval_only_answer(retrieval_results)
        if retrieval_only
        else answer_query(case.question, index, retriever=retriever, top_k=top_k)
    )
    latency_ms = (perf_counter() - start) * 1000

    retrieved_sources = _unique(result.document_id for result in retrieval_results)
    cited_sources = _unique(citation.document_id for citation in answer.citations)
    missing_required_sources = tuple(
        source for source in case.required_sources if source not in retrieved_sources
    )
    missing_required_citations = tuple(
        source for source in case.required_sources if source not in cited_sources
    )
    citation_precision_proxy = _citation_precision(case.required_sources, cited_sources)
    required_answer_matches, missing_answer_terms = _answer_term_matches(
        answer.answer,
        case.expected_answer_contains,
    )
    disallowed_answer_violations = _disallowed_violations(
        answer.answer,
        case.disallowed_answer_contains,
    )
    missing_required_tool_calls = tuple(
        tool for tool in case.required_tool_calls if tool not in answer.tool_call_recommendations
    )

    passed = (
        not missing_required_sources
        and (retrieval_only or citation_precision_proxy > 0)
        and (retrieval_only or not missing_answer_terms)
        and not disallowed_answer_violations
        and (retrieval_only or not missing_required_tool_calls)
    )

    return CaseEvalResult(
        case_id=case.id,
        category=case.category,
        question=case.question,
        passed=passed,
        required_sources=case.required_sources,
        retrieved_sources=retrieved_sources,
        cited_sources=cited_sources,
        missing_required_sources=missing_required_sources,
        missing_required_citations=missing_required_citations,
        retrieval_recall_at_k=_recall(case.required_sources, retrieved_sources),
        citation_precision_proxy=citation_precision_proxy,
        required_answer_matches=required_answer_matches,
        missing_answer_terms=missing_answer_terms,
        answer_contains_match=_recall(case.expected_answer_contains, required_answer_matches),
        disallowed_answer_violations=disallowed_answer_violations,
        unsupported_claim_count=0,
        required_tool_calls=case.required_tool_calls,
        recommended_tool_calls=answer.tool_call_recommendations,
        missing_required_tool_calls=missing_required_tool_calls,
        latency_ms=latency_ms,
        answer=answer.answer,
        retrieved_chunk_ids=answer.retrieved_chunk_ids
        if answer.retrieved_chunk_ids
        else tuple(result.chunk_id for result in retrieval_results),
    )


def _retrieval_only_answer(results: tuple[RetrievalResult, ...]) -> RagAnswer:
    citations = citations_for_results(results)
    return RagAnswer(
        answer=UNSUPPORTED_RESPONSE if not results else "Retrieval-only eval did not compose an answer.",
        citations=citations,
        retrieved_chunk_ids=tuple(result.chunk_id for result in results),
        unsupported=not results,
    )


def _answer_term_matches(answer: str, expected_terms: tuple[str, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    normalized_answer = answer.casefold()
    matches = tuple(term for term in expected_terms if term.casefold() in normalized_answer)
    missing = tuple(term for term in expected_terms if term not in matches)
    return matches, missing


def _disallowed_violations(answer: str, disallowed_terms: tuple[str, ...]) -> tuple[str, ...]:
    normalized_answer = answer.casefold()
    return tuple(term for term in disallowed_terms if term.casefold() in normalized_answer)


def _recall(required: tuple[str, ...], observed: tuple[str, ...]) -> float:
    if not required:
        return 1.0
    return len(set(required) & set(observed)) / len(set(required))


def _citation_precision(required_sources: tuple[str, ...], cited_sources: tuple[str, ...]) -> float:
    if not cited_sources:
        return 0.0 if required_sources else 1.0
    return len(set(required_sources) & set(cited_sources)) / len(set(cited_sources))


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    unique_values: list[str] = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    return tuple(unique_values)


def _prompt_hash(path: str | Path) -> str:
    prompt_path = Path(path)
    if not prompt_path.exists():
        return "sha256:unavailable"
    return f"sha256:{sha256(prompt_path.read_bytes()).hexdigest()}"


def _baseline_comparison(
    metrics: EvalMetrics,
    baseline_report_path: str | Path | None,
) -> dict[str, Any]:
    if baseline_report_path is None:
        return {
            "baseline_report_path": None,
            "baseline_metrics": None,
            "metric_deltas": {},
        }
    path = Path(baseline_report_path)
    if not path.exists():
        return {
            "baseline_report_path": str(path),
            "baseline_metrics": None,
            "metric_deltas": {},
            "note": "Baseline report not found.",
        }
    raw = json.loads(path.read_text())
    baseline_metrics = raw.get("metrics") if isinstance(raw, dict) else None
    if not isinstance(baseline_metrics, dict):
        return {
            "baseline_report_path": str(path),
            "baseline_metrics": None,
            "metric_deltas": {},
            "note": "Baseline report did not contain metrics.",
        }
    current_metrics = metrics.to_json_dict()
    metric_deltas: dict[str, float] = {}
    for key, current_value in current_metrics.items():
        baseline_value = baseline_metrics.get(key)
        if isinstance(current_value, int | float) and isinstance(baseline_value, int | float):
            metric_deltas[key] = float(current_value - baseline_value)
    return {
        "baseline_report_path": str(path),
        "baseline_metrics": baseline_metrics,
        "metric_deltas": metric_deltas,
    }
