"""Optional Pinecone retrieval backend.

This module is safe to import without the Pinecone package installed. Live
network calls are only attempted by scripts that require explicit confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from time import perf_counter

from labflow_rag.backends.base import BackendQueryResult


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
            dimension=int(os.environ.get("PINECONE_DIMENSION", "64") or "64"),
            metric=os.environ.get("PINECONE_METRIC", "cosine"),
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

    def __init__(self, config: PineconeBackendConfig | None = None) -> None:
        self._config = config or PineconeBackendConfig.from_env()

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
        try:
            import pinecone  # type: ignore[import-not-found]
        except ImportError:
            return BackendQueryResult(
                backend_name=self.backend_name,
                results=(),
                latency_ms=(perf_counter() - start) * 1000,
                skipped=True,
                skip_reason="pinecone package is not installed.",
                metadata=self._config.metadata(),
            )
        return BackendQueryResult(
            backend_name=self.backend_name,
            results=(),
            latency_ms=(perf_counter() - start) * 1000,
            skipped=True,
            skip_reason=(
                "Live Pinecone query requires scripts with --confirm-live-pinecone; "
                f"client module detected: {getattr(pinecone, '__name__', 'pinecone')}."
            ),
            metadata=self._config.metadata(),
        )
