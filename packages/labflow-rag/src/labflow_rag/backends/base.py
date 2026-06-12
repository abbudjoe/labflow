"""Backend protocol for local and optional vector retrieval stores."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from labflow_rag.retrieval import RetrievalResult


@dataclass(frozen=True)
class BackendQueryResult:
    """A backend query response with latency and skip metadata."""

    backend_name: str
    results: tuple[RetrievalResult, ...]
    latency_ms: float
    skipped: bool = False
    skip_reason: str | None = None
    metadata: dict[str, str | int | float | bool | None] | None = None


class RetrievalBackend(Protocol):
    """Common backend contract for corpus lifecycle comparisons."""

    backend_name: str

    def query(self, query: str, *, top_k: int = 6) -> BackendQueryResult:
        """Return ranked retrieval results or a skipped result."""
