# Pinecone Vector Backend

LabFlow's default retrieval backend remains local hybrid retrieval. Stage 20 adds an optional Pinecone-shaped backend and scripts so the portfolio can discuss vector index lifecycle, metadata contracts, and backend comparison without requiring a live hosted index.

## Configuration

The optional environment variables are documented in `.env.example`:

- `LABFLOW_RAG_BACKEND`
- `PINECONE_API_KEY`
- `PINECONE_INDEX_NAME`
- `PINECONE_NAMESPACE`
- `PINECONE_CLOUD`
- `PINECONE_REGION`
- `PINECONE_DIMENSION`
- `PINECONE_METRIC`

No test, demo, or portfolio check requires Pinecone credentials.

## Index Metadata

The indexing preview includes metadata needed for reliable retrieval operations:

- `chunk_id`;
- `document_id`;
- `source_family`;
- `status`;
- `authority_level`;
- `version`;
- `effective_date`;
- `corpus_fingerprint`;
- `chunker_version`.

This lets a future hosted index be compared against the local corpus manifest and prevents stale vectors from being treated as invisible implementation detail.

## Guarded Live Behavior

`scripts/index_knowledge_pinecone.py` defaults to dry-run. Live mutations require `--confirm-live-pinecone` and valid Pinecone configuration. The current portfolio implementation intentionally keeps live Pinecone indexing optional; the deterministic manifest and metadata preview are the shareable contract.

## Comparison

`scripts/compare_retrieval_backends.py` compares local retrieval with the optional Pinecone backend and reports source-family recall, exact required-source hits, top-k overlap, stale-source rate, conflict count, latency, and corpus fingerprint.
