from __future__ import annotations

from pathlib import Path

from labflow_agent.answer_model import (
    ClaimCitation,
    GroundedAnswerContext,
    GroundedAnswerDraft,
    GroundedAnswerDraftValidator,
    build_grounded_answer_context,
    sanitize_prompt_text,
)
from labflow_agent.answer_composer import AnswerComposer
from labflow_agent.models import AgentPlan, AgentTask, ExecutedToolCall, ToolCallMode
from labflow_rag import RagAnswer
from labflow_rag.citations import Citation


def _context() -> tuple[GroundedAnswerDraftValidator, GroundedAnswerContext]:
    citation = Citation(
        chunk_id="batch_readiness_doctrine.md#chunk-001",
        document_id="batch_readiness_doctrine.md",
        source_path="knowledge/batch_readiness_doctrine.md",
        title="Batch Readiness Doctrine",
        section_path=("Validation",),
        tags=("batch-readiness",),
    )
    rag_answer = RagAnswer(
        answer="The corpus says missing concentrations block robot readiness.",
        citations=(citation,),
        retrieved_chunk_ids=(citation.chunk_id,),
        unsupported=False,
    )
    plan = AgentPlan(
        task=AgentTask.VALIDATE_BATCH,
        rationale="Validate supplied workflow data.",
        retrieval_query="missing concentration robot readiness",
    )
    tool_call = ExecutedToolCall(
        tool_name="validate_batch",
        arguments={"batch_id": "RNA_BATCH_BAD_001"},
        mode=ToolCallMode.READ_ONLY,
        result={
            "ok": False,
            "status": "invalid",
            "errors": [
                {
                    "code": "MISSING_CONCENTRATION",
                    "message": "Sample RNA_004 has no concentration.",
                }
            ],
            "artifacts": [],
        },
        audit_event_id="audit_123",
    )
    baseline = AnswerComposer().compose(plan=plan, rag_answer=rag_answer, tool_calls=(tool_call,))
    context = build_grounded_answer_context(
        question="Why is this batch not robot-ready?",
        plan=plan,
        rag_answer=rag_answer,
        source_chunks=baseline.sources,
        source_text_by_id={
            citation.chunk_id: (
                "Missing sample concentrations block JANUS worklists and robot readiness."
            )
        },
        tool_calls=(tool_call,),
        baseline_response=baseline,
        has_workflow_yaml=True,
        has_batch_id=True,
        batch_id="RNA_BATCH_BAD_001",
    )
    return GroundedAnswerDraftValidator(), context


