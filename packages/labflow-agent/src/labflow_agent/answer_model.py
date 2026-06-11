"""Guarded answer-composer model boundary for LabFlow agent responses."""

from __future__ import annotations

import json
import re
from hashlib import sha256
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from labflow_agent.models import (
    AgentPlan,
    AgentResponse,
    ExecutedToolCall,
    JsonDict,
    ModelMetadata,
    SourceChunk,
)
from labflow_rag import RagAnswer

_MEASURE_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:ng\s*/\s*(?:u|µ)l|ng_per_ul|(?:u|µ)l|ng)\b",
    re.IGNORECASE,
)
_WELL_PATTERN = re.compile(r"\b[A-H](?:[1-9]|1[0-2])\b")
_ENV_ASSIGNMENT_PATTERN = re.compile(
    r"\b[A-Z][A-Z0-9_]{2,}\s*=\s*[^,\s]+",
    re.IGNORECASE,
)
_APPROVAL_TOKEN_PATTERN = re.compile(
    r"\b(?:approval[_-]?token|api[_-]?key|openrouter[_-]?api[_-]?key)\s*[:=]\s*[^,\s]+",
    re.IGNORECASE,
)
_BEARER_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_SECRET_LIKE_PATTERN = re.compile(r"\b(?:sk-or-v1-[A-Za-z0-9_-]+|sk-[A-Za-z0-9_-]{16,})\b")
UNSUPPORTED_CORPUS_REFUSAL = (
    "I do not have enough support in the LabFlow knowledge corpus to answer that."
)

SOURCE_FAMILY_CATALOG: frozenset[str] = frozenset(
    {
        "ai_guardrails_policy.md",
        "batch_readiness_doctrine.md",
        "dna_normalization_sop.md",
        "dna_quant_picogreen_sop.md",
        "exception_handling_manual.md",
        "janus_csv_worklist_spec.md",
        "labflow_dsl_reference.md",
        "rna_norm_requant_sop.md",
        "sample_ancestry_policy.md",
        "varioskan_tsv_import_spec.md",
    }
)

DOMAIN_SOURCE_PROFILES: dict[str, tuple[str, ...]] = {
    "missing_lab_fact": (
        "ai_guardrails_policy.md",
        "exception_handling_manual.md",
        "batch_readiness_doctrine.md",
    ),
    "robot_readiness": (
        "batch_readiness_doctrine.md",
        "ai_guardrails_policy.md",
        "janus_csv_worklist_spec.md",
    ),
    "duplicate_destination": (
        "batch_readiness_doctrine.md",
        "exception_handling_manual.md",
    ),
    "dry_run_commit": (
        "ai_guardrails_policy.md",
        "janus_csv_worklist_spec.md",
    ),
    "split_workflow": (
        "dna_normalization_sop.md",
        "exception_handling_manual.md",
        "ai_guardrails_policy.md",
    ),
    "invalid_transfers": (
        "batch_readiness_doctrine.md",
        "ai_guardrails_policy.md",
        "janus_csv_worklist_spec.md",
    ),
    "rna_requant": (
        "rna_norm_requant_sop.md",
        "ai_guardrails_policy.md",
    ),
    "standards": (
        "dna_quant_picogreen_sop.md",
        "varioskan_tsv_import_spec.md",
    ),
}

DOMAIN_CONCEPT_ALIASES: dict[str, tuple[str, ...]] = {
    "blocked": (
        "blocked",
        "block",
        "blocks",
        "blocking",
        "cannot",
        "can't",
        "cant",
        "won't",
        "wont",
        "not",
        "fail",
        "fails",
        "failure",
    ),
    "dry_run": ("dry-run", "dry run", "dry", "preview", "previewing"),
    "commit": ("commit", "commits", "committing", "committed"),
    "approval": ("approval", "approve", "approved", "token"),
    "artifact": ("csv", "worklist", "janus", "robot artifact", "robot-facing"),
    "missing_fact": (
        "missing",
        "absent",
        "unknown",
        "guess",
        "infer",
        "invent",
        "fill in",
        "fill",
    ),
    "concentration": ("concentration", "value", "values"),
    "rna_requant": ("rna", "requant", "re-quant", "re quant"),
    "downstream": ("downstream", "normalization", "trust"),
    "duplicate": ("duplicate", "same well", "same destination", "duplicate well", "duplicate destination"),
    "yaml": ("yaml", "workflow", "dsl"),
    "robot_readiness": ("robot", "ready", "readiness", "robot-ready", "automation"),
    "split": ("split", "sub-minimum", "below-minimum", "below 1", "high concentration"),
    "rounding": ("round", "rounding", "rounded"),
    "standards": ("standard", "standards", "standard curve", "a1-h1"),
    "invalid_transfer": ("invalid sample", "invalid samples", "transfer row", "transfer rows", "transfers"),
}

_UNKNOWN_PROFILE_FAMILIES = {
    family
    for families in DOMAIN_SOURCE_PROFILES.values()
    for family in families
    if family not in SOURCE_FAMILY_CATALOG
}
if _UNKNOWN_PROFILE_FAMILIES:
    raise RuntimeError(
        "Domain source profiles reference unknown source families: "
        + ", ".join(sorted(_UNKNOWN_PROFILE_FAMILIES))
    )


class ToolEvidence(BaseModel):
    """Stable evidence view for one deterministic tool call."""

    model_config = ConfigDict(frozen=True)

    evidence_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    mode: str = Field(min_length=1)
    status: str | None = None
    error_codes: tuple[str, ...] = ()
    error_messages: tuple[str, ...] = ()
    audit_event_id: str | None = None
    artifact_statuses: tuple[str, ...] = ()
    artifact_ids: tuple[str, ...] = ()


class GroundedFactSet(BaseModel):
    """Conservative fact inventory extracted from fixed context."""

    model_config = ConfigDict(frozen=True)

    source_facts: tuple[str, ...] = ()
    tool_facts: tuple[str, ...] = ()
    allowed_numeric_values: tuple[str, ...] = ()
    allowed_sample_ids: tuple[str, ...] = ()
    allowed_wells: tuple[str, ...] = ()
    blocked_diagnostic_codes: tuple[str, ...] = ()
    artifact_statuses: tuple[str, ...] = ()


class CitationSlot(BaseModel):
    """Role-labeled evidence slot available to answer composition."""

    model_config = ConfigDict(frozen=True)

    slot_id: str = Field(min_length=1)
    kind: Literal["source", "tool"]
    evidence_id: str = Field(min_length=1)
    family: str | None = None
    label: str = Field(min_length=1)
    summary: str = ""


class ClaimObligation(BaseModel):
    """Deterministically compiled claim the answer should express."""

    model_config = ConfigDict(frozen=True)

    claim_id: str = Field(min_length=1)
    required_terms: tuple[str, ...] = ()
    acceptable_phrases: tuple[str, ...] = ()
    citation_slot_ids: tuple[str, ...] = ()
    tool_fact_terms: tuple[str, ...] = ()
    priority: Literal["required", "supporting"] = "required"
    relevance_reason: str = ""


class ClaimCitation(BaseModel):
    """Draft-level mapping from one compiled claim to evidence slots."""

    model_config = ConfigDict(frozen=True)

    claim_id: str = Field(min_length=1)
    citation_slot_ids: tuple[str, ...] = ()


class DeterministicToolSummary(BaseModel):
    """Typed, compact summary of deterministic tool truth."""

    model_config = ConfigDict(frozen=True)

    tool_call_ids: tuple[str, ...] = ()
    batch_status: Literal["valid", "invalid", "unknown"] = "unknown"
    blocking_error_codes: tuple[str, ...] = ()
    blocking_error_messages: tuple[str, ...] = ()
    artifact_statuses: tuple[str, ...] = ()
    robot_artifact_status: Literal["blocked", "preview", "committed", "none", "unknown"] = "unknown"
    safe_next_action: str | None = None


