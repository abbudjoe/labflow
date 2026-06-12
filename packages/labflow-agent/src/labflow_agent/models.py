"""Typed models for the controlled LabFlow agent runtime."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


JsonDict = dict[str, Any]
DiagnosticDetailValue = str | int | float | bool | None


class AgentTask(StrEnum):
    """Supported high-level agent tasks for Stage 9."""

    ANSWER_WORKFLOW_QUESTION = "answer_workflow_question"
    EXPLAIN_DIAGNOSTIC = "explain_diagnostic"
    VALIDATE_BATCH = "validate_batch"
    RECOMMEND_SAFE_NEXT_ACTION = "recommend_safe_next_action"
    EXPLAIN_QC_FAILURE = "explain_qc_failure"
    UNSUPPORTED = "unsupported"


class ToolCallMode(StrEnum):
    """Execution mode requested for a tool call."""

    READ_ONLY = "read_only"
    DRY_RUN = "dry_run"
    COMMIT = "commit"


class ToolCallPlan(BaseModel):
    """One deterministic tool call selected by the planner."""

    model_config = ConfigDict(frozen=True)

    tool_name: str = Field(min_length=1)
    arguments: JsonDict = Field(default_factory=dict)
    mode: ToolCallMode = ToolCallMode.READ_ONLY
    reason: str = Field(min_length=1)


class PlanDiagnostic(BaseModel):
    """Sanitized planner/provider diagnostic for traces and eval reports."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    provider: str | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    details: dict[str, DiagnosticDetailValue] = Field(default_factory=dict)


class ProviderAttempt(BaseModel):
    """Sanitized provider attempt metadata for traces and eval reports."""

    model_config = ConfigDict(frozen=True)

    attempt_index: int = Field(ge=1)
    requested_model_id: str = Field(min_length=1)
    served_model_id: str | None = None
    diagnostic_code: str | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    retryable: bool = False
    elapsed_ms: float = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class ModelExecutionMetadata(BaseModel):
    """Sanitized execution provenance for optional model providers."""

    model_config = ConfigDict(frozen=True)

    requested_model_id: str = Field(min_length=1)
    final_requested_model_id: str = Field(min_length=1)
    served_model_id: str | None = None
    attempts: tuple[ProviderAttempt, ...] = ()
    retry_count: int = Field(default=0, ge=0)
    failover_count: int = Field(default=0, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class AgentPlan(BaseModel):
    """Structured plan produced before any tool is executed."""

    model_config = ConfigDict(frozen=True)

    task: AgentTask
    rationale: str = Field(min_length=1)
    retrieval_query: str
    tool_calls: tuple[ToolCallPlan, ...] = ()
    unsupported_reason: str | None = None
    diagnostic: PlanDiagnostic | None = None


class AgentRequest(BaseModel):
    """Input to the LabFlow agent runtime."""

    model_config = ConfigDict(frozen=True)

    question: str = Field(min_length=1)
    workflow_yaml: str | None = None
    batch_id: str | None = None
    diagnostic_code: str | None = None
    qc_csv: str | None = None
    lineage_csv: str | None = None
    sample_id: str | None = None


class ModelMetadata(BaseModel):
    """Versioned model adapter metadata."""

    model_config = ConfigDict(frozen=True)

    model_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    provider: str = Field(min_length=1)


class ModelAdapter(Protocol):
    """Planner-capable model adapter interface."""

    metadata: ModelMetadata

    def plan(self, request: AgentRequest) -> AgentPlan:
        """Return a structured agent plan."""


class ModelExecutionMetadataProvider(Protocol):
    """Optional provider execution metadata surface."""

    def last_execution_metadata(self) -> ModelExecutionMetadata | None:
        """Return sanitized metadata for the most recent provider execution."""


class ExecutedToolCall(BaseModel):
    """A completed deterministic tool call and structured result."""

    model_config = ConfigDict(frozen=True)

    tool_name: str = Field(min_length=1)
    arguments: JsonDict
    mode: ToolCallMode
    result: JsonDict
    audit_event_id: str | None = None


class AgentTrace(BaseModel):
    """Trace metadata for one agent request."""

    model_config = ConfigDict(frozen=True)

    trace_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    prompt_id: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    prompt_sha256: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    model_provider: str = Field(min_length=1)
    model_diagnostic: PlanDiagnostic | None = None
    answer_composer_diagnostic: PlanDiagnostic | None = None
    model_execution: ModelExecutionMetadata | None = None
    answer_composer_execution: ModelExecutionMetadata | None = None
    answer_composer_fallback: bool = False
    answer_composer_final_answer_source: str = Field(default="deterministic_baseline", min_length=1)
    retrieved_chunk_ids: tuple[str, ...] = ()
    tool_calls: tuple[str, ...] = ()
    latency_ms: float = Field(ge=0)
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    outcome_status: str = Field(min_length=1)


class SourceChunk(BaseModel):
    """Citation-ready source chunk metadata returned by the agent."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    title: str = Field(min_length=1)
    section_path: tuple[str, ...] = ()


class AgentResponse(BaseModel):
    """Final grounded agent response."""

    model_config = ConfigDict(frozen=True)

    answer: str = Field(min_length=1)
    task: AgentTask
    plan: AgentPlan
    sources: tuple[SourceChunk, ...] = ()
    tool_calls: tuple[ExecutedToolCall, ...] = ()
    next_safe_action: str
    blocked_reason: str | None = None
    unsupported: bool = False
    trace: AgentTrace | None = None

    def to_json_dict(self) -> JsonDict:
        return self.model_dump(mode="json")
