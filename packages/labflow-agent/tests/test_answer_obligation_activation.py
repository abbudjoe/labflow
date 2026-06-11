from __future__ import annotations

from labflow_agent.answer_model import build_grounded_answer_context
from labflow_agent.models import AgentPlan, AgentTask, SourceChunk
from labflow_rag import RagAnswer
from test_answer_model import _context


def _source(document_id: str) -> SourceChunk:
    return SourceChunk(
        chunk_id=f"{document_id}#chunk-test",
        document_id=document_id,
        source_path=f"knowledge/{document_id}",
        title=document_id,
        section_path=("test",),
    )


def _claim_ids(
    question: str,
    source_text: str = "",
    extra_source_families: tuple[str, ...] = (),
) -> tuple[str, ...]:
    _validator, context = _context()
    sources = (
        context.source_chunks
        + tuple(_source(family) for family in extra_source_families)
    )
    source_text_by_id = {
        **context.source_text_by_id,
        context.source_ids[0]: (
            source_text
            or "Split workflow, duplicate destination, dry-run approval, and RNA re-quant are mentioned here."
        ),
    }
    for source in sources:
        source_text_by_id.setdefault(
            source.chunk_id,
            f"{source.document_id} supports LabFlow doctrine for this answer.",
        )
    context = build_grounded_answer_context(
        question=question,
        plan=AgentPlan(
            task=AgentTask.ANSWER_WORKFLOW_QUESTION,
            rationale="Answer a workflow question.",
            retrieval_query=question,
        ),
        rag_answer=RagAnswer(
            answer=source_text or context.rag_answer,
            citations=(),
            retrieved_chunk_ids=(),
            unsupported=False,
        ),
        source_chunks=sources,
        source_text_by_id=source_text_by_id,
        tool_calls=context.baseline_response.tool_calls,
        baseline_response=context.baseline_response,
    )
    assert context.obligations is not None
    return tuple(claim.claim_id for claim in context.obligations.compiled_claims)


def test_split_obligation_does_not_activate_from_irrelevant_retrieved_chunk() -> None:
    claims = _claim_ids(
        "What does RNA re-quant mean downstream?",
        source_text="This unrelated retrieved chunk mentions split workflow and rounding.",
        extra_source_families=("rna_norm_requant_sop.md", "ai_guardrails_policy.md"),
    )

    assert "rna_requant_truth" in claims
    assert "split_not_rounding" not in claims
    assert "deterministic_decides_output" not in claims


def test_duplicate_destination_obligation_requires_duplicate_intent_or_diagnostic() -> None:
    ordinary_claims = _claim_ids("Why is this batch not robot-ready?")
    duplicate_claims = _claim_ids("What if the YAML has a duplicate destination?")

    assert "duplicate_destination_blocks_batch" not in ordinary_claims
    assert "duplicate_destination_blocks_batch" in duplicate_claims


def test_dry_run_obligation_requires_dry_run_commit_intent() -> None:
    ordinary_claims = _claim_ids("Why is this batch not robot-ready?")
    dry_run_claims = _claim_ids(
        "Does dry-run preview commit a JANUS artifact?",
        extra_source_families=("ai_guardrails_policy.md", "janus_csv_worklist_spec.md"),
    )

    assert "dry_run_not_commit" not in ordinary_claims
    assert "dry_run_not_commit" in dry_run_claims


def test_activated_obligations_include_relevance_reason() -> None:
    _validator, context = _context()
    assert context.obligations is not None

    assert context.obligations.active_profiles
    assert all(claim.relevance_reason for claim in context.obligations.compiled_claims)
