"""Retrieval backend abstractions for LabFlow RAG."""

from labflow_rag.backends.base import BackendQueryResult, RetrievalBackend
from labflow_rag.backends.factory import (
    LOCAL_RAG_BACKEND,
    PINECONE_RAG_BACKEND,
    SUPPORTED_RAG_BACKENDS,
    BackendRetrieverAdapter,
    RetrieverBuildResult,
    build_retriever_from_env,
    retriever_runtime_metadata,
)
from labflow_rag.backends.local import LocalHybridBackend
from labflow_rag.backends.pinecone import PineconeBackend, PineconeBackendConfig

__all__ = [
    "BackendQueryResult",
    "BackendRetrieverAdapter",
    "LOCAL_RAG_BACKEND",
    "LocalHybridBackend",
    "PINECONE_RAG_BACKEND",
    "PineconeBackend",
    "PineconeBackendConfig",
    "RetrievalBackend",
    "RetrieverBuildResult",
    "SUPPORTED_RAG_BACKENDS",
    "build_retriever_from_env",
    "retriever_runtime_metadata",
]
