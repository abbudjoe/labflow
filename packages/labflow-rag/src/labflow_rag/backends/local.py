"""Local deterministic retrieval backend."""

from __future__ import annotations

from time import perf_counter

from labflow_rag.backends.base import BackendQueryResult
from labflow_rag.index import RagIndex
from labflow_rag.retrieval import HybridRetriever


class LocalHybridBackend:
    """Local keyword/vector hybrid backend used by default."""

    backend_name = "local_hybrid"

    def __init__(self, index: RagIndex) -> None:
        self._retriever = HybridRetriever(index)

    def query(self, query: str, *, top_k: int = 6) -> BackendQueryResult:
        start = perf_counter()
        results = self._retriever.retrieve(query, top_k=top_k)
        return BackendQueryResult(
            backend_name=self.backend_name,
            results=results,
            latency_ms=(perf_counter() - start) * 1000,
            metadata={"top_k": top_k},
        )