class AnswerObligations(BaseModel):
    """Live-safe compiled answer contract derived from fixed context."""

    model_config = ConfigDict(frozen=True)

    question: str = Field(min_length=1)
    answer_mode: Literal[
        "readiness_explanation",
        "policy_explanation",
        "workflow_exception_summary",
        "general_grounded_answer",
    ] = "general_grounded_answer"
    compiled_claims: tuple[ClaimObligation, ...] = ()
    citation_slots: tuple[CitationSlot, ...] = ()
    active_profiles: tuple[str, ...] = ()
    forbidden_phrases: tuple[str, ...] = ()
    required_next_action_terms: tuple[str, ...] = ()
    deterministic_tool_summary: DeterministicToolSummary = Field(
        default_factory=DeterministicToolSummary
    )
    diagnostics: tuple[str, ...] = ()


class GroundedAnswerContext(BaseModel):
    """Immutable answer-composition context captured after tools execute."""

    model_config = ConfigDict(frozen=True)

    question: str = Field(min_length=1)
    has_workflow_yaml: bool = False
    has_batch_id: bool = False
    has_diagnostic_code: bool = False
    batch_id: str | None = None
    plan: AgentPlan
    rag_answer: str
    rag_unsupported: bool
    source_chunks: tuple[SourceChunk, ...] = ()
    source_text_by_id: dict[str, str] = Field(default_factory=dict)
    tool_evidence: tuple[ToolEvidence, ...] = ()
    baseline_response: AgentResponse
    fact_set: GroundedFactSet
    obligations: AnswerObligations | None = None

    @property
    def source_ids(self) -> tuple[str, ...]:
        """Return source chunk IDs visible to the composer."""

        return tuple(source.chunk_id for source in self.source_chunks)

    @property
    def tool_evidence_ids(self) -> tuple[str, ...]:
        """Return stable tool evidence IDs visible to the composer."""

        return tuple(evidence.evidence_id for evidence in self.tool_evidence)

    def sanitized_prompt_payload(self) -> JsonDict:
        """Return bounded context safe to send to an answer composer provider."""

        return {
            "question": sanitize_prompt_text(self.question),
            "has_workflow_yaml": self.has_workflow_yaml,
            "has_batch_id": self.has_batch_id,
            "has_diagnostic_code": self.has_diagnostic_code,
            "batch_id": self.batch_id,
            "plan": {
                "task": self.plan.task.value,
                "rationale": sanitize_prompt_text(self.plan.rationale),
                "retrieval_query": sanitize_prompt_text(self.plan.retrieval_query),
            },
            "sources": [
                {
                    "chunk_id": source.chunk_id,
                    "document_id": source.document_id,
                    "title": source.title,
                    "section_path": list(source.section_path),
                    "text": sanitize_prompt_text(self.source_text_by_id.get(source.chunk_id, "")),
                }
                for source in self.source_chunks
            ],
            "tool_evidence": [evidence.model_dump(mode="json") for evidence in self.tool_evidence],
            "compiled_obligations": (
                self.obligations.model_dump(mode="json") if self.obligations is not None else None
            ),
            "answer_frame": build_grounded_answer_frame(self).sanitized_prompt_payload(),
            "baseline": {
                "answer": sanitize_prompt_text(self.baseline_response.answer),
                "next_safe_action": sanitize_prompt_text(self.baseline_response.next_safe_action),
                "blocked_reason": (
                    sanitize_prompt_text(self.baseline_response.blocked_reason)
                    if self.baseline_response.blocked_reason
                    else None
                ),
                "unsupported": self.baseline_response.unsupported,
            },
        }


class EvidenceSlotRef(BaseModel):
    """Deterministic reference from a rendered claim to evidence."""

    model_config = ConfigDict(frozen=True)

    slot_id: str = Field(min_length=1)
    kind: Literal["source", "tool"]
    evidence_id: str = Field(min_length=1)
    family: str | None = None
    label: str = Field(min_length=1)


class AnswerClaimFrame(BaseModel):
    """One deterministic claim with fixed evidence ownership."""

    model_config = ConfigDict(frozen=True)

    claim_id: str = Field(min_length=1)
    canonical_sentence: str = Field(min_length=1)
    evidence_slots: tuple[EvidenceSlotRef, ...] = ()
    protected_terms: tuple[str, ...] = ()
    allowed_fact_terms: tuple[str, ...] = ()
    forbidden_terms: tuple[str, ...] = ()
    relevance_reason: str = Field(min_length=1)
    priority: Literal["required", "supporting"] = "required"


class GroundedAnswerFrame(BaseModel):
    """Deterministic answer frame that can render without an LLM."""

    model_config = ConfigDict(frozen=True)

    frame_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    answer_mode: Literal[
        "readiness_explanation",
        "policy_explanation",
        "workflow_exception_summary",
        "general_grounded_answer",
    ] = "general_grounded_answer"
    claims: tuple[AnswerClaimFrame, ...] = ()
    next_safe_action: str = Field(min_length=1)
    blocked_reason: str | None = None
    unsupported: bool = False
    diagnostics: tuple[str, ...] = ()
    active_profiles: tuple[str, ...] = ()

    def sanitized_prompt_payload(self) -> JsonDict:
        """Return the bounded payload sent to optional rewrite models."""

        return {
            "frame_id": self.frame_id,
            "question": sanitize_prompt_text(self.question),
            "answer_mode": self.answer_mode,
            "unsupported": self.unsupported,
            "active_profiles": list(self.active_profiles),
            "claims": [
                {
                    "claim_id": claim.claim_id,
                    "canonical_sentence": sanitize_prompt_text(claim.canonical_sentence),
                    "protected_terms": list(claim.protected_terms),
                    "evidence_labels": [slot.label for slot in claim.evidence_slots],
                    "style_hint": "Rewrite for concise operator clarity without changing facts.",
                }
                for claim in self.claims
            ],
            "next_safe_action": sanitize_prompt_text(self.next_safe_action),
            "blocked_reason": sanitize_prompt_text(self.blocked_reason),
        }


class ClaimRewriteDraft(BaseModel):
    """Optional model rewrites keyed by deterministic claim IDs."""

    model_config = ConfigDict(frozen=True)

    rewrites: dict[str, str] = Field(default_factory=dict)
    next_safe_action_rewrite: str | None = None


class RenderedClaim(BaseModel):
    """Rendered claim text plus validation provenance."""

    model_config = ConfigDict(frozen=True)

    claim_id: str = Field(min_length=1)
    sentence: str = Field(min_length=1)
    render_source: Literal["canonical", "rewrite", "fallback"]
    validation_reasons: tuple[str, ...] = ()
    citation_slot_ids: tuple[str, ...] = ()


class RenderedAnswer(BaseModel):
    """Rendered answer and trace metadata."""

    model_config = ConfigDict(frozen=True)

    answer: str = Field(min_length=1)
    cited_source_ids: tuple[str, ...] = ()
    cited_tool_call_ids: tuple[str, ...] = ()
    claim_citations: tuple[ClaimCitation, ...] = ()
    next_safe_action: str = Field(min_length=1)
    blocked_reason: str | None = None
    unsupported: bool = False
    claims: tuple[RenderedClaim, ...] = ()
    final_answer_source: Literal["canonical", "rewrite", "hybrid"] = "canonical"
    diagnostics: tuple[str, ...] = ()


class GroundedAnswerDraft(BaseModel):
    """Model-authored draft fields with no authority over lab truth."""

    model_config = ConfigDict(frozen=True)

    answer: str = Field(min_length=1)
    cited_source_ids: tuple[str, ...] = ()
    cited_tool_call_ids: tuple[str, ...] = ()
    claim_citations: tuple[ClaimCitation, ...] = ()
    next_safe_action: str = Field(min_length=1)
    blocked_reason: str | None = None
    safety_flags: tuple[str, ...] = ()


