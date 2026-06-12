"""Deterministic corpus manifest and fingerprint generation."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

from labflow_rag.chunking import chunk_document
from labflow_rag.documents import KnowledgeDocument, load_corpus
from labflow_rag.source_precedence import lifecycle_for_document

CHUNKER_VERSION = "labflow-markdown-heading-window-v1"
RETRIEVAL_METADATA_SCHEMA_VERSION = "labflow-retrieval-metadata-v1"
DEFAULT_CHUNKING_SETTINGS = {"max_tokens": 220}


@dataclass(frozen=True)
class CorpusDocumentManifest:
    """Lifecycle and fingerprint metadata for one corpus document."""

    document_id: str
    source_family: str
    status: str
    version: str
    effective_date: str | None
    supersedes: str | None
    authority_level: str
    content_sha256: str
    normalized_content_sha256: str
    chunker_version: str
    chunking_settings: dict[str, int]
    chunk_count: int
    retrieval_metadata_schema_version: str
    stale: bool

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source_family": self.source_family,
            "status": self.status,
            "version": self.version,
            "effective_date": self.effective_date,
            "supersedes": self.supersedes,
            "authority_level": self.authority_level,
            "content_sha256": self.content_sha256,
            "normalized_content_sha256": self.normalized_content_sha256,
            "chunker_version": self.chunker_version,
            "chunking_settings": dict(self.chunking_settings),
            "chunk_count": self.chunk_count,
            "retrieval_metadata_schema_version": self.retrieval_metadata_schema_version,
            "stale": self.stale,
        }


@dataclass(frozen=True)
class CorpusManifest:
    """Deterministic manifest for a loaded corpus."""

    corpus_dir: str
    chunker_version: str
    chunking_settings: dict[str, int]
    retrieval_metadata_schema_version: str
    documents: tuple[CorpusDocumentManifest, ...]
    corpus_fingerprint: str

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "corpus_dir": self.corpus_dir,
            "chunker_version": self.chunker_version,
            "chunking_settings": dict(self.chunking_settings),
            "retrieval_metadata_schema_version": self.retrieval_metadata_schema_version,
            "document_count": len(self.documents),
            "chunk_count": sum(document.chunk_count for document in self.documents),
            "documents": [document.to_json_dict() for document in self.documents],
            "corpus_fingerprint": self.corpus_fingerprint,
        }


def build_corpus_manifest(
    corpus_dir: str | Path = "knowledge",
    *,
    max_tokens: int = 220,
) -> CorpusManifest:
    """Build a deterministic manifest for a corpus directory."""

    root = Path(corpus_dir)
    documents = load_corpus(root)
    return build_manifest_for_documents(
        documents,
        corpus_dir=root.name,
        max_tokens=max_tokens,
    )


def build_manifest_for_documents(
    documents: tuple[KnowledgeDocument, ...],
    *,
    corpus_dir: str = "knowledge",
    max_tokens: int = 220,
) -> CorpusManifest:
    """Build a deterministic manifest from already-loaded documents."""

    settings = {"max_tokens": max_tokens}
    document_entries = tuple(
        _document_manifest(document, max_tokens=max_tokens, settings=settings)
        for document in sorted(documents, key=lambda item: item.document_id)
    )
    fingerprint_payload = {
        "chunker_version": CHUNKER_VERSION,
        "chunking_settings": settings,
        "retrieval_metadata_schema_version": RETRIEVAL_METADATA_SCHEMA_VERSION,
        "documents": [document.to_json_dict() for document in document_entries],
    }
    return CorpusManifest(
        corpus_dir=Path(corpus_dir).name,
        chunker_version=CHUNKER_VERSION,
        chunking_settings=settings,
        retrieval_metadata_schema_version=RETRIEVAL_METADATA_SCHEMA_VERSION,
        documents=document_entries,
        corpus_fingerprint=_json_hash(fingerprint_payload),
    )


def corpus_fingerprint(corpus_dir: str | Path = "knowledge", *, max_tokens: int = 220) -> str:
    """Return the final corpus fingerprint."""

    return build_corpus_manifest(corpus_dir, max_tokens=max_tokens).corpus_fingerprint


def normalized_content(text: str) -> str:
    """Normalize content for path/timestamp-independent hashing."""

    normalized_lines = [re.sub(r"\s+", " ", line.strip()) for line in text.splitlines()]
    return "\n".join(line for line in normalized_lines if line).strip() + "\n"


def _document_manifest(
    document: KnowledgeDocument,
    *,
    max_tokens: int,
    settings: dict[str, int],
) -> CorpusDocumentManifest:
    lifecycle = lifecycle_for_document(document)
    return CorpusDocumentManifest(
        document_id=document.document_id,
        source_family=lifecycle.source_family,
        status=lifecycle.status.value,
        version=lifecycle.version,
        effective_date=lifecycle.effective_date,
        supersedes=lifecycle.supersedes,
        authority_level=lifecycle.authority_level.value,
        content_sha256=_hash_bytes(document.text.encode("utf-8")),
        normalized_content_sha256=_hash_bytes(normalized_content(document.text).encode("utf-8")),
        chunker_version=CHUNKER_VERSION,
        chunking_settings=dict(settings),
        chunk_count=len(chunk_document(document, max_tokens=max_tokens)),
        retrieval_metadata_schema_version=RETRIEVAL_METADATA_SCHEMA_VERSION,
        stale=lifecycle.stale,
    )


def _json_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _hash_bytes(encoded)


def _hash_bytes(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"