def _qc_context() -> tuple[GroundedAnswerDraftValidator, GroundedAnswerContext]:
    citations = (
        Citation(
            chunk_id="ngs_qc_provenance_policy.md#chunk-001",
            document_id="ngs_qc_provenance_policy.md",
            source_path="knowledge/ngs_qc_provenance_policy.md",
            title="NGS QC Provenance Policy",
            section_path=("Core Rules",),
            tags=("qc",),
        ),
        Citation(
            chunk_id="lab_to_analysis_lineage_policy.md#chunk-001",
            document_id="lab_to_analysis_lineage_policy.md",
            source_path="knowledge/lab_to_analysis_lineage_policy.md",
            title="Lab-To-Analysis Lineage Policy",
            section_path=("Interpretation Rules",),
            tags=("lineage",),
        ),
    )
    rag_answer = RagAnswer(
        answer=(
            "Downstream QC failures can be explained from observed QC metrics "
            "and lineage, but they do not prove a lab root cause."
        ),
        citations=citations,
        retrieved_chunk_ids=tuple(citation.chunk_id for citation in citations),
        unsupported=False,
    )
    plan = AgentPlan(
        task=AgentTask.EXPLAIN_QC_FAILURE,
        rationale="Explain downstream QC failure from deterministic tool output.",
        retrieval_query="downstream QC provenance lineage no causal inference",
    )
    tool_call = ExecutedToolCall(
        tool_name="explain_qc_failure",
        arguments={"sample_id": "RNA_DEMO_FAILED_VALID_UPSTREAM_001"},
        mode=ToolCallMode.READ_ONLY,
        result={
            "ok": False,
            "status": "invalid",
            "errors": [
                {
                    "code": "QC_RESULT_FAILED",
                    "message": (
                        "RNA_DEMO_FAILED_VALID_UPSTREAM_001: Downstream QC metrics failed "
                        "configured thresholds; LabFlow cannot infer a lab root cause."
                    ),
                }
            ],
            "warnings": [
                {
                    "code": "DOWNSTREAM_QC_REVIEW_REQUIRED",
                    "message": "Manual review is required before interpreting downstream QC failure.",
                }
            ],
            "artifacts": [
                {
                    "artifact_type": "qc_failure_explanation",
                    "data": {
                        "sample_id": "RNA_DEMO_FAILED_VALID_UPSTREAM_001",
                        "read_count": 600000,
                        "q30_percent": 70.0,
                        "thresholds": {"min_read_count": 1000000, "min_q30_percent": 80.0},
                        "safe_interpretation": (
                            "Downstream QC metrics failed configured thresholds; "
                            "LabFlow cannot infer a lab root cause from QC metrics alone."
                        ),
                    },
                }
            ],
        },
        audit_event_id="audit_qc_123",
    )
    baseline = AnswerComposer().compose(plan=plan, rag_answer=rag_answer, tool_calls=(tool_call,))
    context = build_grounded_answer_context(
        question="Why did RNA_DEMO_FAILED_VALID_UPSTREAM_001 fail downstream QC?",
        plan=plan,
        rag_answer=rag_answer,
        source_chunks=baseline.sources,
        source_text_by_id={
            citations[0].chunk_id: (
                "Failing downstream QC requires review, but it does not prove a lab root cause."
            ),
            citations[1].chunk_id: (
                "Lineage reports connect sample IDs to quantification, normalization, re-quantification, and downstream QC."
            ),
        },
        tool_calls=(tool_call,),
        baseline_response=baseline,
    )
    return GroundedAnswerDraftValidator(), context


def _claim_citations(context: GroundedAnswerContext) -> tuple[ClaimCitation, ...]:
    assert context.obligations is not None
    return tuple(
        ClaimCitation(
            claim_id=claim.claim_id,
            citation_slot_ids=claim.citation_slot_ids[:1],
        )
        for claim in context.obligations.compiled_claims
        if claim.citation_slot_ids
    )


def test_draft_with_unknown_source_falls_back_to_baseline() -> None:
    validator, context = _context()
    draft = GroundedAnswerDraft(
        answer="The batch is not robot-ready because MISSING_CONCENTRATION is blocking.",
        cited_source_ids=("unknown.md#chunk-999",),
        cited_tool_call_ids=("tool:0:validate_batch",),
        claim_citations=_claim_citations(context),
        next_safe_action="Add measured concentration data, then rerun validation.",
        blocked_reason="validate_batch returned status invalid.",
    )

    response, validation = validator.apply(context, draft)

    assert validation.accepted is False
    assert "draft_cites_unknown_source" in validation.reasons
    assert response.answer == context.baseline_response.answer