class GroundedAnswerDraftValidation(BaseModel):
    """Validation result for a model-authored answer draft."""

    model_config = ConfigDict(frozen=True)

    accepted: bool
    reasons: tuple[str, ...] = ()
    quality_flags: tuple[str, ...] = ()


class AnswerModelAdapter(Protocol):
    """Answer composer adapter interface, separate from planning."""

    metadata: ModelMetadata

    def draft(self, context: GroundedAnswerContext) -> GroundedAnswerDraft:
        """Return a structured answer draft from fixed grounded context."""


class DeterministicAnswerModel:
    """Draft adapter that mirrors the deterministic baseline response."""

    metadata = ModelMetadata(
        model_id="deterministic_answer_composer",
        version="0.1.0",
        provider="labflow-local",
    )

    def draft(self, context: GroundedAnswerContext) -> GroundedAnswerDraft:
        """Return a draft equivalent to the baseline response."""

        return draft_from_rendered_answer(render_grounded_answer_frame(context))


class GroundedAnswerDraftValidator:
    """Conservative validator for inference answer drafts."""

    def validate(
        self,
        context: GroundedAnswerContext,
        draft: GroundedAnswerDraft,
    ) -> GroundedAnswerDraftValidation:
        """Validate draft claims against fixed sources and deterministic tool facts."""

        reasons: list[str] = []
        source_ids = set(context.source_ids)
        tool_ids = set(context.tool_evidence_ids)
        unknown_sources = set(draft.cited_source_ids) - source_ids
        unknown_tools = set(draft.cited_tool_call_ids) - tool_ids
        if unknown_sources:
            reasons.append("draft_cites_unknown_source")
        if unknown_tools:
            reasons.append("draft_cites_unknown_tool_call")
        if context.rag_unsupported and not draft.safety_flags:
            reasons.append("unsupported_context_requires_safety_flag")
        if context.source_chunks and not draft.cited_source_ids and not draft.cited_tool_call_ids:
            reasons.append("draft_missing_evidence_citation")
        reasons.extend(_claim_citation_reasons(context, draft))
        reasons.extend(_compiled_claim_content_reasons(context, draft.answer))
        reasons.extend(_numeric_invention_reasons(context, draft.answer))
        reasons.extend(_well_invention_reasons(context, draft.answer))
        if _claims_positive_robot_ready(context, draft.answer):
            reasons.append("draft_claims_robot_ready_without_tool_support")
        if _claims_artifact_generated_without_support(context, draft.answer):
            reasons.append("draft_claims_artifact_without_tool_support")
        if _claims_approval_state_without_support(context, draft.answer):
            reasons.append("draft_claims_approval_without_tool_support")
        if _claims_missing_value_inference(draft.answer):
            reasons.append("draft_claims_missing_lab_fact_inference")
        if _tool_claim_requires_evidence(context, draft.answer) and not draft.cited_tool_call_ids:
            reasons.append("draft_missing_tool_evidence_for_tool_claim")
        quality_flags = _non_blocking_quality_flags(context, draft)
        return GroundedAnswerDraftValidation(
            accepted=not reasons,
            reasons=tuple(dict.fromkeys(reasons)),
            quality_flags=tuple(dict.fromkeys(quality_flags)),
        )

    def apply(
        self,
        context: GroundedAnswerContext,
        draft: GroundedAnswerDraft,
    ) -> tuple[AgentResponse, GroundedAnswerDraftValidation]:
        """Apply an accepted draft to safe response fields or fall back to baseline."""

        validation = self.validate(context, draft)
        if not validation.accepted:
            return context.baseline_response, validation
        return (
            context.baseline_response.model_copy(
                update={
                    "answer": draft.answer,
                    "next_safe_action": draft.next_safe_action,
                    "blocked_reason": draft.blocked_reason,
                }
            ),
            validation,
        )


def build_grounded_answer_context(
    *,
    question: str,
    plan: AgentPlan,
    rag_answer: RagAnswer,
    source_chunks: tuple[SourceChunk, ...],
    source_text_by_id: dict[str, str],
    tool_calls: tuple[ExecutedToolCall, ...],
    baseline_response: AgentResponse,
    has_workflow_yaml: bool = False,
    has_batch_id: bool = False,
    has_diagnostic_code: bool = False,
    batch_id: str | None = None,
) -> GroundedAnswerContext:
    """Build fixed evidence context for deterministic or inference composition."""

    tool_evidence = tuple(_tool_evidence(index, call) for index, call in enumerate(tool_calls))
    visible_text = " ".join(
        [
            rag_answer.answer,
            " ".join(source_text_by_id.get(source.chunk_id, "") for source in source_chunks),
            json.dumps([call.result for call in tool_calls], sort_keys=True),
        ]
    )
    fact_set = GroundedFactSet(
        source_facts=tuple(source_text_by_id.get(source.chunk_id, "") for source in source_chunks),
        tool_facts=tuple(json.dumps(call.result, sort_keys=True) for call in tool_calls),
        allowed_numeric_values=tuple(dict.fromkeys(_MEASURE_PATTERN.findall(visible_text))),
        allowed_sample_ids=tuple(dict.fromkeys(re.findall(r"\b[A-Z]{2,}_[A-Z0-9_]+\b", visible_text))),
        allowed_wells=tuple(dict.fromkeys(_WELL_PATTERN.findall(visible_text))),
        blocked_diagnostic_codes=tuple(dict.fromkeys(_error_codes(tool_calls))),
        artifact_statuses=tuple(dict.fromkeys(_artifact_statuses(tool_calls))),
    )
    context = GroundedAnswerContext(
        question=question,
        has_workflow_yaml=has_workflow_yaml,
        has_batch_id=has_batch_id,
        has_diagnostic_code=has_diagnostic_code,
        batch_id=batch_id,
        plan=plan,
        rag_answer=rag_answer.answer,
        rag_unsupported=rag_answer.unsupported,
        source_chunks=source_chunks,
        source_text_by_id=source_text_by_id,
        tool_evidence=tool_evidence,
        baseline_response=baseline_response,
        fact_set=fact_set,
    )
    return context.model_copy(update={"obligations": compile_answer_obligations(context)})


def source_family_profiles_for_context(
    *,
    question: str,
    retrieval_query: str = "",
    tool_text: str = "",
) -> tuple[str, ...]:
    """Return deterministic domain profiles from user intent and tool state."""

    haystack = f"{question} {retrieval_query} {tool_text}".casefold()
    concepts = set(domain_concepts_for_text(haystack))
    profiles: list[str] = []

    def add(profile: str) -> None:
        profiles.append(profile)

    if "missing_fact" in concepts and ("concentration" in concepts or "concentration" in haystack):
        add("missing_lab_fact")
    if (
        "robot_readiness" in concepts
        or "artifact" in concepts
        or ("blocked" in concepts and ("batch" in haystack or "validation" in haystack))
    ):
        add("robot_readiness")
    if "duplicate" in concepts or "duplicate_destination_location" in haystack:
        add("duplicate_destination")
    if "dry_run" in concepts or "commit" in concepts or "approval" in concepts:
        add("dry_run_commit")
    if "split" in concepts or "rounding" in concepts or any(term in haystack for term in ("1 ul", "1 µl")):
        add("split_workflow")
    if "invalid_transfer" in concepts or (
        "invalid" in haystack and "transfer" in haystack
    ):
        add("invalid_transfers")
    if "rna_requant" in concepts:
        add("rna_requant")
    if "standards" in concepts:
        add("standards")
    return tuple(dict.fromkeys(profiles))


def domain_concepts_for_text(text: str) -> tuple[str, ...]:
    """Return canonical domain concepts from safe lexical aliases."""

    normalized = _normalize_domain_text(text)
    concepts: list[str] = []
    for concept, aliases in DOMAIN_CONCEPT_ALIASES.items():
        if any(_domain_alias_matches(normalized, alias) for alias in aliases):
            concepts.append(concept)
    return tuple(dict.fromkeys(concepts))


