#!/usr/bin/env python3
"""Prepare or live-index LabFlow knowledge chunks into Pinecone."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_SRC = REPO_ROOT / "packages" / "labflow-rag" / "src"
if str(RAG_SRC) not in sys.path:
    sys.path.insert(0, str(RAG_SRC))

from labflow_rag.corpus_manifest import build_corpus_manifest  # noqa: E402
from labflow_rag.chunking import KnowledgeChunk  # noqa: E402
from labflow_rag.index import RagIndex  # noqa: E402
from labflow_rag.source_precedence import lifecycle_for_chunk_tags  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="knowledge")
    parser.add_argument("--output", default="artifacts/pinecone/index_report.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-live-pinecone", action="store_true")
    parser.add_argument("--index-name", default=None)
    parser.add_argument("--namespace", default=None)
    args = parser.parse_args()

    corpus_dir = _repo_path(args.corpus)
    output_path = _repo_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_corpus_manifest(corpus_dir)
    index = RagIndex.from_corpus(corpus_dir)
    vectors = [_chunk_metadata(chunk, manifest.corpus_fingerprint) for chunk in index.chunks]
    live_requested = not args.dry_run
    skip_reason = _skip_reason(args, live_requested=live_requested)
    report = {
        "backend": "pinecone",
        "dry_run": args.dry_run,
        "live_requested": live_requested,
        "skipped": skip_reason is not None,
        "skip_reason": skip_reason,
        "index_name": args.index_name or os.environ.get("PINECONE_INDEX_NAME", ""),
        "namespace": args.namespace or os.environ.get("PINECONE_NAMESPACE", "labflow-local"),
        "corpus_fingerprint": manifest.corpus_fingerprint,
        "chunk_count": len(vectors),
        "metadata_preview": vectors[:3],
    }
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {output_path}")
    if skip_reason:
        print(f"Pinecone indexing skipped: {skip_reason}")
    elif args.dry_run:
        print("Pinecone dry-run complete; no live index was mutated.")
    else:
        print("Pinecone live indexing complete.")
    return 0


def _skip_reason(args: argparse.Namespace, *, live_requested: bool) -> str | None:
    if args.dry_run:
        return None
    if not args.confirm_live_pinecone:
        return "Live Pinecone indexing requires --confirm-live-pinecone."
    if not os.environ.get("PINECONE_API_KEY"):
        return "PINECONE_API_KEY is absent."
    if not (args.index_name or os.environ.get("PINECONE_INDEX_NAME")):
        return "PINECONE_INDEX_NAME is absent."
    try:
        import pinecone  # noqa: F401  # type: ignore[import-not-found]
    except ImportError:
        return "pinecone package is not installed."
    return "Live Pinecone indexing is not implemented in this local-first portfolio build."


def _chunk_metadata(chunk: KnowledgeChunk, corpus_fingerprint: str) -> dict[str, object]:
    lifecycle = lifecycle_for_chunk_tags(
        document_id=chunk.document_id,
        tags=chunk.tags,
        text=chunk.text,
    )
    return {
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


def manifest_chunker_version() -> str:
    from labflow_rag.corpus_manifest import CHUNKER_VERSION

    return CHUNKER_VERSION


def _repo_path(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


if __name__ == "__main__":
    raise SystemExit(main())
