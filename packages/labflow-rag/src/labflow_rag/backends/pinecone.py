"""Optional Pinecone retrieval backend.

This module is safe to import without the Pinecone package installed. Live
network query calls require configured Pinecone credentials.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from time import perf_counter
from typing import Any

from labflow_rag.backends.base import BackendQueryResult
from labflow_rag.chunking import KnowledgeChunk
from labflow_rag.index import RagIndex, tokenize
from labflow_rag.retrieval import (
    DeterministicHashVectorBackend,
    HybridRetriever,
    RetrievalResult,
)
from labflow_rag.source_precedence import lifecycle_for_chunk_tags

DEFAULT_PINECONE_DIMENSION = 384
DEFAULT_PINECONE_METRIC = "cosine"


@dataclass(frozen=True)
class PineconeBackendConfig:
    """Environment-backed Pinecone configuration."""

    api_key: str
    index_name: str
    namespace: str
    cloud: str
    region: str
    dimension: int
    metric: str

    @classmethod
    def from_env(cls) -> PineconeBackendConfig:
        return cls(
            api_key=os.environ.get("PINECONE_API_KEY", ""),
            index_name=os.environ.get("PINECONE_INDEX_NAME", ""),
            namespace=os.environ.get("PINECONE_NAMESPACE", "labflow-local"),
            cloud=os.environ.get("PINECONE_CLOUD", "aws"),
            region=os.environ.get("PINECONE_REGION", "us-east-1"),
            dimension=int(
                os.environ.get("PINECONE_DIMENSION", str(DEFAULT_PINECONE_DIMENSION))
                or str(DEFAULT_PINECONE_DIMENSION)
            ),
            metric=os.environ.get("PINECONE_METRIC", DEFAULT_PINECONE_METRIC),
        )

    def missing_reason(self) -> str | None:
        if not self.api_key.strip():
            return "PINECONE_API_KEY is absent."
        if not self.index_name.strip():
            return "PINECONE_INDEX_NAME is absent."
        return None

    def metadata(self) -> dict[str, str | int | float | bool | None]:
        return {
            "index_name": self.index_name,
            "namespace": self.namespace,
            "cloud": self.cloud,
            "region": self.region,
            "dimension": self.dimension,
            "metric": self.metric,
        }


class PineconeBackend:
    """Optional Pinecone query backend."""

    backend_name = "pinecone"

    def __init__(
        self,
        config: PineconeBackendConfig | None = None,
        *,
        index: RagIndex | None = None,
        client: Any | None = None,
        expected_corpus_fingerprint: str | None = None,
        expected_chunker_version: str | None = None,
    ) -> None:
        self._config = config or PineconeBackendConfig.from_env()
        self._index = index
        self._client = client
        self._expected_corpus_fingerprint = expected_corpus_fingerprint
        self._expected_chunker_version = expected_chunker_version
        self._vector_backend = DeterministicHashVectorBackend(dimension=self._config.dimension)
        self._local_hybrid = HybridRetriever(index) if index is not None else None

    def query(self, query: str, *, top_k: int = 6) -> BackendQueryResult:
        start = perf_counter()
        missing = self._config.missing_reason()
        if missing is not None:
            return BackendQueryResult(
                backend_name=self.backend_name,
                results=(),
                latency_ms=(perf_counter() - start) * 1000,
                skipped=True,
                skip_reason=missing,
                metadata=self._config.metadata(),
            )
        if self._index is None:
            return BackendQueryResult(
                backend_name=self.backend_name,
                results=(),
                latency_ms=(perf_counter() - start) * 1000,
                skipped=True,
                skip_reason="PineconeBackend requires a local RagIndex to hydrate citations.",
                metadata=self._config.metadata(),
            )
        try:
            client = self._client or _pinecone_client(self._config.api_key)
        except ImportError:
            return BackendQueryResult(
                backend_name=self.backend_name,
                results=(),
                latency_ms=(perf_counter() - start) * 1000,
                skipped=True,
                skip_reason="pinecone package is not installed.",
                metadata=self._config.metadata(),
            )
        except Exception as exc:
            return BackendQueryResult(
                backend_name=self.backend_name,
                results=(),
                latency_ms=(perf_counter() - start) * 1000,
                skipped=True,
                skip_reason=f"Pinecone client initialization failed ({type(exc).__name__}).",
                metadata=self._config.metadata(),
            )
        query_vector = self._vector_backend.embed(query)
        if not any(query_vector):
            return BackendQueryResult(
                backend_name=self.backend_name,
                results=(),
                latency_ms=(perf_counter() - start) * 1000,
                metadata=self._config.metadata() | {"match_count": 0, "top_k": top_k},
            )
        chunk_by_id = {chunk.chunk_id: chunk for chunk in self._index.chunks}
        try:
            response = client.Index(self._config.index_name).query(
                vector=list(query_vector),
                top_k=max(top_k * 3, 20),
                include_metadata=True,
                namespace=self._config.namespace,
            )
        except Exception as exc:
            return BackendQueryResult(
                backend_name=self.backend_name,
                results=(),
                latency_ms=(perf_counter() - start) * 1000,
                skipped=True,
                skip_reason=f"Pinecone query failed ({type(exc).__name__}).",
                metadata=self._config.metadata(),
            )
        pinecone_results: list[RetrievalResult] = []
        missing_chunk_ids: list[str] = []
        metadata_mismatch_count = 0
        stale_filtered_count = 0
        for match in _matches_from_response(response):
            chunk_id = _match_id(match)
            if not chunk_id:
                continue
            if self._metadata_mismatch(match):
                metadata_mismatch_count += 1
                continue
            chunk = chunk_by_id.get(chunk_id)
            if chunk is None:
                missing_chunk_ids.append(chunk_id)
                continue
            if _chunk_is_stale(chunk):
                stale_filtered_count += 1
                continue
            pinecone_results.append(
                RetrievalResult(
                    chunk=chunk,
                    score=_match_score(match),
                    match_terms=tuple(sorted(set(tokenize(query)) & set(tokenize(chunk.text)))),
                    retrieval_mode="pinecone",
                )
            )
        results = _merge_with_keyword_results(
            query=query,
            top_k=top_k,
            pinecone_results=tuple(pinecone_results),
            local_hybrid_results=(
                self._local_hybrid.retrieve(query, top_k=top_k)
                if self._local_hybrid is not None
                else ()
            ),
        )
        return BackendQueryResult(
            backend_name=self.backend_name,
            results=results,
            latency_ms=(perf_counter() - start) * 1000,
            metadata=self._config.metadata()
            | {
                "match_count": len(pinecone_results),
                "missing_local_chunk_count": len(missing_chunk_ids),
                "metadata_mismatch_count": metadata_mismatch_count,
                "stale_filtered_count": stale_filtered_count,
                "local_hybrid_rerank_enabled": self._local_hybrid is not None,
                "top_k": top_k,
            },
        )

    def _metadata_mismatch(self, match: Any) -> bool:
        metadata = _match_metadata(match)
        if self._expected_corpus_fingerprint is not None:
            if metadata.get("corpus_fingerprint") != self._expected_corpus_fingerprint:
                return True
        if self._expected_chunker_version is not None:
            if metadata.get("chunker_version") != self._expected_chunker_version:
                return True
        return False


def _pinecone_client(api_key: str) -> Any:
    from pinecone import Pinecone  # type: ignore[import-not-found]

    return Pinecone(api_key=api_key)


def _matches_from_response(response: Any) -> tuple[Any, ...]:
    if isinstance(response, dict):
        matches = response.get("matches", ())
    else:
        matches = getattr(response, "matches", ())
    if matches is None:
        return ()
    return tuple(matches)


def _match_id(match: Any) -> str | None:
    if isinstance(match, dict):
        value = match.get("id")
    else:
        value = getattr(match, "id", None)
    return str(value) if isinstance(value, str) and value else None


def _match_score(match: Any) -> float:
    if isinstance(match, dict):
        value = match.get("score", 0.0)
    else:
        value = getattr(match, "score", 0.0)
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _match_metadata(match: Any) -> dict[str, object]:
    if isinstance(match, dict):
        metadata = match.get("metadata", {})
    else:
        metadata = getattr(match, "metadata", {})
    return dict(metadata) if isinstance(metadata, dict) else {}


def _merge_with_keyword_results(
    *,
    query: str,
    top_k: int,
    pinecone_results: tuple[RetrievalResult, ...],
    local_hybrid_results: tuple[RetrievalResult, ...],
) -> tuple[RetrievalResult, ...]:
    merged: dict[str, RetrievalResult] = {}
    scores: dict[str, float] = {}
    for result in pinecone_results:
        merged[result.chunk_id] = result
        scores[result.chunk_id] = max(scores.get(result.chunk_id, 0.0), result.score)
    max_local_score = max((result.score for result in local_hybrid_results), default=0.0)
    query_terms = set(tokenize(query))
    for result in local_hybrid_results:
        normalized_local = result.score / max_local_score if max_local_score > 0 else 0.0
        existing = scores.get(result.chunk_id, 0.0)
        combined_score = existing + 1.25 * normalized_local
        scores[result.chunk_id] = combined_score
        if result.chunk_id not in merged:
            merged[result.chunk_id] = RetrievalResult(
                chunk=result.chunk,
                score=combined_score,
                match_terms=result.match_terms,
                retrieval_mode="pinecone_local_hybrid",
            )
    return tuple(
        RetrievalResult(
            chunk=result.chunk,
            score=scores[result.chunk_id],
            match_terms=(
                result.match_terms
                if result.match_terms
                else tuple(sorted(query_terms & set(tokenize(result.chunk.text))))
            ),
            retrieval_mode=result.retrieval_mode,
        )
        for result in sorted(merged.values(), key=lambda item: (-scores[item.chunk_id], item.chunk_id))[:top_k]
    )


def _chunk_is_stale(chunk: KnowledgeChunk) -> bool:
    lifecycle = lifecycle_for_chunk_tags(
        document_id=chunk.document_id,
        tags=chunk.tags,
        text=chunk.text,
    )
    return lifecycle.stale
