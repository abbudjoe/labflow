# Stage 7 Assembly Review

Review date: 2026-06-08

Stage: `07_rag_foundation`

Authoritative spec: `.codex_build/prompts/07_rag_foundation.md`

Status: `successful`

## Target Contract

Stage 7 builds a local-first RAG foundation over the synthetic `knowledge/` corpus. It must ingest markdown, create stable citation-ready chunks, preserve source metadata, support local keyword retrieval with a vector abstraction that does not require API keys, provide hybrid retrieval when available, and return a grounded no-answer response when retrieval has insufficient support.

## Extracted DoD Checklist

| DoD item | Status | Evidence |
| --- | --- | --- |
| Read `AGENTS.md` | met | Project operating rules read during preflight. |
| Read `ENGINEERING.md` | met | Engineering guide read during preflight. |
| Read `DOCTRINE.md` | met | Product doctrine read during preflight. |
| Read `DECISIONS_LOCKED.md` | met | Locked domain decisions read during preflight. |
| Read `PROJECT_PLAN.md` | met | Project plan read during preflight. |
| Read relevant RAG/eval specs | met | `specs/04_rag_spec.md` and `specs/05_eval_spec.md` read during preflight. |
| Implement `documents.py` | met | Markdown corpus loader added. |
| Implement `chunking.py` | met | Stable chunk model and chunk generator added. |
| Implement `index.py` | met | In-memory local index and tokenizer added. |
| Implement `retrieval.py` | met | Keyword, vector, and hybrid retrievers added. |
| Implement `citations.py` | met | Citation metadata helpers added. |
| Implement `answering.py` | met | Extractive grounded answer and no-answer behavior added. |
| Load markdown files from `knowledge/` | met | `test_ingest_corpus_preserves_metadata_and_stable_chunk_ids`. |
| Generate stable chunk IDs | met | Chunk determinism test compares repeated chunk IDs. |
| Preserve source path, title, headings, tags | met | Metadata assertions cover title, tags, headings, and source path. |
| Implement keyword retrieval at minimum | met | Keyword retrieval test covers JANUS/batch readiness. |
| Add vector retrieval abstraction without external API dependency | met | Deterministic hash-vector backend and test added. |
| Implement hybrid retrieval if possible | met | Hybrid retriever implemented and used in split workflow test. |
| Return citation-ready chunks | met | Answer/citation test asserts citation metadata and JSON serialization. |
| Implement no-answer behavior | met | Unsupported and generic off-domain no-answer tests added. |
| Retrieve split workflow docs for split questions | met | Split workflow retrieval test covers `dna_normalization_sop.md` and exception manual. |
| Retrieve batch readiness docs for JANUS gating questions | met | JANUS gating retrieval test covers batch readiness and JANUS spec. |
| Tests pass without API keys | met | Dependency scan found no external LLM/API-key references; tests pass locally. |

## Evidence Commands

```text
make test
make lint
make type
rg -n "openai|langchain|api_key|OPENAI" packages/labflow-rag || true
git -C /Users/joseph/ngs_lab_automation status --short
```

## Review Findings

- Curie first review: `review-failed`.
  - P1: no-answer gate was too permissive because generic terms such as `about` could retrieve LabFlow chunks for off-domain questions. Fixed by expanding stopwords, adding a minimum support score in `answer_query`, and adding the pizza/sourdough regression test.
- Curie final review: clean, no blocking findings.
- Residual note: Stage 8 evals should calibrate the `0.75` support threshold against golden cases so retrieval changes do not quietly shift answer/no-answer behavior.

## Subagent Review

Reviewer: Curie (`019ea927-a9bf-7d41-ac50-3eb925299f5c`)

Final classification from reviewer:

- RAG ingestion, chunking, index, retrieval, citations, answering: `met`
- Stable chunk IDs and citation metadata: `met`
- Keyword retrieval plus local vector abstraction and hybrid retrieval: `met`
- No-answer behavior: `met`
- Split workflow and JANUS gating retrieval coverage: `met`
- Tests without API keys: `met`

Evidence:

```text
PYTHONPATH=packages/labflow-rag/src uv run ... pytest packages/labflow-rag/tests/test_rag_foundation.py -q
# 7 passed

make test
# 75 passed

make lint
# All checks passed

make type
# mypy success in 49 source files and VS Code extension tsc success

rg -n "openai|langchain|api_key|OPENAI" packages/labflow-rag || true
# no matches

git -C /Users/joseph/ngs_lab_automation status --short
# ?? .DS_Store
```

## Final Classification

`successful`
