"""Deterministic markdown chunking for citation-ready retrieval."""

from __future__ import annotations

from dataclasses import dataclass
import re

from labflow_rag.documents import KnowledgeDocument

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
WORD_PATTERN = re.compile(r"[A-Za-z0-9_]+")


@dataclass(frozen=True)
class KnowledgeChunk:
    """A stable retrieval chunk with source metadata."""

    chunk_id: str
    document_id: str
    source_path: str
    title: str
    section_path: tuple[str, ...]
    text: str
    tokens_estimate: int
    tags: tuple[str, ...]


def chunk_corpus(
    documents: tuple[KnowledgeDocument, ...],
    *,
    max_tokens: int = 220,
) -> tuple[KnowledgeChunk, ...]:
    """Chunk all documents in stable document order."""

    chunks: list[KnowledgeChunk] = []
    for document in documents:
        chunks.extend(chunk_document(document, max_tokens=max_tokens))
    return tuple(chunks)


def chunk_document(
    document: KnowledgeDocument,
    *,
    max_tokens: int = 220,
) -> tuple[KnowledgeChunk, ...]:
    """Chunk one markdown document by heading section and paragraph windows."""

    sections = _split_sections(document)
    chunks: list[KnowledgeChunk] = []
    chunk_number = 1
    for section_path, section_text in sections:
        for text in _split_text(section_text, max_tokens=max_tokens):
            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"{document.document_id}#chunk-{chunk_number:03d}",
                    document_id=document.document_id,
                    source_path=document.source_path,
                    title=document.title,
                    section_path=section_path,
                    text=text,
                    tokens_estimate=estimate_tokens(text),
                    tags=document.tags,
                )
            )
            chunk_number += 1
    return tuple(chunks)


def estimate_tokens(text: str) -> int:
    """Estimate tokens using a simple word count suitable for local tests."""

    return max(1, len(WORD_PATTERN.findall(text)))


def chunk_search_text(chunk: KnowledgeChunk) -> str:
    """Return the searchable text surface for a chunk."""

    metadata = " ".join((chunk.title, " ".join(chunk.section_path), " ".join(chunk.tags)))
    return f"{metadata}\n{chunk.text}"


def _split_sections(document: KnowledgeDocument) -> tuple[tuple[tuple[str, ...], str], ...]:
    sections: list[tuple[tuple[str, ...], str]] = []
    current_path: tuple[str, ...] = ()
    current_lines: list[str] = []
    heading_stack: list[tuple[int, str]] = []

    for line in document.text.splitlines():
        match = HEADING_PATTERN.match(line)
        if match is None:
            current_lines.append(line)
            continue

        level = len(match.group(1))
        heading = match.group(2).strip()
        if level == 1:
            continue

        _append_section(sections, current_path, current_lines)
        current_lines = []
        heading_stack = [(item_level, item_heading) for item_level, item_heading in heading_stack if item_level < level]
        heading_stack.append((level, heading))
        current_path = tuple(item_heading for _, item_heading in heading_stack)

    _append_section(sections, current_path, current_lines)
    if not sections:
        return (((document.title,), document.text.strip()),)
    return tuple(sections)


def _append_section(
    sections: list[tuple[tuple[str, ...], str]],
    section_path: tuple[str, ...],
    lines: list[str],
) -> None:
    text = "\n".join(lines).strip()
    if text:
        sections.append((section_path, text))


def _split_text(text: str, *, max_tokens: int) -> tuple[str, ...]:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for paragraph in paragraphs:
        paragraph_tokens = estimate_tokens(paragraph)
        if current and current_tokens + paragraph_tokens > max_tokens:
            chunks.append("\n\n".join(current))
            current = []
            current_tokens = 0
        current.append(paragraph)
        current_tokens += paragraph_tokens

    if current:
        chunks.append("\n\n".join(current))
    return tuple(chunks)
