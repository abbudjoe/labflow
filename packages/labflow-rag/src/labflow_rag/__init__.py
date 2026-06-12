"""Local-first retrieval over the synthetic LabFlow knowledge corpus."""

__version__ = "0.1.0"

from labflow_rag.answering import RagAnswer, answer_query
from labflow_rag.chunking import KnowledgeChunk, chunk_corpus, chunk_document
from labflow_rag.citations import Citation, citation_for_chunk, citations_for_results
from labflow_rag.conflict_detection import conflict_notice_for_results
from labflow_rag.corpus_manifest import CorpusManifest, build_corpus_manifest, corpus_fingerprint
from labflow_rag.documents import KnowledgeDocument, load_corpus, load_markdown_document
from labflow_rag.enterprise import (
    RetrievalDebugReport,
    retrieval_debug_report,
)
from labflow_rag.index import RagIndex
from labflow_rag.retrieval import (
    DeterministicHashVectorBackend,
    HybridRetriever,
    KeywordRetriever,
    RetrievalFilter,
    RetrievalResult,
    VectorRetriever,
)

__all__ = [
    "__version__",
    "Citation",
    "CorpusManifest",
    "DeterministicHashVectorBackend",
    "HybridRetriever",
    "KeywordRetriever",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "RagAnswer",
    "RagIndex",
    "RetrievalFilter",
    "RetrievalResult",
    "RetrievalDebugReport",
    "VectorRetriever",
    "answer_query",
    "build_corpus_manifest",
    "chunk_corpus",
    "chunk_document",
    "citation_for_chunk",
    "citations_for_results",
    "conflict_notice_for_results",
    "corpus_fingerprint",
    "load_corpus",
    "load_markdown_document",
    "retrieval_debug_report",
]
