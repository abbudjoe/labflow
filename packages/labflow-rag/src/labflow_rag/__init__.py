"""Local-first retrieval over the synthetic LabFlow knowledge corpus."""

__version__ = "0.1.0"

from labflow_rag.answering import RagAnswer, answer_query
from labflow_rag.chunking import KnowledgeChunk, chunk_corpus, chunk_document
from labflow_rag.citations import Citation, citation_for_chunk, citations_for_results
from labflow_rag.documents import KnowledgeDocument, load_corpus, load_markdown_document
from labflow_rag.enterprise import (
    RetrievalDebugReport,
    conflict_notice_for_results,
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
    "chunk_corpus",
    "chunk_document",
    "citation_for_chunk",
    "citations_for_results",
    "conflict_notice_for_results",
    "load_corpus",
    "load_markdown_document",
    "retrieval_debug_report",
]
