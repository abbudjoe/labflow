from __future__ import annotations

from labflow_agent.answer_model import (
    ClaimRewriteDraft,
    UNSUPPORTED_CORPUS_REFUSAL,
    build_grounded_answer_context,
    build_grounded_answer_frame,
    draft_from_rendered_answer,
    render_grounded_answer_frame,
)
from labflow_agent.models import AgentPlan, AgentTask
from labflow_agent.models import SourceChunk
from labflow_rag import RagAnswer
from test_answer_model import _context


def test_canonical_frame_renders_required_claims_and_deterministic_citations() -> None:
    _validator, context = _context()

    frame = build_grounded_answer_frame(context)
    rendered = render_grounded_answer_frame(context)

    assert frame.claims
    assert "readiness_invalid_batch" in [claim.claim_id for claim in frame.claims]
    readiness_claim = next(claim for claim in frame.claims if claim.claim_id == "readiness_invalid_batch")
    assert "not robot-ready" in readiness_claim.canonical_sentence
    assert "block readiness" in readiness_claim.canonical_sentence
    assert "Deterministic validation" in rendered.answer
    assert "MISSING_CONCENTRATION" in rendered.answer
    assert rendered.cited_source_ids == ("batch_readiness_doctrine.md#chunk-001",)
    assert rendered.cited_tool_call_ids == ("tool:0:validate_batch",)
    assert rendered.claim_citations


def test_hybrid_render_keeps_good_rewrite_and_falls_back_bad_claim() -> None:
    _validator, context = _context()
    ai_source = SourceChunk(
        chunk_id="ai_guardrails_policy.md#chunk-test",
        document_id="ai_guardrails_policy.md",
        source_path="knowledge/ai_guardrails_policy.md",
        title="AI Guardrails Policy",
        section_path=("test",),
    )
    context = build_grounded_answer_context(
        question="Why is this batch not robot-ready, and can we guess the missing concentration?",
        plan=context.plan.model_copy(
            update={
                "retrieval_query": "missing concentration robot readiness guess",
            }
        ),
        rag_answer=RagAnswer(
            answer=context.rag_answer,
            citations=(),
            retrieved_chunk_ids=(),
            unsupported=False,
        ),
        source_chunks=(*context.source_chunks, ai_source),
        source_text_by_id={
            **context.source_text_by_id,
            ai_source.chunk_id: "The assistant cannot invent concentrations or infer missing lab facts.",
        },
        tool_calls=context.baseline_response.tool_calls,
        baseline_response=context.baseline_response,
    )
    assert context.obligations is not None
    claim_ids = [claim.claim_id for claim in context.obligations.compiled_claims]
    good_claim = claim_ids[0]
    bad_claim = claim_ids[-1]

    rendered = render_grounded_answer_frame(
        context,
        ClaimRewriteDraft(
            rewrites={
                good_claim: (
                    "Deterministic validation says the batch is not robot-ready and blocks "
                    "readiness because MISSING_CONCENTRATION is present."
                ),
                bad_claim: "The batch is robot-ready and approval was granted.",
            }
        ),
    )

    assert rendered.final_answer_source == "hybrid"
    rejected = [claim for claim in rendered.claims if claim.claim_id == bad_claim][0]
    assert rejected.render_source == "fallback"
    assert rejected.validation_reasons
    assert "robot-ready and approval was granted" not in rendered.answer


def test_unsupported_frame_refuses_without_citations_or_rewrite_authority() -> None:
    _validator, context = _context()
    unsupported = build_grounded_answer_context(
        question="What is the freezer temperature policy?",
        plan=AgentPlan(
            task=AgentTask.ANSWER_WORKFLOW_QUESTION,
            rationale="Answer only if supported.",
            retrieval_query="freezer temperature policy",
        ),
        rag_answer=RagAnswer(
            answer=UNSUPPORTED_CORPUS_REFUSAL,
            citations=(),
            retrieved_chunk_ids=(),
            unsupported=True,
        ),
        source_chunks=(),
        source_text_by_id={},
        tool_calls=(),
        baseline_response=context.baseline_response.model_copy(
            update={
                "answer": UNSUPPORTED_CORPUS_REFUSAL,
                "sources": (),
                "tool_calls": (),
                "unsupported": True,
            }
        ),
    )

    rendered = render_grounded_answer_frame(
        unsupported,
        ClaimRewriteDraft(rewrites={"new_claim": "Invent a supported answer."}),
    )
    draft = draft_from_rendered_answer(rendered)

    assert rendered.unsupported is True
    assert rendered.answer == UNSUPPORTED_CORPUS_REFUSAL
    assert rendered.cited_source_ids == ()
    assert rendered.cited_tool_call_ids == ()
    assert draft.safety_flags == ("unsupported",)