def test_answer_composer_adds_profile_policy_sentences() -> None:
    citation = Citation(
        chunk_id="exception_handling_manual.md#chunk-001",
        document_id="exception_handling_manual.md",
        source_path="knowledge/exception_handling_manual.md",
        title="Exception Handling Manual",
        section_path=("Diagnostics",),
        tags=("exceptions",),
    )
    rag_answer = RagAnswer(
        answer="The corpus lists MISSING_CONCENTRATION as a deterministic exception.",
        citations=(citation,),
        retrieved_chunk_ids=(citation.chunk_id,),
        unsupported=False,
    )
    plan = AgentPlan(
        task=AgentTask.ANSWER_WORKFLOW_QUESTION,
        rationale="Answer policy question.",
        retrieval_query=(
            "Could we fill in an absent stock concentration, should failed samples "
            "appear in transfer rows, and can below-minimum volume be rounded?"
        ),
    )

    response = AnswerComposer().compose(plan=plan, rag_answer=rag_answer, tool_calls=())

    assert "must not invent or infer missing concentration" in response.answer
    assert "Invalid samples are blocked" in response.answer
    assert "generate no transfer rows" in response.answer
    assert "split workflow" in response.answer
    assert "rounding is not allowed" in response.answer


def test_draft_with_invented_concentration_falls_back() -> None:
    validator, context = _context()
    draft = GroundedAnswerDraft(
        answer="The batch is not robot-ready; use 12 ng/uL for RNA_004.",
        cited_source_ids=("batch_readiness_doctrine.md#chunk-001",),
        cited_tool_call_ids=("tool:0:validate_batch",),
        claim_citations=_claim_citations(context),
        next_safe_action="Use measured values, then rerun validation.",
        blocked_reason="validate_batch returned status invalid.",
    )

    response, validation = validator.apply(context, draft)

    assert validation.accepted is False
    assert "draft_invents_numeric_lab_value" in validation.reasons
    assert response.answer == context.baseline_response.answer


def test_user_question_numeric_value_does_not_become_allowed_lab_fact() -> None:
    validator, context = _context()
    context = build_grounded_answer_context(
        question="Can I use 42 ng/uL for missing RNA_004?",
        plan=context.plan,
        rag_answer=RagAnswer(
            answer=context.rag_answer,
            citations=(),
            retrieved_chunk_ids=(),
            unsupported=False,
        ),
        source_chunks=context.source_chunks,
        source_text_by_id=context.source_text_by_id,
        tool_calls=context.baseline_response.tool_calls,
        baseline_response=context.baseline_response,
        has_workflow_yaml=True,
        has_batch_id=True,
        batch_id="RNA_BATCH_BAD_001",
    )
    draft = GroundedAnswerDraft(
        answer="The batch is not robot-ready; use 42 ng/uL for RNA_004.",
        cited_source_ids=("batch_readiness_doctrine.md#chunk-001",),
        cited_tool_call_ids=("tool:0:validate_batch",),
        claim_citations=_claim_citations(context),
        next_safe_action="Use measured values, then rerun validation.",
        blocked_reason="validate_batch returned status invalid.",
    )

    response, validation = validator.apply(context, draft)

    assert "42 ng/uL" not in context.fact_set.allowed_numeric_values
    assert validation.accepted is False
    assert "draft_invents_numeric_lab_value" in validation.reasons
    assert response.answer == context.baseline_response.answer


def test_negative_robot_ready_claim_is_accepted_for_invalid_context() -> None:
    validator, context = _context()
    draft = GroundedAnswerDraft(
        answer=(
            "The batch is not robot-ready because deterministic validation reported "
            "MISSING_CONCENTRATION for RNA_004."
        ),
        cited_source_ids=("batch_readiness_doctrine.md#chunk-001",),
        cited_tool_call_ids=("tool:0:validate_batch",),
        claim_citations=_claim_citations(context),
        next_safe_action="Add measured concentration data, then rerun validation.",
        blocked_reason="validate_batch returned status invalid.",
    )

    response, validation = validator.apply(context, draft)

    assert validation.accepted is True
    assert response.answer == draft.answer
    assert response.task is context.baseline_response.task
    assert response.tool_calls == context.baseline_response.tool_calls


