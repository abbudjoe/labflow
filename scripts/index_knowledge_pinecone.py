#!/usr/bin/env python3
"""Prepare or live-index LabFlow knowledge chunks into Pinecone."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_SRC = REPO_ROOT / "packages" / "labflow-rag" / "src"
if str(RAG_SRC) not in sys.path:
    sys.path.insert(0, str(RAG_SRC))

from labflow_rag.backends.pinecone import DEFAULT_PINECONE_DIMENSION  # noqa: E402
from labflow_rag.corpus_manifest import build_corpus_manifest  # noqa: E402
from labflow_rag.chunking import KnowledgeChunk, chunk_search_text  # noqa: E402
from labflow_rag.index import RagIndex  # noqa: E402
from labflow_rag.retrieval import DeterministicHashVectorBackend  # noqa: E402
from labflow_rag.source_precedence import lifecycle_for_chunk_tags  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="knowledge")
    parser.add_argument("--output", default="artifacts/pinecone/index_report.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-live-pinecone", action="store_true")
    parser.add_argument("--index-name", default=None)
    parser.add_argument("--namespace", default=None)
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()

    corpus_dir = _repo_path(args.corpus)
    output_path = _repo_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_corpus_manifest(corpus_dir)
    index = RagIndex.from_corpus(corpus_dir)
    configured_dimension = int(
        os.environ.get("PINECONE_DIMENSION", str(DEFAULT_PINECONE_DIMENSION))
        or str(DEFAULT_PINECONE_DIMENSION)
    )
    vectors = [_chunk_metadata(chunk, manifest.corpus_fingerprint) for chunk in index.chunks]
    live_requested = args.confirm_live_pinecone and not args.dry_run
    effective_dry_run = not live_requested
    skip_reason = _skip_reason(args, live_requested=live_requested)
    upserted_count = 0
    if live_requested and skip_reason is None:
        upserted_count = upsert_knowledge_index(
            index=index,
            corpus_fingerprint=manifest.corpus_fingerprint,
            index_name=args.index_name or os.environ.get("PINECONE_INDEX_NAME", ""),
            namespace=args.namespace or os.environ.get("PINECONE_NAMESPACE", "labflow-local"),
            dimension=configured_dimension,
            batch_size=args.batch_size,
        )
    report = {
        "backend": "pinecone",
        "dry_run": effective_dry_run,
        "live_requested": live_requested,
        "skipped": skip_reason is not None,
        "skip_reason": skip_reason,
        "index_name": args.index_name or os.environ.get("PINECONE_INDEX_NAME", ""),
        "namespace": args.namespace or os.environ.get("PINECONE_NAMESPACE", "labflow-local"),
        "corpus_fingerprint": manifest.corpus_fingerprint,
        "chunk_count": len(vectors),
        "dimension": configured_dimension,
        "metric": os.environ.get("PINECONE_METRIC", "cosine"),
        "upserted_count": upserted_count,
        "metadata_preview": vectors[:3],
    }
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {output_path}")
    if skip_reason:
        print(f"Pinecone indexing skipped: {skip_reason}")
    elif effective_dry_run:
        print("Pinecone dry-run complete; no live index was mutated.")
    else:
        print("Pinecone live indexing complete.")
    return 0


def _skip_reason(args: argparse.Namespace, *, live_requested: bool) -> str | None:
    if not live_requested:
        return None
    if not os.environ.get("PINECONE_API_KEY"):
        return "PINECONE_API_KEY is absent."
    if not (args.index_name or os.environ.get("PINECONE_INDEX_NAME")):
        return "PINECONE_INDEX_NAME is absent."
    try:
        import pinecone  # noqa: F401  # type: ignore[import-not-found]
    except ImportError:
        return "pinecone package is not installed."
    return None


def upsert_knowledge_index(
    *,
    index: RagIndex,
    corpus_fingerprint: str,
    index_name: str,
    namespace: str,
    dimension: int,
    batch_size: int = 100,
    client: Any | None = None,
) -> int:
    """Upsert deterministic knowledge vectors into a configured Pinecone index."""

    if not index_name:
        msg = "Pinecone index name is required for live upsert."
        raise ValueError(msg)
    if batch_size <= 0:
        msg = "batch_size must be positive."
        raise ValueError(msg)
    pinecone_client = client or _pinecone_client(os.environ["PINECONE_API_KEY"])
    pinecone_index = pinecone_client.Index(index_name)
    vector_backend = DeterministicHashVectorBackend(dimension=dimension)
    records = [
        {
            "id": chunk.chunk_id,
            "values": list(vector_backend.embed(chunk_search_text(chunk))),
            "metadata": _chunk_metadata(chunk, corpus_fingerprint),
        }
        for chunk in index.chunks
    ]
    upserted = 0
    for batch_start in range(0, len(records), batch_size):
        batch = records[batch_start : batch_start + batch_size]
        pinecone_index.upsert(vectors=batch, namespace=namespace)
        upserted += len(batch)
    return upserted


def _pinecone_client(api_key: str) -> Any:
    from pinecone import Pinecone  # type: ignore[import-not-found]

    return Pinecone(api_key=api_key)


def _chunk_metadata(chunk: KnowledgeChunk, corpus_fingerprint: str) -> dict[str, object]:
    lifecycle = lifecycle_for_chunk_tags(
        document_id=chunk.document_id,
        tags=chunk.tags,
        text=chunk.text,
    )
    metadata: dict[str, object | None] = {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "source_family": lifecycle.source_family,
        "status": lifecycle.status.value,
        "version": lifecycle.version,
        "effective_date": lifecycle.effective_date,
        "authority_level": lifecycle.authority_level.value,
        "corpus_fingerprint": corpus_fingerprint,
        "chunker_version": manifest_chunker_version(),
        "tags": list(chunk.tags),
        "stale": lifecycle.stale,
    }
    return _pinecone_metadata(metadata)


def _pinecone_metadata(metadata: dict[str, object | None]) -> dict[str, object]:
    """Return metadata restricted to Pinecone-supported scalar/list values."""

    sanitized: dict[str, object] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
            continue
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            sanitized[key] = value
            continue
        msg = f"Unsupported Pinecone metadata value for {key}: {type(value).__name__}"
        raise TypeError(msg)
    return sanitized


def manifest_chunker_version() -> str:
    from labflow_rag.corpus_manifest import CHUNKER_VERSION

    return CHUNKER_VERSION


def _repo_path(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


if __name__ == "__main__":
    raise SystemExit(main())
