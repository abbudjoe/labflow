"""In-memory local index for LabFlow RAG chunks."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re

from labflow_rag.chunking import KnowledgeChunk, chunk_corpus, chunk_search_text
from labflow_rag.documents import KnowledgeDocument, load_corpus

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")
STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "about",
        "are",
        "as",
        "at",
        "be",
        "before",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "for",
        "from",
        "how",
        "i",
        "if",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "please",
        "should",
        "tell",
        "that",
        "the",
        "these",
        "this",
        "those",
        "to",
        "use",
        "what",
        "when",
        "where",
        "who",
        "will",
        "won",
        "would",
        "why",
        "with",
    }
)


@dataclass(frozen=True)
class RagIndex:
    """A local immutable view over documents, chunks, and keyword statistics."""

    documents: tuple[KnowledgeDocument, ...]
    chunks: tuple[KnowledgeChunk, ...]
    document_frequencies: dict[str, int]
    chunk_term_frequencies: dict[str, dict[str, int]]

    @classmethod
    def from_corpus(
        cls,
        corpus_dir: str | Path = "knowledge",
        *,
        max_tokens: int = 220,
    ) -> RagIndex:
        documents = load_corpus(corpus_dir)
        return cls.build(documents, max_tokens=max_tokens)

    @classmethod
    def build(
        cls,
        documents: tuple[KnowledgeDocument, ...],
        *,
        max_tokens: int = 220,
    ) -> RagIndex:
        chunks = chunk_corpus(documents, max_tokens=max_tokens)
        chunk_term_frequencies: dict[str, dict[str, int]] = {}
        document_frequencies: Counter[str] = Counter()
        for chunk in chunks:
            terms = Counter(tokenize(chunk_search_text(chunk)))
            chunk_term_frequencies[chunk.chunk_id] = dict(terms)
            document_frequencies.update(terms.keys())
        return cls(
            documents=documents,
            chunks=chunks,
            document_frequencies=dict(document_frequencies),
            chunk_term_frequencies=chunk_term_frequencies,
        )

    @property
    def document_count(self) -> int:
        return len(self.documents)

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    def chunks_for(
        self,
        *,
        document_ids: tuple[str, ...] = (),
        tags: tuple[str, ...] = (),
    ) -> tuple[KnowledgeChunk, ...]:
        wanted_documents = set(document_ids)
        wanted_tags = {tag.lower() for tag in tags}
        chunks: list[KnowledgeChunk] = []
        for chunk in self.chunks:
            if wanted_documents and chunk.document_id not in wanted_documents:
                continue
            if wanted_tags and wanted_tags.isdisjoint(set(chunk.tags)):
                continue
            chunks.append(chunk)
        return tuple(chunks)


def tokenize(text: str) -> tuple[str, ...]:
    """Tokenize text for local keyword retrieval."""

    return tuple(
        token
        for token in (match.group(0).lower() for match in TOKEN_PATTERN.finditer(text))
        if token not in STOPWORDS
    )