def test_qc_evidence_packet_extracts_metric_status_and_boundary_terms() -> None:
    _, context = _qc_context()

    assert context.qc_evidence.present is True
    assert "RNA_DEMO_FAILED_VALID_UPSTREAM_001" in context.qc_evidence.sample_ids
    assert "QC_RESULT_FAILED" in context.qc_evidence.status_codes
    assert "DOWNSTREAM_QC_REVIEW_REQUIRED" in context.qc_evidence.status_codes
    assert "read_count" in context.qc_evidence.metric_terms
    assert "q30_percent" in context.qc_evidence.metric_terms
    assert context.qc_evidence.root_cause_boundary is True


def test_qc_draft_missing_tool_metric_facts_falls_back() -> None:
    validator, context = _qc_context()
    draft = GroundedAnswerDraft(
        answer=(
            "Downstream QC can be explained from observed QC metrics and provenance, "
            "but LabFlow cannot infer a lab root cause from downstream QC alone."
        ),
        cited_source_ids=tuple(source.chunk_id for source in context.source_chunks),
        cited_tool_call_ids=tuple(evidence.evidence_id for evidence in context.tool_evidence),
        claim_citations=_claim_citations(context),
        next_safe_action="Review QC metrics and lineage without inferring root cause.",
    )

    response, validation = validator.apply(context, draft)

    assert validation.accepted is False
    assert any(reason.startswith("draft_missing_tool_fact:") for reason in validation.reasons)
    assert response.answer == context.baseline_response.answer


def test_missing_claim_citations_falls_back() -> None:
    validator, context = _context()
    draft = GroundedAnswerDraft(
        answer=(
            "The batch is not robot-ready because deterministic validation reported "
            "MISSING_CONCENTRATION."
        ),
        cited_source_ids=("batch_readiness_doctrine.md#chunk-001",),
        cited_tool_call_ids=("tool:0:validate_batch",),
        next_safe_action="Add measured concentration data, then rerun validation.",
        blocked_reason="validate_batch returned status invalid.",
    )

    response, validation = validator.apply(context, draft)

    assert validation.accepted is False
    assert "draft_missing_claim_citations" in validation.reasons
    assert response.answer == context.baseline_response.answer


def test_missing_compiled_claim_content_falls_back() -> None:
    validator, context = _context()
    draft = GroundedAnswerDraft(
        answer="The cited evidence was reviewed.",
        cited_source_ids=("batch_readiness_doctrine.md#chunk-001",),
        cited_tool_call_ids=("tool:0:validate_batch",),
        claim_citations=_claim_citations(context),
        next_safe_action="Add measured concentration data, then rerun validation.",
        blocked_reason="validate_batch returned status invalid.",
    )

    response, validation = validator.apply(context, draft)

    assert validation.accepted is False
    assert any(reason.startswith("draft_missing_compiled_claim:") for reason in validation.reasons)
    assert response.answer == context.baseline_response.answer


def test_approval_state_invention_falls_back_without_tool_support() -> None:
    validator, context = _context()
    draft = GroundedAnswerDraft(
        answer=(
            "The batch is not robot-ready because deterministic validation reported "
            "MISSING_CONCENTRATION, and approval was granted."
        ),
        cited_source_ids=("batch_readiness_doctrine.md#chunk-001",),
        cited_tool_call_ids=("tool:0:validate_batch",),
        claim_citations=_claim_citations(context),
        next_safe_action="Add measured concentration data, then rerun validation.",
        blocked_reason="validate_batch returned status invalid.",
    )

    response, validation = validator.apply(context, draft)

    assert validation.accepted is False
    assert "draft_claims_approval_without_tool_support" in validation.reasons
    assert response.answer == context.baseline_response.answer


