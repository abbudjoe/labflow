"""Retriever factory for local and optional hosted backends."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from labflow_rag.backends.base import BackendQueryResult, RetrievalBackend
from labflow_rag.backends.pinecone import PineconeBackend, PineconeBackendConfig
from labflow_rag.corpus_manifest import CHUNKER_VERSION, build_corpus_manifest
from labflow_rag.index import RagIndex
from labflow_rag.retrieval import HybridRetriever, RetrievalFilter, RetrievalResult, Retriever

LOCAL_RAG_BACKEND = "local"
PINECONE_RAG_BACKEND = "pinecone"
SUPPORTED_RAG_BACKENDS = (LOCAL_RAG_BACKEND, PINECONE_RAG_BACKEND)


@dataclass(frozen=True)
class RetrieverBuildResult:
    """Selected retriever plus auditable backend metadata."""

    retriever: Retriever
    backend_name: str
    metadata: dict[str, object]


class BackendRetrieverAdapter:
    """Adapt backend comparison stores to the normal Retriever protocol."""

    def __init__(self, backend: RetrievalBackend) -> None:
        self._backend = backend
        self._query_count = 0
        self._skipped_count = 0
        self._last_query: BackendQueryResult | None = None

    @property
    def backend_name(self) -> str:
        return self._backend.backend_name

    @property
    def query_count(self) -> int:
        return self._query_count

    @property
    def skipped_count(self) -> int:
        return self._skipped_count

    @property
    def last_query(self) -> BackendQueryResult | None:
        return self._last_query

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilter | None = None,
    ) -> tuple[RetrievalResult, ...]:
        result = self._backend.query(query, top_k=top_k)
        self._query_count += 1
        self._last_query = result
        if result.skipped:
            self._skipped_count += 1
            return ()
        if filters is None:
            return result.results
        return _filter_results(result.results, filters)[:top_k]

    def metadata(self) -> dict[str, object]:
        last = self._last_query
        return {
            "backend_name": self.backend_name,
            "query_count": self._query_count,
            "skipped_count": self._skipped_count,
            "last_query_skipped": last.skipped if last is not None else None,
            "last_query_skip_reason": last.skip_reason if last is not None else None,
            "last_query_latency_ms": last.latency_ms if last is not None else None,
            "last_query_metadata": last.metadata if last is not None else None,
        }


def build_retriever_from_env(
    index: RagIndex,
    *,
    corpus_dir: str | Path = "knowledge",
    backend_name: str | None = None,
    confirm_live_pinecone: bool = False,
) -> RetrieverBuildResult:
    """Build the configured RAG retriever.

    Local hybrid retrieval is the default. Pinecone is opt-in because it performs
    hosted network reads and depends on credentials plus a pre-indexed corpus.
    """

    selected = _normalize_backend_name(backend_name or os.environ.get("LABFLOW_RAG_BACKEND", "local"))
    if selected == LOCAL_RAG_BACKEND:
        return RetrieverBuildResult(
            retriever=HybridRetriever(index),
            backend_name=LOCAL_RAG_BACKEND,
            metadata={
                "backend_name": LOCAL_RAG_BACKEND,
                "requested_backend": selected,
                "live": False,
                "implementation": "labflow_rag.retrieval.HybridRetriever",
            },
        )
    if selected != PINECONE_RAG_BACKEND:
        raise ValueError(
            f"Unsupported RAG backend {selected!r}. Expected one of: "
            + ", ".join(SUPPORTED_RAG_BACKENDS)
        )
    if not confirm_live_pinecone:
        raise ValueError(
            "Pinecone retrieval requires --confirm-live-pinecone to document an "
            "explicit live hosted backend run."
        )
    manifest = build_corpus_manifest(corpus_dir)
    config = PineconeBackendConfig.from_env()
    backend = PineconeBackend(
        config,
        index=index,
        expected_corpus_fingerprint=manifest.corpus_fingerprint,
        expected_chunker_version=CHUNKER_VERSION,
    )
    adapter = BackendRetrieverAdapter(backend)
    return RetrieverBuildResult(
        retriever=adapter,
        backend_name=PINECONE_RAG_BACKEND,
        metadata={
            "backend_name": PINECONE_RAG_BACKEND,
            "requested_backend": selected,
            "live": True,
            "implementation": "labflow_rag.backends.pinecone.PineconeBackend",
            "corpus_fingerprint": manifest.corpus_fingerprint,
            "chunker_version": CHUNKER_VERSION,
            "pinecone": config.metadata(),
            "confirm_live_pinecone": True,
        },
    )


def retriever_runtime_metadata(retriever: Retriever, base_metadata: dict[str, object]) -> dict[str, object]:
    """Return static and runtime backend metadata for eval artifacts."""

    payload = dict(base_metadata)
    metadata = getattr(retriever, "metadata", None)
    if callable(metadata):
        payload["runtime"] = metadata()
    return payload


def _normalize_backend_name(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized in {"hybrid", "local_hybrid"}:
        return LOCAL_RAG_BACKEND
    return normalized


def _filter_results(
    results: tuple[RetrievalResult, ...],
    filters: RetrievalFilter,
) -> tuple[RetrievalResult, ...]:
    filtered = results
    if filters.document_ids:
        allowed_documents = set(filters.document_ids)
        filtered = tuple(result for result in filtered if result.document_id in allowed_documents)
    if filters.tags:
        required_tags = set(filters.tags)
        filtered = tuple(
            result for result in filtered if required_tags.issubset(set(result.chunk.tags))
        )
    return filtered