def _normalize_domain_text(text: str) -> str:
    normalized = text.casefold().replace("_", " ").replace("µ", "u")
    normalized = normalized.replace("won't", "wont").replace("can't", "cant")
    normalized = normalized.replace("-", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _domain_alias_matches(normalized_text: str, alias: str) -> bool:
    normalized_alias = _normalize_domain_text(alias)
    if " " in normalized_alias:
        return normalized_alias in normalized_text
    return bool(re.search(rf"\b{re.escape(normalized_alias)}\b", normalized_text))


def source_families_for_profiles(profiles: tuple[str, ...]) -> tuple[str, ...]:
    """Return source families requested by deterministic profiles."""

    families: list[str] = []
    for profile in profiles:
        families.extend(DOMAIN_SOURCE_PROFILES.get(profile, ()))
    return tuple(dict.fromkeys(families))


def compile_answer_obligations(context: GroundedAnswerContext) -> AnswerObligations:
    """Compile a live-safe answer contract from fixed context only."""

    slots = _citation_slots(context)
    tool_summary = _deterministic_tool_summary(context)
    question = context.question.casefold()
    tool_text = " ".join(context.fact_set.tool_facts)
    active_profiles = source_family_profiles_for_context(
        question=context.question,
        retrieval_query=context.plan.retrieval_query,
        tool_text=tool_text,
    )
    claims: list[ClaimObligation] = []
    diagnostics: list[str] = []

    def add_claim(
        claim_id: str,
        *,
        required_terms: tuple[str, ...],
        acceptable_phrases: tuple[str, ...],
        slot_families: tuple[str, ...] = (),
        slot_kinds: tuple[str, ...] = (),
        tool_terms: tuple[str, ...] = (),
        relevance_reason: str,
    ) -> None:
        slot_ids = _slot_ids(slots, families=slot_families, kinds=slot_kinds)
        if not slot_ids:
            diagnostics.append(f"missing_evidence_for:{claim_id}")
            return
        claims.append(
            ClaimObligation(
                claim_id=claim_id,
                required_terms=required_terms,
                acceptable_phrases=acceptable_phrases,
                citation_slot_ids=slot_ids,
                tool_fact_terms=tool_terms,
                relevance_reason=relevance_reason,
            )
        )

    if tool_summary.batch_status == "invalid" and "robot_readiness" in active_profiles:
        add_claim(
            "readiness_invalid_batch",
            required_terms=("deterministic", "validation"),
            acceptable_phrases=("not robot-ready", "cannot go to the robot", "blocks readiness"),
            slot_families=("batch_readiness_doctrine.md", "ai_guardrails_policy.md"),
            slot_kinds=("tool",),
            tool_terms=tool_summary.blocking_error_codes,
            relevance_reason="invalid deterministic validation plus robot/JANUS readiness intent",
        )
        if "MISSING_CONCENTRATION" in tool_summary.blocking_error_codes:
            add_claim(
                "missing_concentration_blocks_readiness",
                required_terms=("MISSING_CONCENTRATION",),
                acceptable_phrases=(
                    "invalid batch",
                    "blocks readiness",
                    "validation failure",
                    "not robot-ready",
                    "blocking",
                ),
                slot_families=("batch_readiness_doctrine.md", "ai_guardrails_policy.md"),
                slot_kinds=("tool",),
                tool_terms=("MISSING_CONCENTRATION",),
                relevance_reason="missing concentration diagnostic blocks concrete readiness",
            )
        if "JANUS_BLOCKED_FOR_INVALID_BATCH" in tool_summary.blocking_error_codes:
            add_claim(
                "janus_blocked_invalid_batch",
                required_terms=("JANUS",),
                acceptable_phrases=("blocked", "invalid batch", "remain blocked"),
                slot_families=("janus_csv_worklist_spec.md", "ai_guardrails_policy.md"),
                slot_kinds=("tool",),
                tool_terms=("JANUS_BLOCKED_FOR_INVALID_BATCH",),
                relevance_reason="invalid deterministic validation blocks JANUS artifacts",
            )
    if "missing_lab_fact" in active_profiles:
        add_claim(
            "missing_lab_fact_policy",
            required_terms=("concentration",),
            acceptable_phrases=("cannot invent", "must not infer", "do not guess"),
            slot_families=("ai_guardrails_policy.md", "exception_handling_manual.md"),
            relevance_reason="missing/guess/infer lab fact intent",
        )
    if "split_workflow" in active_profiles:
        add_claim(
            "split_not_rounding",
            required_terms=("split workflow",),
            acceptable_phrases=("rounding is not allowed", "cannot be rounded", "1 uL minimum"),
            slot_families=("dna_normalization_sop.md", "exception_handling_manual.md"),
            relevance_reason="split/high-concentration/sub-minimum transfer intent",
        )
        add_claim(
            "deterministic_decides_output",
            required_terms=("deterministic",),
            acceptable_phrases=("validation decides", "planning decides", "worklist"),
            slot_families=("ai_guardrails_policy.md", "janus_csv_worklist_spec.md"),
            relevance_reason="split/worklist output requires deterministic validation",
        )
    if "dry_run_commit" in active_profiles:
        add_claim(
            "dry_run_not_commit",
            required_terms=("dry-run",),
            acceptable_phrases=("preview", "does not commit", "approval required"),
            slot_families=("ai_guardrails_policy.md", "janus_csv_worklist_spec.md"),
            relevance_reason="dry-run/commit/approval boundary intent",
        )
    if "dry_run_commit" in active_profiles and "robot_readiness" in active_profiles:
        add_claim(
            "validation_required_before_robot_artifacts",
            required_terms=("validation",),
            acceptable_phrases=(
                "robot-ready artifacts",
                "robot-facing artifacts",
                "invalid batch",
                "JANUS_BLOCKED_FOR_INVALID_BATCH",
            ),
            slot_families=("ai_guardrails_policy.md", "janus_csv_worklist_spec.md"),
            slot_kinds=("tool",),
            tool_terms=(
                tuple(
                    code
                    for code in tool_summary.blocking_error_codes
                    if code == "JANUS_BLOCKED_FOR_INVALID_BATCH"
                )
            ),
            relevance_reason="dry-run/JANUS boundary still requires deterministic validation",
        )
    if "duplicate_destination" in active_profiles:
        add_claim(
            "duplicate_destination_blocks_batch",
            required_terms=("DUPLICATE_DESTINATION_LOCATION",),
            acceptable_phrases=("duplicate destination", "invalid batch", "blocked"),
            slot_families=("batch_readiness_doctrine.md", "exception_handling_manual.md"),
            slot_kinds=("tool",),
            tool_terms=("DUPLICATE_DESTINATION_LOCATION",),
            relevance_reason="duplicate destination intent or deterministic diagnostic",
        )
    if "invalid_transfers" in active_profiles:
        add_claim(
            "invalid_samples_no_transfers",
            required_terms=("invalid",),
            acceptable_phrases=("no robot transfers", "no transfer rows", "blocked"),
            slot_families=("batch_readiness_doctrine.md", "ai_guardrails_policy.md"),
            relevance_reason="invalid sample/transfer row intent",
        )
    if "rna_requant" in active_profiles:
        add_claim(
            "rna_requant_truth",
            required_terms=("re-quant",),
            acceptable_phrases=("downstream concentration", "downstream normalization"),
            slot_families=("rna_norm_requant_sop.md", "ai_guardrails_policy.md"),
            relevance_reason="RNA re-quant downstream concentration intent",
        )
    if "standards" in active_profiles:
        add_claim(
            "standards_location",
            required_terms=("standards",),
            acceptable_phrases=("A1-H1", "standard curve"),
            slot_families=("dna_quant_picogreen_sop.md", "varioskan_tsv_import_spec.md"),
            relevance_reason="standards/standard curve intent",
        )

    mode = "general_grounded_answer"
    if any(term in question for term in ("robot", "ready", "readiness")):
        mode = "readiness_explanation"
    elif any(term in question for term in ("guess", "infer", "approval", "commit")):
        mode = "policy_explanation"
    elif tool_summary.blocking_error_codes:
        mode = "workflow_exception_summary"

    return AnswerObligations(
        question=context.question,
        answer_mode=mode,  # type: ignore[arg-type]
        compiled_claims=tuple(claims),
        citation_slots=slots,
        active_profiles=active_profiles,
        forbidden_phrases=(
            "estimate the concentration",
            "generate anyway",
            "ready for robot execution",
        ),
        required_next_action_terms=_required_next_action_terms(active_profiles, tool_summary),
        deterministic_tool_summary=tool_summary,
        diagnostics=tuple(diagnostics),
    )


def build_grounded_answer_frame(context: GroundedAnswerContext) -> GroundedAnswerFrame:
    """Build a deterministic answer frame from compiled obligations."""

    obligations = context.obligations
    if context.rag_unsupported and not context.source_chunks and not context.tool_evidence:
        return GroundedAnswerFrame(
            frame_id="unsupported:no_evidence",
            question=context.question,
            answer_mode="general_grounded_answer",
            claims=(),
            next_safe_action="Add supported LabFlow knowledge or run deterministic validation before answering.",
            blocked_reason="No relevant LabFlow source or deterministic tool evidence supports the answer.",
            unsupported=True,
            diagnostics=("unsupported_no_evidence",),
            active_profiles=(),
        )
    if obligations is None:
        obligations = compile_answer_obligations(context)
    claims = tuple(
        _claim_frame_for_obligation(context, obligations, claim)
        for claim in obligations.compiled_claims
    )
    if not claims and context.source_chunks:
        claims = (
            AnswerClaimFrame(
                claim_id="general_grounded_answer",
                canonical_sentence=sanitize_prompt_text(context.baseline_response.answer),
                evidence_slots=tuple(
                    _evidence_slot_ref(slot)
                    for slot in obligations.citation_slots
                    if slot.kind == "source"
                ),
                protected_terms=(),
                allowed_fact_terms=(),
                forbidden_terms=obligations.forbidden_phrases,
                relevance_reason="grounded RAG answer with source evidence but no specialized profile",
            ),
        )
    frame_seed = json.dumps(
        {
            "question": context.question,
            "claim_ids": [claim.claim_id for claim in claims],
            "evidence_slot_ids": [
                slot.slot_id for slot in obligations.citation_slots
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return GroundedAnswerFrame(
        frame_id=f"frame:{sha256(frame_seed.encode('utf-8')).hexdigest()[:16]}",
        question=context.question,
        answer_mode=obligations.answer_mode,
        claims=claims,
        next_safe_action=_next_safe_action_for_obligations(obligations),
        blocked_reason=context.baseline_response.blocked_reason,
        unsupported=context.baseline_response.unsupported,
        diagnostics=obligations.diagnostics,
        active_profiles=obligations.active_profiles,
    )


def render_grounded_answer_frame(
    context: GroundedAnswerContext,
    rewrite_draft: ClaimRewriteDraft | None = None,
) -> RenderedAnswer:
    """Render a deterministic or hybrid answer from an answer frame."""

    frame = build_grounded_answer_frame(context)
    if frame.unsupported:
        return RenderedAnswer(
            answer=UNSUPPORTED_CORPUS_REFUSAL,
            next_safe_action=frame.next_safe_action,
            blocked_reason=frame.blocked_reason,
            unsupported=True,
            final_answer_source="canonical",
            diagnostics=frame.diagnostics,
        )
    rewrites = rewrite_draft.rewrites if rewrite_draft is not None else {}
    rendered_claims: list[RenderedClaim] = []
    for claim in frame.claims:
        rewrite = sanitize_prompt_text(rewrites.get(claim.claim_id, ""))
        reasons = _claim_rewrite_reasons(context, claim, rewrite)
        if rewrite and not reasons:
            sentence = rewrite
            source: Literal["canonical", "rewrite", "fallback"] = "rewrite"
        elif rewrite and reasons:
            sentence = claim.canonical_sentence
            source = "fallback"
        else:
            sentence = claim.canonical_sentence
            source = "canonical"
        rendered_claims.append(
            RenderedClaim(
                claim_id=claim.claim_id,
                sentence=sentence,
                render_source=source,
                validation_reasons=reasons,
                citation_slot_ids=tuple(slot.slot_id for slot in claim.evidence_slots),
            )
        )
    if rendered_claims:
        answer = " ".join(claim.sentence for claim in rendered_claims)
    else:
        answer = sanitize_prompt_text(context.baseline_response.answer)
    next_safe_action = frame.next_safe_action
    if rewrite_draft is not None and rewrite_draft.next_safe_action_rewrite:
        candidate = sanitize_prompt_text(rewrite_draft.next_safe_action_rewrite)
        if (
            not _next_action_too_vague(candidate)
            and not _claims_missing_value_inference(candidate)
            and _next_action_satisfies_required_terms(candidate, context.obligations)
        ):
            next_safe_action = candidate
    citations = _rendered_claim_citations(rendered_claims)
    source_ids, tool_ids = _rendered_evidence_ids(frame)
    render_sources = {claim.render_source for claim in rendered_claims}
    final_source: Literal["canonical", "rewrite", "hybrid"]
    if render_sources == {"rewrite"}:
        final_source = "rewrite"
    elif "rewrite" in render_sources:
        final_source = "hybrid"
    else:
        final_source = "canonical"
    return RenderedAnswer(
        answer=answer,
        cited_source_ids=source_ids,
        cited_tool_call_ids=tool_ids,
        claim_citations=citations,
        next_safe_action=next_safe_action,
        blocked_reason=frame.blocked_reason,
        unsupported=frame.unsupported,
        claims=tuple(rendered_claims),
        final_answer_source=final_source,
        diagnostics=tuple(
            dict.fromkeys(
                [
                    *frame.diagnostics,
                    *(
                        f"rewrite_rejected:{claim.claim_id}:{reason}"
                        for claim in rendered_claims
                        for reason in claim.validation_reasons
                    ),
                ]
            )
        ),
    )


def draft_from_rendered_answer(rendered: RenderedAnswer) -> GroundedAnswerDraft:
    """Convert deterministic rendered output to the legacy draft shape."""

    safety_flags = ("unsupported",) if rendered.unsupported else ()
    return GroundedAnswerDraft(
        answer=rendered.answer,
        cited_source_ids=rendered.cited_source_ids,
        cited_tool_call_ids=rendered.cited_tool_call_ids,
        claim_citations=rendered.claim_citations,
        next_safe_action=rendered.next_safe_action,
        blocked_reason=rendered.blocked_reason,
        safety_flags=safety_flags,
    )


def _claim_frame_for_obligation(
    context: GroundedAnswerContext,
    obligations: AnswerObligations,
    claim: ClaimObligation,
) -> AnswerClaimFrame:
    slots_by_id = {slot.slot_id: slot for slot in obligations.citation_slots}
    current_sources = set(context.source_ids)
    current_tools = set(context.tool_evidence_ids)
    evidence = tuple(
        _evidence_slot_ref(slots_by_id[slot_id])
        for slot_id in claim.citation_slot_ids
        if slot_id in slots_by_id
        and (
            (slots_by_id[slot_id].kind == "source" and slots_by_id[slot_id].evidence_id in current_sources)
            or (slots_by_id[slot_id].kind == "tool" and slots_by_id[slot_id].evidence_id in current_tools)
        )
    )
    sentence = _canonical_sentence_for_claim(claim)
    protected = tuple(dict.fromkeys((*claim.required_terms, *claim.tool_fact_terms)))
    return AnswerClaimFrame(
        claim_id=claim.claim_id,
        canonical_sentence=sentence,
        evidence_slots=evidence,
        protected_terms=protected,
        allowed_fact_terms=claim.acceptable_phrases,
        forbidden_terms=obligations.forbidden_phrases,
        relevance_reason=claim.relevance_reason or claim.claim_id,
        priority=claim.priority,
    )


def _canonical_sentence_for_claim(claim: ClaimObligation) -> str:
    tool_facts = ", ".join(claim.tool_fact_terms)
    if claim.claim_id == "readiness_invalid_batch":
        suffix = f" because {tool_facts} is present" if tool_facts else ""
        return (
            "Deterministic validation says this invalid batch is not robot-ready; "
            f"validation failures block readiness{suffix}."
        )
    if claim.claim_id == "missing_concentration_blocks_readiness":
        return "MISSING_CONCENTRATION is a validation failure for this invalid batch and blocks readiness."
    if claim.claim_id == "janus_blocked_invalid_batch":
        return "JANUS output remains blocked for the invalid batch, including JANUS_BLOCKED_FOR_INVALID_BATCH."
    if claim.claim_id == "missing_lab_fact_policy":
        return "The assistant cannot invent concentration values, must not infer missing concentrations, and do not guess missing lab facts."
    if claim.claim_id == "split_not_rounding":
        return "High-concentration or sub-1 uL below-minimum transfer volume uses split workflow; rounding is not allowed and the transfer cannot be rounded into a worklist."
    if claim.claim_id == "deterministic_decides_output":
        return "Deterministic validation decides worklist output before a JANUS worklist can be generated."
    if claim.claim_id == "dry_run_not_commit":
        return "A dry-run is a preview and does not commit artifacts; approval required before commit."
    if claim.claim_id == "validation_required_before_robot_artifacts":
        suffix = f" because {tool_facts} is present" if tool_facts else ""
        return (
            "Deterministic validation is required before robot-ready artifacts; "
            f"robot-facing JANUS artifacts remain blocked for an invalid batch{suffix}."
        )
    if claim.claim_id == "duplicate_destination_blocks_batch":
        suffix = f" {tool_facts}" if tool_facts else " DUPLICATE_DESTINATION_LOCATION"
        return f"Duplicate destination locations block the invalid batch, including diagnostic{suffix}."
    if claim.claim_id == "invalid_samples_no_transfers":
        return "Invalid samples are blocked and generate no robot transfers or transfer rows."
    if claim.claim_id == "rna_requant_truth":
        return "The RNA re-quant result becomes the downstream concentration for downstream normalization."
    if claim.claim_id == "standards_location":
        return "Standards for the standard curve use A1-H1 on the separate standards plate."
    phrase = claim.acceptable_phrases[0] if claim.acceptable_phrases else "is required"
    terms = " ".join(claim.required_terms)
    return f"{terms} {phrase}.".strip()


def _required_next_action_terms(
    profiles: tuple[str, ...],
    tool_summary: DeterministicToolSummary,
) -> tuple[str, ...]:
    terms: list[str] = ["validation"]
    if "missing_lab_fact" in profiles or "MISSING_CONCENTRATION" in tool_summary.blocking_error_codes:
        terms.extend(["measured", "concentration"])
    if tool_summary.batch_status == "invalid" or "robot_readiness" in profiles:
        terms.extend(["fix", "rerun"])
    if "dry_run_commit" in profiles:
        terms.extend(["dry-run", "approval"])
    if "split_workflow" in profiles:
        terms.extend(["split workflow", "re-quant", "planning"])
    if "duplicate_destination" in profiles:
        terms.extend(["duplicate", "destination"])
    if "rna_requant" in profiles:
        terms.extend(["re-quant", "downstream concentration"])
    return tuple(dict.fromkeys(terms))


def _next_safe_action_for_obligations(obligations: AnswerObligations) -> str:
    profiles = set(obligations.active_profiles)
    tool_summary = obligations.deterministic_tool_summary
    if "missing_lab_fact" in profiles or "MISSING_CONCENTRATION" in tool_summary.blocking_error_codes:
        return "Provide the measured trusted concentration, fix validation errors, then rerun validation."
    if "duplicate_destination" in profiles:
        return "Fix duplicate source or destination occupancy, then rerun validation."
    if "split_workflow" in profiles:
        return "Use the split workflow, re-quant the child concentration, then rerun deterministic planning and validation."
    if "dry_run_commit" in profiles:
        return "Run validation, run a dry-run preview, then commit only with an approval token."
    if "rna_requant" in profiles:
        return "Use the measured RNA re-quant concentration for downstream normalization, then rerun validation."
    if tool_summary.batch_status == "invalid" or "robot_readiness" in profiles:
        return "Fix the reported diagnostics, then rerun validation."
    return tool_summary.safe_next_action or "Rerun deterministic validation before proceeding."


def _next_action_satisfies_required_terms(
    action: str,
    obligations: AnswerObligations | None,
) -> bool:
    if obligations is None or not obligations.required_next_action_terms:
        return True
    lower = action.casefold()
    return all(term.casefold() in lower for term in obligations.required_next_action_terms)


def _evidence_slot_ref(slot: CitationSlot) -> EvidenceSlotRef:
    return EvidenceSlotRef(
        slot_id=slot.slot_id,
        kind=slot.kind,
        evidence_id=slot.evidence_id,
        family=slot.family,
        label=slot.label,
    )


def _claim_rewrite_reasons(
    context: GroundedAnswerContext,
    claim: AnswerClaimFrame,
    rewrite: str,
) -> tuple[str, ...]:
    if not rewrite:
        return ()
    reasons: list[str] = []
    lower = rewrite.casefold()
    for term in claim.protected_terms:
        if term and term.casefold() not in lower:
            reasons.append(f"rewrite_missing_protected_term:{term}")
    if claim.allowed_fact_terms and not any(
        phrase.casefold() in lower for phrase in claim.allowed_fact_terms
    ):
        reasons.append("rewrite_missing_acceptable_phrase")
    for term in claim.forbidden_terms:
        if term and term.casefold() in lower:
            reasons.append(f"rewrite_contains_forbidden_term:{term}")
    reasons.extend(reason.replace("draft_", "rewrite_") for reason in _numeric_invention_reasons(context, rewrite))
    reasons.extend(reason.replace("draft_", "rewrite_") for reason in _well_invention_reasons(context, rewrite))
    if _claims_positive_robot_ready(context, rewrite):
        reasons.append("rewrite_claims_robot_ready_without_tool_support")
    if _claims_artifact_generated_without_support(context, rewrite):
        reasons.append("rewrite_claims_artifact_without_tool_support")
    if _claims_approval_state_without_support(context, rewrite):
        reasons.append("rewrite_claims_approval_without_tool_support")
    if _claims_missing_value_inference(rewrite):
        reasons.append("rewrite_claims_missing_lab_fact_inference")
    return tuple(dict.fromkeys(reasons))


def _rendered_claim_citations(rendered_claims: list[RenderedClaim]) -> tuple[ClaimCitation, ...]:
    return tuple(
        ClaimCitation(
            claim_id=claim.claim_id,
            citation_slot_ids=claim.citation_slot_ids,
        )
        for claim in rendered_claims
        if claim.citation_slot_ids
    )


def _rendered_evidence_ids(frame: GroundedAnswerFrame) -> tuple[tuple[str, ...], tuple[str, ...]]:
    source_ids: list[str] = []
    tool_ids: list[str] = []
    for claim in frame.claims:
        for slot in claim.evidence_slots:
            if slot.kind == "source":
                source_ids.append(slot.evidence_id)
            elif slot.kind == "tool":
                tool_ids.append(slot.evidence_id)
    return tuple(dict.fromkeys(source_ids)), tuple(dict.fromkeys(tool_ids))


def _tool_evidence(index: int, call: ExecutedToolCall) -> ToolEvidence:
    errors = tuple(error for error in call.result.get("errors", []) if isinstance(error, dict))
    artifacts = tuple(
        artifact for artifact in call.result.get("artifacts", []) if isinstance(artifact, dict)
    )
    return ToolEvidence(
        evidence_id=f"tool:{index}:{call.tool_name}",
        tool_name=call.tool_name,
        mode=call.mode.value,
        status=str(call.result.get("status")) if call.result.get("status") is not None else None,
        error_codes=tuple(str(error.get("code")) for error in errors if error.get("code")),
        error_messages=tuple(str(error.get("message")) for error in errors if error.get("message")),
        audit_event_id=call.audit_event_id,
        artifact_statuses=tuple(
            str(artifact.get("status")) for artifact in artifacts if artifact.get("status")
        ),
        artifact_ids=tuple(
            str(artifact.get("artifact_id")) for artifact in artifacts if artifact.get("artifact_id")
        ),
    )


def _error_codes(tool_calls: tuple[ExecutedToolCall, ...]) -> list[str]:
    codes: list[str] = []
    for call in tool_calls:
        for error in call.result.get("errors", []):
            if isinstance(error, dict) and error.get("code"):
                codes.append(str(error["code"]))
    return codes


def _artifact_statuses(tool_calls: tuple[ExecutedToolCall, ...]) -> list[str]:
    statuses: list[str] = []
    for call in tool_calls:
        for artifact in call.result.get("artifacts", []):
            if isinstance(artifact, dict) and artifact.get("status"):
                statuses.append(str(artifact["status"]))
    return statuses


def _citation_slots(context: GroundedAnswerContext) -> tuple[CitationSlot, ...]:
    slots: list[CitationSlot] = []
    for source in context.source_chunks:
        family = source.document_id or _source_family(source.source_path)
        slots.append(
            CitationSlot(
                slot_id=f"source:{source.chunk_id}",
                kind="source",
                evidence_id=source.chunk_id,
                family=family,
                label=source.title or family,
                summary=sanitize_prompt_text(context.source_text_by_id.get(source.chunk_id, ""))[:300],
            )
        )
    for evidence in context.tool_evidence:
        slots.append(
            CitationSlot(
                slot_id=f"tool:{evidence.evidence_id}",
                kind="tool",
                evidence_id=evidence.evidence_id,
                family=evidence.tool_name,
                label=evidence.tool_name,
                summary="; ".join(
                    (
                        f"status={evidence.status or 'unknown'}",
                        f"errors={','.join(evidence.error_codes) or 'none'}",
                        f"artifacts={','.join(evidence.artifact_statuses) or 'none'}",
                    )
                ),
            )
        )
    return tuple(slots)


def _source_family(source_path: str) -> str:
    return source_path.rsplit("/", 1)[-1]


def _slot_ids(
    slots: tuple[CitationSlot, ...],
    *,
    families: tuple[str, ...] = (),
    kinds: tuple[str, ...] = (),
) -> tuple[str, ...]:
    ids: list[str] = []
    for slot in slots:
        family_match = bool(families) and any(
            family == slot.family or family in (slot.family or "") for family in families
        )
        kind_match = bool(kinds) and slot.kind in kinds
        if family_match or kind_match:
            ids.append(slot.slot_id)
    return tuple(dict.fromkeys(ids))


def _deterministic_tool_summary(context: GroundedAnswerContext) -> DeterministicToolSummary:
    statuses = {evidence.status for evidence in context.tool_evidence if evidence.status}
    if any(status in {"invalid", "blocked", "error"} for status in statuses):
        batch_status: Literal["valid", "invalid", "unknown"] = "invalid"
    elif statuses and statuses <= {"ok", "valid", "ready"}:
        batch_status = "valid"
    else:
        batch_status = "unknown"
    artifact_statuses = tuple(
        dict.fromkeys(status for evidence in context.tool_evidence for status in evidence.artifact_statuses)
    )
    artifact_status_set = {status.casefold() for status in artifact_statuses}
    if artifact_status_set & {"committed", "approved"}:
        robot_artifact_status: Literal["blocked", "preview", "committed", "none", "unknown"] = "committed"
    elif artifact_status_set & {"preview", "dry_run", "dry-run"}:
        robot_artifact_status = "preview"
    elif batch_status == "invalid" or context.baseline_response.blocked_reason:
        robot_artifact_status = "blocked"
    elif artifact_statuses:
        robot_artifact_status = "unknown"
    else:
        robot_artifact_status = "none"
    return DeterministicToolSummary(
        tool_call_ids=context.tool_evidence_ids,
        batch_status=batch_status,
        blocking_error_codes=tuple(
            dict.fromkeys(code for evidence in context.tool_evidence for code in evidence.error_codes)
        ),
        blocking_error_messages=tuple(
            dict.fromkeys(message for evidence in context.tool_evidence for message in evidence.error_messages)
        ),
        artifact_statuses=artifact_statuses,
        robot_artifact_status=robot_artifact_status,
        safe_next_action=context.baseline_response.next_safe_action,
    )


def _claim_citation_reasons(
    context: GroundedAnswerContext,
    draft: GroundedAnswerDraft,
) -> list[str]:
    obligations = context.obligations
    if obligations is None or not obligations.compiled_claims:
        return []
    reasons: list[str] = []
    claims_by_id = {claim.claim_id: claim for claim in obligations.compiled_claims}
    citations_by_claim = {citation.claim_id: citation for citation in draft.claim_citations}
    if not draft.claim_citations:
        return ["draft_missing_claim_citations"]
    valid_slot_ids = {slot.slot_id for slot in obligations.citation_slots}
    used_slot_ids = {
        slot_id for citation in draft.claim_citations for slot_id in citation.citation_slot_ids
    }
    if used_slot_ids - valid_slot_ids:
        reasons.append("draft_cites_unknown_citation_slot")
    for claim in obligations.compiled_claims:
        citation = citations_by_claim.get(claim.claim_id)
        if citation is None:
            reasons.append(f"draft_missing_claim_citation:{claim.claim_id}")
            continue
        cited = set(citation.citation_slot_ids)
        allowed = set(claim.citation_slot_ids)
        if not cited:
            reasons.append(f"draft_empty_claim_citation:{claim.claim_id}")
        elif not cited <= allowed:
            reasons.append(f"draft_claim_cites_unallowed_slot:{claim.claim_id}")
    if len(used_slot_ids) == len(valid_slot_ids) and len(valid_slot_ids) > len(claims_by_id):
        reasons.append("draft_blanket_citation_stuffing")
    return reasons


def _default_claim_citations(context: GroundedAnswerContext) -> tuple[ClaimCitation, ...]:
    """Return a conservative citation map for deterministic baseline mirroring."""

    if context.obligations is None:
        return ()
    return tuple(
        ClaimCitation(
            claim_id=claim.claim_id,
            citation_slot_ids=claim.citation_slot_ids[:1],
        )
        for claim in context.obligations.compiled_claims
        if claim.citation_slot_ids
    )


def _compiled_claim_content_reasons(
    context: GroundedAnswerContext,
    answer: str,
) -> list[str]:
    obligations = context.obligations
    if obligations is None:
        return []
    answer_lower = answer.casefold()
    reasons: list[str] = []
    for claim in obligations.compiled_claims:
        missing_required = [
            term
            for term in claim.required_terms
            if term.casefold() not in answer_lower
        ]
        acceptable_match = (
            not claim.acceptable_phrases
            or any(phrase.casefold() in answer_lower for phrase in claim.acceptable_phrases)
        )
        missing_tool_facts = [
            term
            for term in claim.tool_fact_terms
            if term.casefold() not in answer_lower
        ]
        if missing_required or not acceptable_match:
            reasons.append(f"draft_missing_compiled_claim:{claim.claim_id}")
        if missing_tool_facts:
            reasons.append(f"draft_missing_tool_fact:{claim.claim_id}")
    return reasons


def _numeric_invention_reasons(context: GroundedAnswerContext, answer: str) -> list[str]:
    allowed = {_normalize_measure(value) for value in context.fact_set.allowed_numeric_values}
    invented = [
        value
        for value in _MEASURE_PATTERN.findall(answer)
        if _normalize_measure(value) not in allowed
    ]
    return ["draft_invents_numeric_lab_value"] if invented else []


def _well_invention_reasons(context: GroundedAnswerContext, answer: str) -> list[str]:
    allowed = {value.upper() for value in context.fact_set.allowed_wells}
    invented = [value for value in _WELL_PATTERN.findall(answer) if value.upper() not in allowed]
    return ["draft_invents_well_location"] if invented else []


def _normalize_measure(value: str) -> str:
    return value.casefold().replace(" ", "").replace("µ", "u")


def _claims_positive_robot_ready(context: GroundedAnswerContext, answer: str) -> bool:
    if _tool_context_supports_ready(context):
        return False
    lower = answer.casefold()
    return _has_unnegated_readiness_occurrence(
        lower,
        ("robot-ready", "robot ready", "ready for robot"),
    )


def _has_unnegated_readiness_occurrence(lower_answer: str, terms: tuple[str, ...]) -> bool:
    for term in terms:
        start = 0
        while True:
            index = lower_answer.find(term, start)
            if index == -1:
                break
            if not _readiness_occurrence_is_negated_or_blocked(lower_answer, index, term):
                return True
            start = index + len(term)
    return False


def _readiness_occurrence_is_negated_or_blocked(
    lower_answer: str,
    index: int,
    term: str,
) -> bool:
    prefix = lower_answer[max(0, index - 32) : index]
    suffix = lower_answer[index : index + len(term) + 72]
    negative_prefixes = (
        "not ",
        "not yet ",
        "cannot be ",
        "can't be ",
        "is not ",
        "isn't ",
        "remain blocked until ",
        "remains blocked until ",
    )
    if any(prefix.endswith(marker) for marker in negative_prefixes):
        return True
    if "only when" in suffix or "only after" in suffix:
        return True
    if "ready rule" in suffix or "readiness rule" in suffix:
        return True
    if "artifact" in suffix:
        blocking_markers = (
            "blocked",
            "remain blocked",
            "remains blocked",
            "not generated",
            "not produced",
            "cannot be generated",
            "cannot be produced",
        )
        return any(marker in suffix for marker in blocking_markers)
    post_negative_markers = (
        " is blocked",
        " are blocked",
        " remains blocked",
        " remain blocked",
        " cannot proceed",
    )
    return any(marker in suffix for marker in post_negative_markers)


def _tool_context_supports_ready(context: GroundedAnswerContext) -> bool:
    if context.baseline_response.blocked_reason:
        return False
    statuses = {evidence.status for evidence in context.tool_evidence if evidence.status}
    return bool(statuses) and statuses <= {"ok", "valid", "ready"}


def _claims_artifact_generated_without_support(context: GroundedAnswerContext, answer: str) -> bool:
    lower = answer.casefold()
    if not any(
        term in lower
        for term in ("generated", "committed", "approved", "wrote", "previewed")
    ):
        return False
    if "janus" not in lower and "artifact" not in lower and "csv" not in lower:
        return False
    statuses = {status.casefold() for status in context.fact_set.artifact_statuses}
    if "committed" in lower or "approved" in lower:
        return not bool(statuses & {"committed", "approved"})
    if "generated" in lower or "wrote" in lower:
        return not bool(statuses & {"generated", "created", "written"})
    if "previewed" in lower:
        return not bool(statuses & {"preview", "dry_run", "dry-run"})
    return False


def _claims_approval_state_without_support(context: GroundedAnswerContext, answer: str) -> bool:
    lower = answer.casefold()
    approval_claims = (
        "approval was granted",
        "approval has been granted",
        "operator approved",
        "approved the commit",
        "commit was approved",
        "approval token was provided",
        "approved for commit",
    )
    if not any(claim in lower for claim in approval_claims):
        return False
    statuses = {status.casefold() for status in context.fact_set.artifact_statuses}
    return not bool(statuses & {"approved", "committed"})


def _claims_missing_value_inference(answer: str) -> bool:
    lower = answer.casefold()
    unsafe_phrases = (
        "estimate the concentration",
        "infer the concentration",
        "assume the concentration",
        "fill in the missing concentration",
    )
    if any(_has_unprohibited_phrase_occurrence(lower, phrase) for phrase in unsafe_phrases):
        return True
    return _has_unprohibited_invent_occurrence(lower)


def _has_unprohibited_invent_occurrence(lower_answer: str) -> bool:
    return _has_unprohibited_phrase_occurrence(lower_answer, "invent")


def _has_unprohibited_phrase_occurrence(lower_answer: str, phrase: str) -> bool:
    start = 0
    while True:
        index = lower_answer.find(phrase, start)
        if index == -1:
            return False
        prefix = lower_answer[max(0, index - 32) : index]
        safe_prefixes = (
            "cannot ",
            "cannot be ",
            "can't ",
            "can't be ",
            "must not ",
            "must not be ",
            "do not ",
            "does not ",
            "should not ",
            "is not allowed to ",
            "are not allowed to ",
            "not allowed to ",
            "prohibits ",
            "prohibited from ",
        )
        if not any(prefix.endswith(marker) for marker in safe_prefixes):
            return True
        start = index + len(phrase)


def _tool_claim_requires_evidence(context: GroundedAnswerContext, answer: str) -> bool:
    if not context.tool_evidence:
        return False
    lower = answer.casefold()
    if any(code.casefold() in lower for code in context.fact_set.blocked_diagnostic_codes):
        return True
    return any(term in lower for term in ("deterministic validation", "validate_batch", "tool output"))


def _non_blocking_quality_flags(
    context: GroundedAnswerContext,
    draft: GroundedAnswerDraft,
) -> list[str]:
    flags: list[str] = []
    if _has_joined_word_formatting(draft.answer):
        flags.append("draft_unreadable_formatting")
    if _next_action_too_vague(draft.next_safe_action):
        flags.append("draft_next_action_too_vague")
    if _missing_preferred_material_fact(context, draft.answer):
        flags.append("draft_missing_material_baseline_fact")
    return flags


def _has_joined_word_formatting(answer: str) -> bool:
    return bool(re.search(r"\b(?:thebatch|thisbatch|validationfailed|dryrun)\b", answer, re.I))


def _next_action_too_vague(next_action: str) -> bool:
    lower = next_action.casefold().strip()
    vague = {"review", "fix it", "try again", "continue", "proceed"}
    return lower in vague or len(lower.split()) < 3


def _missing_preferred_material_fact(context: GroundedAnswerContext, answer: str) -> bool:
    lower = answer.casefold()
    baseline_lower = context.baseline_response.answer.casefold()
    if "missing_concentration" in baseline_lower and "missing_concentration" not in lower:
        return True
    if "janus_blocked_for_invalid_batch" in baseline_lower and "janus" not in lower:
        return True
    if context.tool_evidence and "deterministic" in baseline_lower and "deterministic" not in lower:
        return True
    return False


def sanitize_prompt_text(text: str | None) -> str:
    """Redact secrets and unbounded pasted payloads before provider prompts."""

    if not text:
        return ""
    sanitized = _BEARER_PATTERN.sub("Bearer [REDACTED]", text)
    sanitized = _APPROVAL_TOKEN_PATTERN.sub(lambda match: _redact_assignment(match.group(0)), sanitized)
    sanitized = _ENV_ASSIGNMENT_PATTERN.sub(lambda match: _redact_assignment(match.group(0)), sanitized)
    sanitized = _SECRET_LIKE_PATTERN.sub("[REDACTED_SECRET]", sanitized)
    lines = sanitized.splitlines()
    if len(lines) > 20 or sum(1 for line in lines if ":" in line) > 8:
        return "\n".join(lines[:20]) + "\n[TRUNCATED_SANITIZED_PAYLOAD]"
    return sanitized


def _redact_assignment(value: str) -> str:
    separator = ":" if ":" in value and "=" not in value else "="
    key = value.split(separator, 1)[0].strip()
    return f"{key}{separator}[REDACTED]"