def test_blanket_claim_citation_stuffing_falls_back() -> None:
    validator, context = _context()
    assert context.obligations is not None
    all_slots = tuple(slot.slot_id for slot in context.obligations.citation_slots)
    draft = GroundedAnswerDraft(
        answer=(
            "The batch is not robot-ready because deterministic validation reported "
            "MISSING_CONCENTRATION."
        ),
        cited_source_ids=("batch_readiness_doctrine.md#chunk-001",),
        cited_tool_call_ids=("tool:0:validate_batch",),
        claim_citations=(
            ClaimCitation(
                claim_id=context.obligations.compiled_claims[0].claim_id,
                citation_slot_ids=all_slots,
            ),
        ),
        next_safe_action="Add measured concentration data, then rerun validation.",
        blocked_reason="validate_batch returned status invalid.",
    )

    response, validation = validator.apply(context, draft)

    assert validation.accepted is False
    assert any(
        reason in validation.reasons
        for reason in (
            "draft_blanket_citation_stuffing",
            "draft_missing_claim_citation:missing_concentration_blocks_readiness",
        )
    )
    assert response.answer == context.baseline_response.answer


def test_tool_output_claim_without_tool_citation_falls_back() -> None:
    validator, context = _context()
    draft = GroundedAnswerDraft(
        answer="Deterministic validation reported MISSING_CONCENTRATION for RNA_004.",
        cited_source_ids=("batch_readiness_doctrine.md#chunk-001",),
        cited_tool_call_ids=(),
        claim_citations=_claim_citations(context),
        next_safe_action="Add measured concentration data, then rerun validation.",
        blocked_reason="validate_batch returned status invalid.",
    )

    response, validation = validator.apply(context, draft)

    assert validation.accepted is False
    assert "draft_missing_tool_evidence_for_tool_claim" in validation.reasons
    assert response.answer == context.baseline_response.answer


def test_quality_flags_report_readability_next_action_and_material_fact_issues() -> None:
    validator, context = _context()
    draft = GroundedAnswerDraft(
        answer=(
            "Thebatch is not robot-ready because deterministic validation reported "
            "MISSING_CONCENTRATION."
        ),
        cited_source_ids=("batch_readiness_doctrine.md#chunk-001",),
        cited_tool_call_ids=("tool:0:validate_batch",),
        claim_citations=_claim_citations(context),
        next_safe_action="Review",
        blocked_reason="validate_batch returned status invalid.",
    )

    response, validation = validator.apply(context, draft)

    assert validation.accepted is True
    assert response.answer == draft.answer
    assert "draft_unreadable_formatting" in validation.quality_flags
    assert "draft_next_action_too_vague" in validation.quality_flags


def test_positive_robot_ready_claim_falls_back_for_invalid_context() -> None:
    validator, context = _context()
    draft = GroundedAnswerDraft(
        answer="The batch is robot-ready after validation.",
        cited_source_ids=("batch_readiness_doctrine.md#chunk-001",),
        cited_tool_call_ids=("tool:0:validate_batch",),
        claim_citations=_claim_citations(context),
        next_safe_action="Generate the JANUS CSV.",
        blocked_reason=None,
    )

    response, validation = validator.apply(context, draft)

    assert validation.accepted is False
    assert "draft_claims_robot_ready_without_tool_support" in validation.reasons
    assert response.blocked_reason == context.baseline_response.blocked_reason


def test_safe_negative_invent_statement_is_accepted() -> None:
    validator, context = _context()
    draft = GroundedAnswerDraft(
        answer=(
            "The batch is not robot-ready because the assistant cannot invent a concentration for RNA_004 because "
            "deterministic validation reported MISSING_CONCENTRATION."
        ),
        cited_source_ids=("batch_readiness_doctrine.md#chunk-001",),
        cited_tool_call_ids=("tool:0:validate_batch",),
        claim_citations=_claim_citations(context),
        next_safe_action="Add measured concentration data, then rerun validation.",
        blocked_reason="validate_batch returned status invalid.",
    )

    response, validation = validator.apply(context, draft)

    assert validation.accepted is True
    assert "draft_claims_missing_lab_fact_inference" not in validation.reasons
    assert response.answer == draft.answer


