"""Local-first retrieval over LabFlow knowledge chunks."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import log, sqrt
from typing import Protocol

from labflow_rag.chunking import KnowledgeChunk, chunk_search_text
from labflow_rag.index import RagIndex, tokenize


@dataclass(frozen=True)
class RetrievalFilter:
    """Optional metadata filters for retrieval."""

    document_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class RetrievalResult:
    """A scored retrieval result containing a citation-ready chunk."""

    chunk: KnowledgeChunk
    score: float
    match_terms: tuple[str, ...]
    retrieval_mode: str

    @property
    def chunk_id(self) -> str:
        return self.chunk.chunk_id

    @property
    def document_id(self) -> str:
        return self.chunk.document_id


class Retriever(Protocol):
    """Retriever protocol shared by keyword, vector, and hybrid implementations."""

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilter | None = None,
    ) -> tuple[RetrievalResult, ...]:
        """Return ranked retrieval results."""


class KeywordRetriever:
    """TF-IDF-style keyword retriever using only local corpus statistics."""

    def __init__(self, index: RagIndex) -> None:
        self._index = index

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilter | None = None,
    ) -> tuple[RetrievalResult, ...]:
        query_terms = _expand_query_terms(tokenize(query))
        if not query_terms:
            return ()
        candidates = self._index.chunks_for(
            document_ids=(filters.document_ids if filters is not None else ()),
            tags=(filters.tags if filters is not None else ()),
        )
        results: list[RetrievalResult] = []
        for chunk in candidates:
            term_frequencies = self._index.chunk_term_frequencies.get(chunk.chunk_id, {})
            score, match_terms = self._score_terms(query_terms, term_frequencies)
            if score > 0:
                results.append(
                    RetrievalResult(
                        chunk=chunk,
                        score=score,
                        match_terms=match_terms,
                        retrieval_mode="keyword",
                    )
                )
        return tuple(sorted(results, key=_sort_key)[:top_k])

    def _score_terms(
        self,
        query_terms: tuple[str, ...],
        term_frequencies: dict[str, int],
    ) -> tuple[float, tuple[str, ...]]:
        score = 0.0
        matches: list[str] = []
        corpus_size = max(1, self._index.chunk_count)
        for term in query_terms:
            count = term_frequencies.get(term, 0)
            if count == 0:
                continue
            document_frequency = self._index.document_frequencies.get(term, 0)
            inverse_document_frequency = log((corpus_size + 1) / (document_frequency + 1)) + 1
            score += (1 + log(count)) * inverse_document_frequency
            if term not in matches:
                matches.append(term)
        normalized_score = score / max(1, len(set(query_terms)))
        return normalized_score, tuple(matches)


class VectorBackend(Protocol):
    """Embedding abstraction; implementations must be local-test friendly."""

    dimension: int

    def embed(self, text: str) -> tuple[float, ...]:
        """Embed text into a deterministic vector."""


class DeterministicHashVectorBackend:
    """Deterministic token-hash embedding for local tests and offline demos."""

    def __init__(self, *, dimension: int = 64) -> None:
        if dimension <= 0:
            msg = "Vector dimension must be positive."
            raise ValueError(msg)
        self.dimension = dimension

    def embed(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self.dimension
        for token in tokenize(text):
            digest = sha256(token.encode()).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
        return _normalize(tuple(vector))


class VectorRetriever:
    """Retriever backed by a pluggable local vector backend."""

    def __init__(
        self,
        index: RagIndex,
        *,
        backend: VectorBackend | None = None,
    ) -> None:
        self._index = index
        self._backend = backend or DeterministicHashVectorBackend()
        self._chunk_vectors = {
            chunk.chunk_id: self._backend.embed(chunk_search_text(chunk)) for chunk in index.chunks
        }

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilter | None = None,
    ) -> tuple[RetrievalResult, ...]:
        query_vector = self._backend.embed(query)
        if not any(query_vector):
            return ()
        candidates = self._index.chunks_for(
            document_ids=(filters.document_ids if filters is not None else ()),
            tags=(filters.tags if filters is not None else ()),
        )
        results: list[RetrievalResult] = []
        for chunk in candidates:
            score = _cosine_similarity(query_vector, self._chunk_vectors[chunk.chunk_id])
            if score > 0:
                results.append(
                    RetrievalResult(
                        chunk=chunk,
                        score=score,
                        match_terms=(),
                        retrieval_mode="vector",
                    )
                )
        return tuple(sorted(results, key=_sort_key)[:top_k])


class HybridRetriever:
    """Merge keyword and vector retrieval into one ranked result set."""

    def __init__(
        self,
        index: RagIndex,
        *,
        keyword_weight: float = 0.75,
        vector_weight: float = 0.25,
        vector_backend: VectorBackend | None = None,
    ) -> None:
        self._keyword = KeywordRetriever(index)
        self._vector = VectorRetriever(index, backend=vector_backend)
        self._keyword_weight = keyword_weight
        self._vector_weight = vector_weight

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilter | None = None,
    ) -> tuple[RetrievalResult, ...]:
        candidate_limit = max(top_k * 3, 60)
        keyword_results = self._keyword.retrieve(query, top_k=candidate_limit, filters=filters)
        vector_results = self._vector.retrieve(query, top_k=candidate_limit, filters=filters)
        merged: dict[str, _MergedResult] = {}
        _merge_results(
            merged,
            keyword_results,
            weight=self._keyword_weight,
            max_score=_max_score(keyword_results),
        )
        _merge_results(
            merged,
            vector_results,
            weight=self._vector_weight,
            max_score=_max_score(vector_results),
        )
        _apply_policy_source_boosts(merged, query)
        results = [
            RetrievalResult(
                chunk=entry.chunk,
                score=entry.score,
                match_terms=tuple(sorted(entry.match_terms)),
                retrieval_mode="hybrid",
            )
            for entry in merged.values()
            if entry.score > 0
        ]
        return _diversify_by_document(tuple(sorted(results, key=_sort_key)), top_k=top_k)


@dataclass
class _MergedResult:
    chunk: KnowledgeChunk
    score: float
    match_terms: set[str]


def _merge_results(
    merged: dict[str, _MergedResult],
    results: tuple[RetrievalResult, ...],
    *,
    weight: float,
    max_score: float,
) -> None:
    if max_score <= 0:
        return
    for result in results:
        weighted_score = weight * (result.score / max_score)
        entry = merged.get(result.chunk_id)
        if entry is None:
            merged[result.chunk_id] = _MergedResult(
                chunk=result.chunk,
                score=weighted_score,
                match_terms=set(result.match_terms),
            )
            continue
        entry.score += weighted_score
        entry.match_terms.update(result.match_terms)


def _apply_policy_source_boosts(merged: dict[str, _MergedResult], query: str) -> None:
    """Promote guardrail and exception families for policy-critical questions."""

    terms = set(_expand_query_terms(tokenize(query)))
    for entry in merged.values():
        boost = _policy_source_boost(entry.chunk.document_id, terms)
        if boost <= 0:
            continue
        entry.score += boost
        entry.match_terms.add("policy_source_boost")


def _policy_source_boost(document_id: str, terms: set[str]) -> float:
    boost = 0.0
    missing_fact = (
        {"missing", "concentration"} <= terms
        and bool(terms & {"guess", "infer", "invent", "fill", "absent", "unknown"})
    )
    dry_run_commit = bool(terms & {"dry", "dry-run", "preview"}) and bool(
        terms & {"commit", "approval", "janus", "worklist", "csv"}
    )
    robot_artifact = bool(terms & {"robot", "artifact", "worklist", "janus", "transfer", "transfers"}) and bool(
        terms & {"invalid", "blocked", "readiness", "validation"}
    )
    duplicate = "duplicate" in terms and bool(terms & {"destination", "well", "yaml", "blocked"})
    rna_requant = bool(terms & {"rna", "requant", "re-quant"}) and bool(
        terms & {"downstream", "concentration"}
    )

    if document_id == "ai_guardrails_policy.md":
        if missing_fact:
            boost += 0.55
        if dry_run_commit or robot_artifact:
            boost += 0.25
        if rna_requant:
            boost += 0.45
    if document_id == "exception_handling_manual.md" and (missing_fact or duplicate):
        boost += 0.20
    if document_id == "batch_readiness_doctrine.md" and robot_artifact:
        boost += 0.20
    if document_id == "janus_csv_worklist_spec.md" and dry_run_commit:
        boost += 0.20
    return boost


def _diversify_by_document(
    results: tuple[RetrievalResult, ...],
    *,
    top_k: int,
) -> tuple[RetrievalResult, ...]:
    """Prefer source-document coverage before adding duplicate chunks."""

    if top_k <= 0:
        return ()

    selected: list[RetrievalResult] = []
    selected_chunk_ids: set[str] = set()
    selected_document_ids: set[str] = set()

    for result in results:
        if result.document_id in selected_document_ids:
            continue
        selected.append(result)
        selected_chunk_ids.add(result.chunk_id)
        selected_document_ids.add(result.document_id)
        if len(selected) == top_k:
            return tuple(selected)

    for result in results:
        if result.chunk_id in selected_chunk_ids:
            continue
        selected.append(result)
        selected_chunk_ids.add(result.chunk_id)
        if len(selected) == top_k:
            break

    return tuple(selected)


def _expand_query_terms(query_terms: tuple[str, ...]) -> tuple[str, ...]:
    expanded = list(query_terms)
    term_set = set(query_terms)
    singulars = {
        "batches": "batch",
        "worklists": "worklist",
        "samples": "sample",
        "standards": "standard",
        "blanks": "blank",
        "concentrations": "concentration",
        "artifacts": "artifact",
    }
    for plural, singular in singulars.items():
        if plural in term_set:
            expanded.append(singular)

    if {"below", "transfer", "ul"} <= term_set or {"below", "volume", "ul"} <= term_set:
        expanded.extend(
            [
                "split",
                "workflow",
                "child",
                "parent_child",
                "ancestry",
                "split_required_high_concentration",
            ]
        )
    if (
        "split" in term_set
        or "requant" in term_set
        or {"re", "quant"} <= term_set
        or "downstream" in term_set
    ):
        expanded.extend(["ancestry", "requantified", "downstream_concentration", "sample_id"])
    if {"missing", "concentration"} <= term_set:
        expanded.extend(["missing_concentration", "exceptions", "blocking", "manual_review"])
    if ("janus" in term_set or "worklist" in term_set or "worklists" in term_set) and (
        "invalid" in term_set
        or "batch" in term_set
        or "batches" in term_set
        or "missing" in term_set
        or "generated" in term_set
        or "generating" in term_set
    ):
        expanded.extend(
            [
                "readiness",
                "robot_ready",
                "batch_readiness",
                "validation",
                "janus_blocked_for_invalid_batch",
            ]
        )
    if "agent" in term_set or "assistant" in term_set or "ai" in term_set:
        expanded.extend(["ai_guardrails", "no_invention", "must", "validation"])
    if "round" in term_set or "rounded" in term_set:
        expanded.extend(["split", "workflow", "sample_transfer_below_minimum", "ai_guardrails"])
    if (
        "molar" in term_set
        or "molarity" in term_set
        or "nm" in term_set
        or "pmol" in term_set
        or "fmol" in term_set
    ):
        expanded.extend(
            [
                "unsupported",
                "molarity_excluded",
                "unsupported_concentration_unit",
                "dsl",
                "yaml",
                "ai_guardrails",
            ]
        )
    if "throughput" in term_set and ("validation" in term_set or "gates" in term_set):
        expanded.extend(["batch_readiness", "robot_ready", "readiness", "invalid_batch_block"])

    return tuple(dict.fromkeys(expanded))


def _max_score(results: tuple[RetrievalResult, ...]) -> float:
    if not results:
        return 0.0
    return max(result.score for result in results)


def _sort_key(result: RetrievalResult) -> tuple[float, str]:
    return (-result.score, result.chunk_id)


def _normalize(vector: tuple[float, ...]) -> tuple[float, ...]:
    magnitude = sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector
    return tuple(value / magnitude for value in vector)


def _cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
