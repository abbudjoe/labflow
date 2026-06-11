# RAG Specification

## Purpose

`labflow-rag` retrieves and cites domain-specific knowledge so the agent can answer workflow questions without hallucinating.

## Knowledge corpus

Files in `knowledge/`:

- `dna_quant_picogreen_sop.md`
- `dna_normalization_sop.md`
- `rna_norm_requant_sop.md`
- `batch_readiness_doctrine.md`
- `exception_handling_manual.md`
- `janus_csv_worklist_spec.md`
- `varioskan_tsv_import_spec.md`
- `sample_ancestry_policy.md`
- `ai_guardrails_policy.md`
- `labflow_dsl_reference.md`

## Chunk model

Each chunk should include:

```json
{
  "chunk_id": "batch_readiness_doctrine.md#chunk-003",
  "document_id": "batch_readiness_doctrine.md",
  "title": "Batch Readiness Doctrine",
  "section_path": ["Batch readiness", "Robot-ready gates"],
  "text": "...",
  "tokens_estimate": 220,
  "tags": ["batch_readiness", "janus", "guardrails"]
}
```

## Retrieval

Implement local-first retrieval:

- keyword/BM25-style retrieval or simple TF-IDF fallback;
- vector retrieval if dependencies are available;
- hybrid merge;
- optional reranking stub;
- metadata filters by tags/workflow type;
- stable chunk IDs.

## Answer behavior

A RAG answer must include:

- answer text;
- cited source chunks;
- unsupported/uncertain notes if needed;
- retrieved chunk IDs;
- optional tool-call recommendations.

If no relevant source is retrieved, answer:

> I do not have enough support in the LabFlow knowledge corpus to answer that.

## Grounding rules

- Do not make lab claims without retrieved sources.
- Do not infer missing concentration values.
- Do not state that a batch is valid without calling deterministic validation or citing known validation output.