def test_safe_negative_infer_statement_is_accepted() -> None:
    validator, context = _context()
    draft = GroundedAnswerDraft(
        answer=(
            "The batch is not robot-ready because the assistant must not infer the concentration for RNA_004 because "
            "deterministic validation reported MISSING_CONCENTRATION."
        ),
        cited_source_ids=("batch_readiness_doctrine.md#chunk-001",),
        cited_tool_call_ids=("tool:0:validate_batch",),
        claim_citations=_claim_citations(context),
        next_safe_action="Add measured concentration data, then rerun validation.",
        blocked_reason="validate_batch returned status invalid.",
    )

    response, validation = validator.apply(context, draft)

    assert validation.accepted is True
    assert "draft_claims_missing_lab_fact_inference" not in validation.reasons
    assert response.answer == draft.answer


def test_qc_causal_root_cause_overclaim_falls_back() -> None:
    validator, context = _qc_context()
    draft = GroundedAnswerDraft(
        answer=(
            "Downstream QC can be explained from observed QC metrics and provenance, "
            "but the root cause was failed upstream normalization."
        ),
        cited_source_ids=(
            "ngs_qc_provenance_policy.md#chunk-001",
            "lab_to_analysis_lineage_policy.md#chunk-001",
        ),
        cited_tool_call_ids=("tool:0:explain_qc_failure",),
        claim_citations=_claim_citations(context),
        next_safe_action="Review QC metrics and LabFlow lineage without inferring a lab root cause.",
        blocked_reason="explain_qc_failure returned status invalid.",
    )

    response, validation = validator.apply(context, draft)

    assert validation.accepted is False
    assert "draft_claims_downstream_qc_causal_overclaim" in validation.reasons
    assert response.answer == context.baseline_response.answer


def test_qc_negative_root_cause_boundary_is_accepted() -> None:
    validator, context = _qc_context()
    draft = GroundedAnswerDraft(
        answer=(
            "RNA_DEMO_FAILED_VALID_UPSTREAM_001 has QC_RESULT_FAILED with read_count "
            "600000 and q30_percent 70.0, so downstream QC can be explained from "
            "observed QC metrics and provenance. DOWNSTREAM_QC_REVIEW_REQUIRED applies, "
            "and lineage connects quantification, normalization, re-quantification, "
            "and downstream QC by sample ID. This does not prove a lab root cause."
        ),
        cited_source_ids=(
            "ngs_qc_provenance_policy.md#chunk-001",
            "lab_to_analysis_lineage_policy.md#chunk-001",
        ),
        cited_tool_call_ids=("tool:0:explain_qc_failure",),
        claim_citations=_claim_citations(context),
        next_safe_action="Review QC metrics and LabFlow lineage without inferring a lab root cause.",
        blocked_reason="explain_qc_failure returned status invalid.",
    )

    response, validation = validator.apply(context, draft)

    assert validation.accepted is True
    assert "draft_claims_downstream_qc_causal_overclaim" not in validation.reasons
    assert response.answer == draft.answer


def test_blocked_robot_ready_artifact_statement_is_accepted_for_invalid_context() -> None:
    validator, context = _context()
    draft = GroundedAnswerDraft(
        answer=(
            "The batch is not robot-ready because robot-ready artifacts remain blocked until deterministic validation clears "
            "MISSING_CONCENTRATION."
        ),
        cited_source_ids=("batch_readiness_doctrine.md#chunk-001",),
        cited_tool_call_ids=("tool:0:validate_batch",),
        claim_citations=_claim_citations(context),
        next_safe_action="Add measured concentration data, then rerun validation.",
        blocked_reason="validate_batch returned status invalid.",
    )

    response, validation = validator.apply(context, draft)

    assert validation.accepted is True
    assert response.answer == draft.answer


