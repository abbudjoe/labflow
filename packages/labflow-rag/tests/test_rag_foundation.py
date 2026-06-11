from __future__ import annotations

import json

from labflow_rag import (
    DeterministicHashVectorBackend,
    HybridRetriever,
    KeywordRetriever,
    RagIndex,
    answer_query,
    chunk_document,
    load_corpus,
    retrieval_debug_report,
)


def test_ingest_corpus_preserves_metadata_and_stable_chunk_ids() -> None:
    documents = load_corpus("knowledge")
    document_ids = {document.document_id for document in documents}
    assert "dna_normalization_sop.md" in document_ids
    assert "batch_readiness_doctrine.md" in document_ids

    normalization = next(
        document for document in documents if document.document_id == "dna_normalization_sop.md"
    )
    assert normalization.title == "DNA Normalization SOP"
    assert "split_workflow" in normalization.tags
    assert "Synthetic And Non-Production Note" in normalization.headings

    first_pass = chunk_document(normalization)
    second_pass = chunk_document(normalization)
    assert first_pass
    assert [chunk.chunk_id for chunk in first_pass] == [chunk.chunk_id for chunk in second_pass]
    assert first_pass[0].source_path.endswith("knowledge/dna_normalization_sop.md")


def test_retrieve_split_workflow_docs_for_split_question() -> None:
    index = RagIndex.from_corpus("knowledge")
    retriever = HybridRetriever(index)

    results = retriever.retrieve(
        "What happens when calculated sample transfer volume is below 1 uL?",
        top_k=6,
    )

    document_ids = {result.document_id for result in results}
    assert "dna_normalization_sop.md" in document_ids
    assert "exception_handling_manual.md" in document_ids
    assert any("split" in result.match_terms for result in results)


def test_retrieve_batch_readiness_docs_for_janus_gating_question() -> None:
    index = RagIndex.from_corpus("knowledge")
    retriever = KeywordRetriever(index)

    results = retriever.retrieve(
        "Can invalid batches generate JANUS worklists?",
        top_k=6,
    )

    document_ids = {result.document_id for result in results}
    assert "batch_readiness_doctrine.md" in document_ids
    assert "janus_csv_worklist_spec.md" in document_ids
    assert results[0].score > 0


def test_guardrail_policy_ranks_first_for_missing_fact_questions() -> None:
    index = RagIndex.from_corpus("knowledge")
    retriever = HybridRetriever(index)

    results = retriever.retrieve(
        "Could we fill in an absent stock concentration so the batch keeps moving? "
        "guardrail missing infer concentration invalid batch robot readiness exception",
        top_k=6,
    )

    assert results
    assert results[0].document_id == "ai_guardrails_policy.md"
    assert "policy_source_boost" in results[0].match_terms


def test_guardrail_policy_is_returned_for_rna_requant_truth_questions() -> None:
    index = RagIndex.from_corpus("knowledge")
    retriever = HybridRetriever(index)

    results = retriever.retrieve(
        "After RNA re-quant, which concentration is downstream truth for normalization?",
        top_k=6,
    )

    guardrail_result = next(
        result for result in results if result.document_id == "ai_guardrails_policy.md"
    )
    assert "policy_source_boost" in guardrail_result.match_terms


def test_answer_query_returns_citation_ready_chunks() -> None:
    index = RagIndex.from_corpus("knowledge")

    answer = answer_query("Why is a JANUS worklist blocked for an invalid batch?", index)

    assert answer.unsupported is False
    assert answer.citations
    assert answer.retrieved_chunk_ids
    assert "validate_batch" in answer.tool_call_recommendations
    citation = answer.citations[0]
    assert citation.chunk_id.startswith(citation.document_id)
    assert citation.source_path.endswith(citation.document_id)
    json.dumps(answer.to_json_dict())


def test_no_answer_query_returns_unsupported_response() -> None:
    index = RagIndex.from_corpus("knowledge")

    answer = answer_query("Who won the ice hockey championship on Europa in 2035?", index)

    assert answer.unsupported is True
    assert answer.answer == "I do not have enough support in the LabFlow knowledge corpus to answer that."
    assert answer.citations == ()
    assert answer.retrieved_chunk_ids == ()
    json.dumps(answer.to_json_dict())


def test_generic_off_domain_query_returns_unsupported_response() -> None:
    index = RagIndex.from_corpus("knowledge")

    answer = answer_query("Tell me about pizza recipes and sourdough starters", index)

    assert answer.unsupported is True
    assert answer.answer == "I do not have enough support in the LabFlow knowledge corpus to answer that."
    assert answer.citations == ()
    assert answer.retrieved_chunk_ids == ()


def test_vector_backend_is_deterministic_and_local() -> None:
    backend = DeterministicHashVectorBackend(dimension=16)

    first = backend.embed("split workflow child sample")
    second = backend.embed("split workflow child sample")

    assert first == second
    assert len(first) == 16
    assert any(first)


def test_retrieval_debug_reports_stale_source_conflict() -> None:
    index = RagIndex.from_corpus("knowledge")
    retriever = HybridRetriever(index)

    report = retrieval_debug_report(
        "legacy missing concentration estimate current guardrail policy",
        index,
        retriever=retriever,
        top_k=8,
    )

    payload = report.to_json_dict()
    assert "concentration" in payload["expanded_query_terms"]
    assert {"policy", "exception_manual", "retired_sop"}.issubset(
        set(payload["source_family_requirements"])
    )
    assert payload["source_family_counts"]["retired_sop"] >= 1
    assert "legacy_missing_concentration_sop.md" in payload["supplemented_sources"]
    assert payload["missing_required_source_families"] == []
    assert "legacy_missing_concentration_sop.md" in payload["stale_sources"]
    assert payload["conflicts"]
    assert payload["conflicts"][0]["conflict_id"] == "missing_concentration_no_invention"


def test_answer_query_surfaces_source_conflict_with_citations() -> None:
    index = RagIndex.from_corpus("knowledge")
    retriever = HybridRetriever(index)

    answer = answer_query(
        "legacy missing concentration estimate current guardrail policy",
        index,
        retriever=retriever,
        top_k=8,
        minimum_supported_score=0.0,
    )

    assert answer.unsupported is False
    assert "Conflict detected" in answer.answer
    assert "legacy_missing_concentration_sop.md" in answer.answer
    assert "deterministic validation take precedence" in answer.answer
    assert "legacy_missing_concentration_sop.md" in {
        citation.document_id for citation in answer.citations
    }
    assert any(
        citation.document_id != "legacy_missing_concentration_sop.md"
        and (
            "no_invention" in citation.tags
            or "trusted_concentration_source" in citation.tags
            or "deterministic_validation" in citation.tags
            or "guardrails" in citation.tags
        )
        for citation in answer.citations
    )
