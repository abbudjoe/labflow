"""Citation helpers for LabFlow RAG chunks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from labflow_rag.chunking import KnowledgeChunk
from labflow_rag.retrieval import RetrievalResult


@dataclass(frozen=True)
class Citation:
    """Citation metadata for a retrieved chunk."""

    chunk_id: str
    document_id: str
    source_path: str
    title: str
    section_path: tuple[str, ...]
    tags: tuple[str, ...]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_path": self.source_path,
            "title": self.title,
            "section_path": list(self.section_path),
            "tags": list(self.tags),
        }


def citation_for_chunk(chunk: KnowledgeChunk) -> Citation:
    """Create citation metadata for one chunk."""

    return Citation(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        source_path=chunk.source_path,
        title=chunk.title,
        section_path=chunk.section_path,
        tags=chunk.tags,
    )


def citations_for_results(results: tuple[RetrievalResult, ...]) -> tuple[Citation, ...]:
    """Return unique citations in result order."""

    citations: list[Citation] = []
    seen: set[str] = set()
    for result in results:
        if result.chunk_id in seen:
            continue
        citations.append(citation_for_chunk(result.chunk))
        seen.add(result.chunk_id)
    return tuple(citations)


def citation_ready_chunk(result: RetrievalResult) -> dict[str, Any]:
    """Return a JSON-compatible retrieved chunk with citation metadata."""

    citation = citation_for_chunk(result.chunk)
    return {
        "score": result.score,
        "retrieval_mode": result.retrieval_mode,
        "match_terms": list(result.match_terms),
        "citation": citation.to_json_dict(),
        "text": result.chunk.text,
    }


def format_citation(citation: Citation) -> str:
    """Format a compact human-readable citation label."""

    section = " > ".join(citation.section_path)
    if section:
        return f"{citation.title} ({citation.document_id}, {section})"
    return f"{citation.title} ({citation.document_id})"