def test_mixed_negative_and_positive_robot_ready_claim_falls_back() -> None:
    validator, context = _context()
    draft = GroundedAnswerDraft(
        answer=(
            "The batch is not robot-ready yet. "
            "The batch is robot-ready after validation."
        ),
        cited_source_ids=("batch_readiness_doctrine.md#chunk-001",),
        cited_tool_call_ids=("tool:0:validate_batch",),
        claim_citations=_claim_citations(context),
        next_safe_action="Generate the JANUS CSV.",
        blocked_reason=None,
    )

    response, validation = validator.apply(context, draft)

    assert validation.accepted is False
    assert "draft_claims_robot_ready_without_tool_support" in validation.reasons
    assert response.answer == context.baseline_response.answer


def test_source_only_policy_draft_is_accepted_without_tool_evidence() -> None:
    validator, context = _context()
    context = context.model_copy(update={"tool_evidence": (), "obligations": None})
    draft = GroundedAnswerDraft(
        answer="The policy requires deterministic validation before concrete readiness claims.",
        cited_source_ids=("batch_readiness_doctrine.md#chunk-001",),
        cited_tool_call_ids=(),
        claim_citations=(),
        next_safe_action="Run deterministic validation before making a batch-specific claim.",
        blocked_reason=context.baseline_response.blocked_reason,
    )

    response, validation = validator.apply(context, draft)

    assert validation.accepted is True
    assert response.answer == draft.answer


def test_dry_run_preview_does_not_support_committed_artifact_claim() -> None:
    validator, context = _context()
    context = context.model_copy(
        update={
            "fact_set": context.fact_set.model_copy(update={"artifact_statuses": ("preview",)})
        }
    )
    draft = GroundedAnswerDraft(
        answer="The JANUS CSV was committed and approved.",
        cited_source_ids=("batch_readiness_doctrine.md#chunk-001",),
        cited_tool_call_ids=("tool:0:validate_batch",),
        claim_citations=_claim_citations(context),
        next_safe_action="Proceed to robot execution.",
        blocked_reason=None,
    )

    response, validation = validator.apply(context, draft)

    assert validation.accepted is False
    assert "draft_claims_artifact_without_tool_support" in validation.reasons
    assert response.answer == context.baseline_response.answer


def test_sanitized_context_does_not_include_workflow_yaml_or_secrets() -> None:
    _validator, context = _context()
    payload_text = str(context.sanitized_prompt_payload())

    assert "OPENROUTER_API_KEY" not in payload_text
    assert Path("examples/workflows/invalid_rna_norm_requant.workflow.yaml").read_text() not in payload_text
    assert "tool:0:validate_batch" in payload_text


def test_sanitized_context_redacts_planner_fields_that_echo_question_secrets() -> None:
    _validator, context = _context()
    context = context.model_copy(
        update={
            "question": "OPENROUTER_API_KEY=sk-or-v1-secret",
            "plan": context.plan.model_copy(
                update={
                    "rationale": "User pasted OPENROUTER_API_KEY=sk-or-v1-secret.",
                    "retrieval_query": "OPENROUTER_API_KEY=sk-or-v1-secret robot readiness",
                }
            ),
        }
    )

    payload_text = str(context.sanitized_prompt_payload())

    assert "sk-or-v1-secret" not in payload_text
    assert "OPENROUTER_API_KEY=[REDACTED]" in payload_text


def test_sanitize_prompt_text_redacts_question_secrets_and_long_yaml_like_payload() -> None:
    raw = "\n".join(
        [
            "Can I run this? OPENROUTER_API_KEY=sk-or-v1-secret approval_token: approve-123",
            "Authorization: Bearer abc.def.ghi",
            *[f"sample_{index}: value" for index in range(25)],
        ]
    )

    sanitized = sanitize_prompt_text(raw)

    assert "sk-or-v1-secret" not in sanitized
    assert "approve-123" not in sanitized
    assert "abc.def.ghi" not in sanitized
    assert "[TRUNCATED_SANITIZED_PAYLOAD]" in sanitized
