"""Optional OpenRouter model adapter for LabFlow agent planning."""

from __future__ import annotations

import json
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, NotRequired, Protocol, TypedDict

from pydantic import ValidationError

from labflow_agent.answer_model import domain_concepts_for_text
from labflow_agent.models import (
    AgentPlan,
    AgentRequest,
    AgentTask,
    JsonDict,
    ModelExecutionMetadata,
    ModelMetadata,
    PlanDiagnostic,
    ProviderAttempt,
    ToolCallMode,
    ToolCallPlan,
)

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
OPENROUTER_ADAPTER_VERSION = "openrouter-adapter-0.1.0"

_ALLOWED_MODEL_TOOL_INTENTS = frozenset({"validate_batch", "explain_exception_code"})
_SENSITIVE_RE = re.compile(r"(sk-or-[A-Za-z0-9_-]+|Bearer\s+[A-Za-z0-9._-]+)", re.IGNORECASE)
_RETRYABLE_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
_RETRYABLE_CODES = frozenset(
    {
        "openrouter_http_error",
        "openrouter_timeout",
        "openrouter_url_error",
        "openrouter_response_json_invalid",
        "openrouter_response_not_object",
        "openrouter_response_missing_choices",
        "openrouter_choice_finish_reason_error",
    }
)
_RETRIEVAL_ALLOWED_TERMS = frozenset(
    {
        "approval",
        "artifact",
        "ancestry",
        "batch",
        "blank",
        "block",
        "blocked",
        "child",
        "commit",
        "concentration",
        "deterministic",
        "diagnostic",
        "do",
        "dry",
        "dry-run",
        "exception",
        "exceptions",
        "guardrail",
        "invent",
        "infer",
        "invalid",
        "janus",
        "missing",
        "not",
        "parent",
        "policy",
        "readiness",
        "ready",
        "relationship",
        "robot",
        "robot-ready",
        "round",
        "rounding",
        "sample",
        "split",
        "standard",
        "tool",
        "validation",
        "workflow",
        "worklist",
        "automation",
        "destination",
        "duplicate",
        "yaml",
        "csv",
        "export",
        "preview",
        "transfer",
        "transfers",
        "rna",
        "requant",
        "re-quant",
        "downstream",
    }
)
_RETRIEVAL_MAX_TOKENS = 12
_RETRIEVAL_MAX_CHARS = 160


class _CorpusRetrievalExpansion(TypedDict):
    family_id: str
    terms: tuple[str, ...]
    source_document_ids: tuple[str, ...]
    all_terms: NotRequired[tuple[str, ...]]
    any_terms: NotRequired[tuple[str, ...]]
    any_term_groups: NotRequired[tuple[tuple[str, ...], ...]]
    concept_groups: NotRequired[tuple[tuple[str, ...], ...]]
    doctrine_rules: NotRequired[tuple[str, ...]]
    supporting_phrases: NotRequired[tuple[str, ...]]
    reason: NotRequired[str]


_CORPUS_RETRIEVAL_EXPANSIONS: tuple[_CorpusRetrievalExpansion, ...] = (
    {
        "family_id": "missing_value_guardrail",
        "concept_groups": (
            ("missing_fact",),
            ("concentration",),
        ),
        "any_term_groups": (
            ("missing", "absent", "unknown"),
            ("concentration", "value"),
            ("guess", "infer", "invent", "fill"),
        ),
        "terms": ("infer", "missing", "concentration", "invalid", "batch", "robot", "readiness", "guardrail", "exception"),
        "source_document_ids": (
            "ai_guardrails_policy.md",
            "batch_readiness_doctrine.md",
            "exception_handling_manual.md",
        ),
        "doctrine_rules": (
            "no_missing_lab_fact_inference",
            "invalid_batch_blocks_robot_readiness",
        ),
        "supporting_phrases": (
            "The AI must not invent missing sample IDs, concentrations, source locations, destination wells, standards, blanks, or JANUS worklist rows.",
            "The AI must not repair a worklist by guessing values.",
            "do not infer a concentration.",
        ),
        "reason": "Maps colloquial missing-value guessing to corpus policy prohibiting inferred lab facts and invalid-batch readiness.",
    },
    {
        "family_id": "ancestry_no_invention",
        "any_term_groups": (
            ("invent", "infer", "assume", "guess"),
            ("ancestry", "parent", "child", "relationship"),
        ),
        "terms": ("ancestry", "parent", "child", "relationship", "invent", "guardrail", "policy"),
        "source_document_ids": (
            "sample_ancestry_policy.md",
            "ai_guardrails_policy.md",
        ),
        "doctrine_rules": (
            "no_invented_ancestry_relationships",
            "no_missing_lab_fact_inference",
        ),
        "supporting_phrases": (
            "The assistant must not invent parent-child relationships or ancestry facts.",
            "Ancestry records must be derived from trusted workflow data.",
        ),
        "reason": "Maps ancestry invention questions to supported negative policy doctrine.",
    },
    {
        "family_id": "dry_run_prerequisite",
        "concept_groups": (
            ("dry_run",),
            ("commit", "approval", "blocked"),
        ),
        "any_term_groups": (
            ("dry", "dry-run"),
            ("run", "preview", "commit", "validation", "prereq"),
        ),
        "terms": ("dry-run", "validation", "approval", "janus", "policy"),
        "source_document_ids": ("ai_guardrails_policy.md", "janus_csv_worklist_spec.md"),
        "doctrine_rules": (
            "dry_run_before_state_change",
            "approval_required_before_commit",
        ),
        "supporting_phrases": (
            "Use `generate_janus_csv` with `dry_run=true` only after deterministic validation passes.",
        ),
        "reason": "Maps dry-run prerequisite questions to validation and approval policy documents.",
    },
    {
        "family_id": "automation_readiness",
        "concept_groups": (("robot_readiness",),),
        "any_term_groups": (("automation",),),
        "terms": ("automation", "validation", "readiness", "robot", "blocked", "policy"),
        "source_document_ids": (
            "batch_readiness_doctrine.md",
            "ai_guardrails_policy.md",
        ),
        "doctrine_rules": (
            "automation_requires_deterministic_validation",
            "invalid_batch_blocks_robot_readiness",
        ),
        "supporting_phrases": (
            "A batch is robot-ready only when deterministic readiness gates pass.",
        ),
        "reason": "Maps low-keyword automation readiness questions to validation and readiness doctrine.",
    },
    {
        "family_id": "blocked_duplicate_yaml",
        "concept_groups": (
            ("duplicate",),
            ("yaml", "blocked"),
        ),
        "any_term_groups": (
            ("duplicate",),
            ("yaml", "well", "destination", "blocked", "validation"),
        ),
        "terms": ("yaml", "blocked", "duplicate", "destination", "deterministic", "validation", "exception"),
        "source_document_ids": (
            "batch_readiness_doctrine.md",
            "exception_handling_manual.md",
        ),
        "doctrine_rules": (
            "duplicate_destination_blocks_batch",
            "domain_validation_beyond_schema",
        ),
        "supporting_phrases": (
            "Duplicate destination occupancy blocks execution.",
        ),
        "reason": "Maps blocked YAML and duplicate-well wording to readiness and exception doctrine.",
    },
    {
        "family_id": "blocked_worklist_export",
        "concept_groups": (
            ("artifact",),
            ("blocked",),
        ),
        "any_term_groups": (
            ("blocked",),
            ("worklist", "export", "csv", "janus"),
        ),
        "terms": ("janus", "csv", "worklist", "blocked", "validation", "readiness"),
        "source_document_ids": (
            "janus_csv_worklist_spec.md",
            "batch_readiness_doctrine.md",
        ),
        "doctrine_rules": (
            "janus_requires_valid_batch",
            "invalid_batch_blocks_robot_readiness",
        ),
        "supporting_phrases": (
            "JANUS-style artifacts are blocked for invalid batches.",
            "A batch is robot-ready only when deterministic readiness gates pass.",
        ),
        "reason": "Maps generic blocked export wording to JANUS gating and batch readiness doctrine.",
    },
    {
        "family_id": "rna_requant_downstream_truth",
        "concept_groups": (
            ("rna_requant",),
            ("downstream", "concentration"),
        ),
        "any_term_groups": (
            ("rna",),
            ("requant", "re", "quant", "downstream", "normalization"),
        ),
        "terms": ("rna", "re-quant", "requant", "downstream", "concentration", "guardrail", "policy"),
        "source_document_ids": (
            "rna_norm_requant_sop.md",
            "ai_guardrails_policy.md",
        ),
        "doctrine_rules": (
            "rna_requant_result_is_downstream_concentration",
            "no_missing_lab_fact_inference",
        ),
        "supporting_phrases": (
            "RNA re-quant result becomes downstream concentration.",
            "The AI must not invent missing sample IDs, concentrations, source locations, destination wells, standards, blanks, or JANUS worklist rows.",
        ),
        "reason": "Maps RNA requant truth questions to re-quant SOP and no-invention policy.",
    },
    {
        "family_id": "invalid_samples_no_transfers",
        "concept_groups": (
            ("invalid_transfer",),
        ),
        "any_term_groups": (
            ("invalid",),
            ("sample", "samples", "transfer", "transfers", "robot"),
        ),
        "terms": ("invalid", "sample", "transfers", "robot", "readiness", "guardrail", "policy"),
        "source_document_ids": (
            "batch_readiness_doctrine.md",
            "ai_guardrails_policy.md",
        ),
        "doctrine_rules": (
            "invalid_samples_generate_no_robot_transfers",
            "janus_requires_valid_batch",
        ),
        "supporting_phrases": (
            "invalid samples still generate no robot transfers",
            "The agent must not generate robot-ready artifacts unless deterministic validation passes.",
        ),
        "reason": "Maps invalid-sample transfer wording to readiness doctrine and robot-artifact guardrails.",
    },
)


class OpenRouterError(RuntimeError):
    """Raised for sanitized OpenRouter provider or transport failures."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        http_status: int | None = None,
        details: dict[str, str | int | float | bool | None] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}
        self.retryable = retryable
        self.attempts: tuple[ProviderAttempt, ...] = ()

    def to_diagnostic(self) -> PlanDiagnostic:
        """Return a sanitized diagnostic suitable for traces and eval reports."""

        return PlanDiagnostic(
            code=self.code,
            message=self.message,
            provider="openrouter",
            http_status=self.http_status,
            details=self.details,
        )


class ChatCompletionClient(Protocol):
    """Small boundary for mocked or real OpenRouter chat-completion calls."""

    def complete(
        self,
        messages: list[JsonDict],
        *,
        model: str | None = None,
        response_format: JsonDict | None = None,
    ) -> "OpenRouterHTTPResponse | JsonDict":
        """Return an OpenAI-compatible chat completion response boundary."""


@dataclass(frozen=True)
class OpenRouterConfig:
    """Configuration for the optional OpenRouter adapter."""

    api_key: str = field(repr=False)
    model: str = DEFAULT_OPENROUTER_MODEL
    base_url: str = DEFAULT_OPENROUTER_BASE_URL
    http_referer: str | None = None
    app_title: str = "LabFlow AI Studio"
    timeout_seconds: float = 30.0
    max_retries: int = 1
    retry_backoff_seconds: float = 1.0
    retry_backoff_multiplier: float = 2.0
    retry_max_backoff_seconds: float = 8.0
    fallback_models: tuple[str, ...] = ()
    enable_metadata: bool = False
    response_format: str = "json_object"


@dataclass(frozen=True)
class OpenRouterHTTPResponse:
    """Sanitized HTTP response boundary for one OpenRouter attempt."""

    status: int
    headers: dict[str, str]
    body_json: JsonDict | None
    body_text_preview: str | None
    elapsed_ms: float


class UrlLibOpenRouterClient:
    """Minimal stdlib OpenRouter HTTP client."""

    def __init__(self, config: OpenRouterConfig) -> None:
        self._config = config

    def complete(
        self,
        messages: list[JsonDict],
        *,
        model: str | None = None,
        response_format: JsonDict | None = None,
    ) -> OpenRouterHTTPResponse:
        url = self._config.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": model or self._config.model,
            "messages": messages,
            "temperature": 0,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self._config.timeout_seconds) as response:
                raw = response.read().decode("utf-8", errors="replace")
                return _http_response_from_raw(
                    status=response.status,
                    headers=dict(response.headers.items()),
                    raw=raw,
                    elapsed_ms=(time.perf_counter() - start) * 1000,
                )
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            return _http_response_from_raw(
                status=exc.code,
                headers=dict(exc.headers.items()) if exc.headers is not None else {},
                raw=raw,
                elapsed_ms=(time.perf_counter() - start) * 1000,
            )
        except TimeoutError as exc:
            raise OpenRouterError(
                "openrouter_timeout",
                f"OpenRouter request timed out after {self._config.timeout_seconds:g} seconds.",
                details={
                    "timeout_seconds": self._config.timeout_seconds,
                    "elapsed_ms": round((time.perf_counter() - start) * 1000, 3),
                },
                retryable=True,
            ) from exc
        except socket.timeout as exc:
            raise OpenRouterError(
                "openrouter_timeout",
                f"OpenRouter request timed out after {self._config.timeout_seconds:g} seconds.",
                details={
                    "timeout_seconds": self._config.timeout_seconds,
                    "elapsed_ms": round((time.perf_counter() - start) * 1000, 3),
                },
                retryable=True,
            ) from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", None)
            reason_type = type(reason).__name__ if reason is not None else "unknown"
            raise OpenRouterError(
                "openrouter_url_error",
                f"OpenRouter request failed before receiving a response ({reason_type}).",
                details={
                    "reason_type": reason_type,
                    "elapsed_ms": round((time.perf_counter() - start) * 1000, 3),
                },
                retryable=True,
            ) from exc

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        if self._config.http_referer:
            headers["HTTP-Referer"] = self._config.http_referer
        if self._config.app_title:
            headers["X-Title"] = self._config.app_title
        if self._config.enable_metadata:
            headers["X-OpenRouter-Metadata"] = "enabled"
        return headers


class OpenRouterModelAdapter:
    """OpenRouter-backed implementation of the LabFlow model adapter."""

    def __init__(
        self,
        config: OpenRouterConfig,
        *,
        client: ChatCompletionClient | None = None,
    ) -> None:
        if not config.api_key.strip():
            raise OpenRouterError(
                "openrouter_missing_api_key",
                "OPENROUTER_API_KEY is required when OpenRouter is selected.",
            )
        self._config = config
        self._client = client or UrlLibOpenRouterClient(config)
        self._execution_metadata: ModelExecutionMetadata | None = None
        self.metadata = ModelMetadata(
            model_id=config.model,
            version=OPENROUTER_ADAPTER_VERSION,
            provider="openrouter",
        )

    def last_execution_metadata(self) -> ModelExecutionMetadata | None:
        """Return sanitized metadata for the most recent OpenRouter planning call."""

        return self._execution_metadata

    def plan(self, request: AgentRequest) -> AgentPlan:
        self._execution_metadata = None
        try:
            content, metadata = complete_chat_content(
                config=self._config,
                client=self._client,
                messages=_messages_for_request(request),
                schema=AgentPlan.model_json_schema(),
            )
            self._execution_metadata = metadata
            raw_plan = json.loads(content)
            if not isinstance(raw_plan, dict):
                return _unsupported_plan(
                    request,
                    "OpenRouter message content did not contain a JSON object plan.",
                    diagnostic=_diagnostic(
                        "model_plan_not_object",
                        "OpenRouter message content decoded to a non-object plan.",
                    ),
                )
            model_plan = AgentPlan.model_validate(raw_plan)
        except json.JSONDecodeError:
            return _normalize_model_plan(
                _unsupported_plan(
                    request,
                    "OpenRouter message content was not valid AgentPlan JSON.",
                    diagnostic=_diagnostic(
                        "model_plan_json_invalid",
                        "OpenRouter message content was not valid AgentPlan JSON.",
                    ),
                ),
                request,
            )
        except OpenRouterError as exc:
            self._execution_metadata = _metadata_from_error(self._config, exc)
            return _normalize_model_plan(
                _unsupported_plan(
                    request,
                    exc.message,
                    diagnostic=exc.to_diagnostic(),
                ),
                request,
            )
        except ValidationError as exc:
            return _normalize_model_plan(
                _unsupported_plan(
                    request,
                    "OpenRouter message content did not match the AgentPlan schema.",
                    diagnostic=_diagnostic(
                        "model_plan_schema_invalid",
                        (
                            "OpenRouter message content did not match the AgentPlan schema "
                            f"({exc.error_count()} validation errors)."
                        ),
                    ),
                ),
                request,
            )
        except (KeyError, TypeError, ValueError) as exc:
            return _normalize_model_plan(
                _unsupported_plan(
                    request,
                    "OpenRouter plan could not be normalized.",
                    diagnostic=_diagnostic(
                        "model_plan_normalization_error",
                        f"OpenRouter plan normalization failed ({type(exc).__name__}).",
                    ),
                ),
                request,
            )

        return _normalize_model_plan(_normalize_retrieval_query(model_plan, request), request)


def _messages_for_request(request: AgentRequest) -> list[JsonDict]:
    system = (
        "You are planning for LabFlow AI Studio. Return only one JSON object. "
        "LabFlow is synthetic and non-clinical. Deterministic validators own lab truth. "
        "Do not invent sample IDs, concentrations, wells, standards, blanks, workflow YAML, "
        "batch IDs, file paths, or JANUS artifacts. You may suggest only these tool intents: "
        "validate_batch and explain_exception_code. Use read_only mode. "
        "Route corpus-policy questions about default standards, blank counts, guardrails, "
        "JANUS dry-run prerequisites, split workflow doctrine, units, ancestry, throughput, "
        "or DSL rules to answer_workflow_question with no tool_calls unless trusted "
        "workflow_yaml or a diagnostic_code is supplied in the user payload. "
        "Only choose validate_batch when has_workflow_yaml is true. "
        "Only choose explain_diagnostic when has_diagnostic_code is true. "
        "For questions asking what the assistant should do before a tool action, answer from "
        "policy; do not emit a tool call unless the required trusted request data is present. "
        "Questions asking whether the assistant can invent, infer, assume, fill in, or fix "
        "missing lab facts are answer_workflow_question policy questions, not unsupported "
        "requests; answer them from guardrail or ancestry doctrine with no tool_calls. "
        "Use unsupported only for requests outside the LabFlow corpus or impossible without "
        "inventing missing lab facts. "
        "The JSON object must use this exact shape: "
        '{"task":"answer_workflow_question","rationale":"short reason",'
        '"retrieval_query":"search query","tool_calls":[],"unsupported_reason":null}. '
        "Allowed task values are answer_workflow_question, explain_diagnostic, validate_batch, "
        "recommend_safe_next_action, and unsupported. "
        "Tool calls, when present, must use this shape with empty arguments only: "
        '{"tool_name":"explain_exception_code","arguments":{},'
        '"mode":"read_only","reason":"short reason"}.'
    )
    user_payload = {
        "question": request.question,
        "has_workflow_yaml": request.workflow_yaml is not None,
        "has_batch_id": request.batch_id is not None,
        "has_diagnostic_code": request.diagnostic_code is not None,
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user_payload, sort_keys=True)},
    ]


def complete_chat_content(
    *,
    config: OpenRouterConfig,
    client: ChatCompletionClient,
    messages: list[JsonDict],
    schema: JsonDict | None,
) -> tuple[str, ModelExecutionMetadata]:
    """Complete a chat request with bounded retry/failover and sanitized provenance."""

    attempts: list[ProviderAttempt] = []
    models = (config.model, *config.fallback_models)
    max_attempts = config.max_retries + 1
    last_error: OpenRouterError | None = None
    for model_index, requested_model in enumerate(models):
        for attempt_number in range(1, max_attempts + 1):
            try:
                response = _call_client(
                    client,
                    messages,
                    model=requested_model,
                    response_format=_response_format(config, schema),
                )
                content = _content_from_response(response)
                attempts.append(
                    ProviderAttempt(
                        attempt_index=len(attempts) + 1,
                        requested_model_id=requested_model,
                        served_model_id=_served_model_id(response.body_json),
                        http_status=response.status,
                        elapsed_ms=response.elapsed_ms,
                    )
                )
                metadata = _execution_metadata(
                    config=config,
                    requested_model=requested_model,
                    response=response,
                    attempts=attempts,
                    failover_count=model_index,
                )
                return content, metadata
            except OpenRouterError as exc:
                last_error = exc
                attempts.append(
                    ProviderAttempt(
                        attempt_index=len(attempts) + 1,
                        requested_model_id=requested_model,
                        served_model_id=str(exc.details.get("served_model_id"))
                        if exc.details.get("served_model_id")
                        else None,
                        diagnostic_code=exc.code,
                        http_status=exc.http_status,
                        retryable=exc.retryable,
                        elapsed_ms=float(exc.details.get("elapsed_ms") or 0),
                    )
                )
                exc.details.update(_attempt_details(config, attempts, model_index))
                exc.attempts = tuple(attempts)
                if not exc.retryable:
                    raise exc
                if attempt_number < max_attempts:
                    _sleep_before_retry(config, exc, attempt_number)
                    continue
                if model_index + 1 < len(models):
                    continue
                raise exc

    if last_error is not None:
        raise last_error
    raise OpenRouterError(
        "openrouter_no_models_configured",
        "OpenRouter had no configured model to call.",
        details={"attempt_count": 0},
    )


def _content_from_completion(completion: JsonDict | OpenRouterHTTPResponse) -> str:
    """Extract content from a completion envelope for legacy test callers."""

    return _content_from_response(_coerce_response(completion))


def _content_from_response(response: OpenRouterHTTPResponse) -> str:
    completion = response.body_json
    if completion is None:
        raise OpenRouterError(
            "openrouter_response_json_invalid",
            "OpenRouter response envelope was not valid JSON.",
            http_status=response.status,
            details=_response_details(response),
            retryable=True,
        )
    if response.status >= 400:
        raise _provider_error_from_response(response)
    error = completion.get("error")
    if isinstance(error, dict):
        raise _provider_error_from_response(response)
    choices = completion.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenRouterError(
            "openrouter_response_missing_choices",
            "OpenRouter response envelope did not include choices.",
            http_status=response.status,
            details=_response_details(response),
            retryable=True,
        )
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise OpenRouterError(
            "openrouter_response_invalid_choice",
            "OpenRouter response choice was not a JSON object.",
            http_status=response.status,
            details=_response_details(response),
            retryable=False,
        )
    finish_reason = first_choice.get("finish_reason")
    if finish_reason == "error":
        raise OpenRouterError(
            "openrouter_choice_finish_reason_error",
            "OpenRouter returned a choice with finish_reason=error.",
            http_status=response.status,
            details=_response_details(response),
            retryable=True,
        )
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise OpenRouterError(
            "openrouter_response_missing_message",
            "OpenRouter response choice did not include a message object.",
            http_status=response.status,
            details=_response_details(response),
            retryable=False,
        )
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise OpenRouterError(
            "openrouter_response_empty_content",
            "OpenRouter response message content was empty.",
            http_status=response.status,
            details=_response_details(response),
            retryable=False,
        )
    return content


def _call_client(
    client: ChatCompletionClient,
    messages: list[JsonDict],
    *,
    model: str,
    response_format: JsonDict | None,
) -> OpenRouterHTTPResponse:
    try:
        response = client.complete(messages, model=model, response_format=response_format)
    except TypeError:
        response = client.complete(messages)  # compatibility for older local stubs
    return _coerce_response(response)


def _coerce_response(response: JsonDict | OpenRouterHTTPResponse) -> OpenRouterHTTPResponse:
    if isinstance(response, OpenRouterHTTPResponse):
        return response
    return OpenRouterHTTPResponse(
        status=200,
        headers={},
        body_json=response,
        body_text_preview=None,
        elapsed_ms=0,
    )


def _http_response_from_raw(
    *,
    status: int,
    headers: dict[str, str],
    raw: str,
    elapsed_ms: float,
) -> OpenRouterHTTPResponse:
    preview: str | None = None
    try:
        decoded: Any = json.loads(raw)
    except json.JSONDecodeError:
        decoded = None
        preview = _sanitize_preview(raw)
    return OpenRouterHTTPResponse(
        status=status,
        headers=_sanitized_headers(headers),
        body_json=decoded if isinstance(decoded, dict) else None,
        body_text_preview=preview,
        elapsed_ms=elapsed_ms,
    )


def _provider_error_from_response(response: OpenRouterHTTPResponse) -> OpenRouterError:
    body = response.body_json or {}
    error = body.get("error") if isinstance(body, dict) else None
    error_code = None
    error_message = None
    metadata_keys = ""
    if isinstance(error, dict):
        raw_code = error.get("code")
        error_code = str(raw_code) if raw_code is not None else None
        raw_message = error.get("message")
        error_message = _sanitize_preview(str(raw_message)) if raw_message is not None else None
        metadata = error.get("metadata")
        if isinstance(metadata, dict):
            metadata_keys = ",".join(sorted(str(key) for key in metadata.keys()))
    code = _labflow_code_for_provider_error(response.status, error_code)
    message = f"OpenRouter provider response failed with HTTP {response.status}."
    if error_message:
        message = f"OpenRouter provider error: {error_message}"
    details = _response_details(response)
    if error_code is not None:
        details["provider_error_code"] = error_code
    if error_message is not None:
        details["provider_error_message"] = error_message
    if metadata_keys:
        details["provider_error_metadata_keys"] = metadata_keys
    provider_status = _provider_status_code(error_code)
    retryable = (
        response.status in _RETRYABLE_HTTP_STATUSES
        or (provider_status is not None and provider_status in _RETRYABLE_HTTP_STATUSES)
        or code in _RETRYABLE_CODES
    )
    return OpenRouterError(
        code,
        message,
        http_status=response.status,
        details=details,
        retryable=retryable,
    )


def _labflow_code_for_provider_error(status: int, provider_code: str | None) -> str:
    provider_status = _provider_status_code(provider_code)
    effective_status = provider_status or status
    if effective_status == 408:
        return "openrouter_provider_timeout"
    if effective_status == 429:
        return "openrouter_rate_limited"
    if effective_status in {500, 502, 503, 504}:
        return "openrouter_provider_unavailable"
    if status >= 400:
        return "openrouter_http_error"
    if provider_code:
        return "openrouter_provider_error"
    return "openrouter_http_error"


def _provider_status_code(provider_code: str | None) -> int | None:
    if provider_code is None:
        return None
    try:
        parsed = int(provider_code)
    except ValueError:
        return None
    return parsed if 100 <= parsed <= 599 else None


def _response_details(response: OpenRouterHTTPResponse) -> dict[str, str | int | float | bool | None]:
    body = response.body_json or {}
    details: dict[str, str | int | float | bool | None] = {
        "elapsed_ms": round(response.elapsed_ms, 3),
        "envelope_keys": ",".join(sorted(str(key) for key in body.keys())) if body else "",
    }
    retry_after = _retry_after_seconds(response.headers)
    if retry_after is not None:
        details["retry_after_seconds"] = retry_after
    if response.body_json is None and response.body_text_preview:
        details["body_text_preview"] = response.body_text_preview
    served_model = _served_model_id(body)
    if served_model:
        details["served_model_id"] = served_model
    return details


def _attempt_details(
    config: OpenRouterConfig,
    attempts: list[ProviderAttempt],
    failover_count: int,
) -> dict[str, str | int | float | bool | None]:
    final_requested_model_id = attempts[-1].requested_model_id if attempts else config.model
    return {
        "attempt_count": len(attempts),
        "max_attempts": config.max_retries + 1,
        "retry_count": max(0, len(attempts) - 1 - failover_count),
        "failover_count": failover_count,
        "final_requested_model_id": final_requested_model_id,
        "metadata_enabled": config.enable_metadata,
    }


def _execution_metadata(
    *,
    config: OpenRouterConfig,
    requested_model: str,
    response: OpenRouterHTTPResponse,
    attempts: list[ProviderAttempt],
    failover_count: int,
) -> ModelExecutionMetadata:
    return ModelExecutionMetadata(
        requested_model_id=config.model,
        final_requested_model_id=requested_model,
        served_model_id=_served_model_id(response.body_json),
        attempts=tuple(attempts),
        retry_count=max(0, len(attempts) - 1 - failover_count),
        failover_count=failover_count,
    )


def _metadata_from_error(
    config: OpenRouterConfig,
    error: OpenRouterError,
) -> ModelExecutionMetadata | None:
    attempt_count = int(error.details.get("attempt_count") or 0)
    if attempt_count <= 0:
        return None
    if error.attempts:
        attempts = error.attempts
    else:
        attempts = (
            ProviderAttempt(
                attempt_index=attempt_count,
                requested_model_id=str(error.details.get("final_requested_model_id") or config.model),
                diagnostic_code=error.code,
                http_status=error.http_status,
                retryable=error.retryable,
                elapsed_ms=float(error.details.get("elapsed_ms") or 0),
            ),
        )
    return ModelExecutionMetadata(
        requested_model_id=config.model,
        final_requested_model_id=str(error.details.get("final_requested_model_id") or config.model),
        attempts=attempts,
        retry_count=int(error.details.get("retry_count") or 0),
        failover_count=int(error.details.get("failover_count") or 0),
    )


def _response_format(config: OpenRouterConfig, schema: JsonDict | None) -> JsonDict | None:
    mode = config.response_format.strip().casefold()
    if mode in {"", "off", "none"}:
        return None
    if mode == "json_schema" and schema is not None:
        return {
            "type": "json_schema",
            "json_schema": {"name": "labflow_structured_output", "strict": True, "schema": schema},
        }
    return {"type": "json_object"}


def _sleep_before_retry(config: OpenRouterConfig, error: OpenRouterError, attempt_number: int) -> None:
    retry_after = error.details.get("retry_after_seconds")
    if isinstance(retry_after, (int, float)):
        delay = float(retry_after)
    else:
        delay = config.retry_backoff_seconds * (config.retry_backoff_multiplier ** (attempt_number - 1))
    delay = max(0.0, min(delay, config.retry_max_backoff_seconds))
    if delay > 0:
        time.sleep(delay)


def _retry_after_seconds(headers: dict[str, str]) -> float | None:
    value = next((val for key, val in headers.items() if key.casefold() == "retry-after"), None)
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _served_model_id(body: JsonDict | None) -> str | None:
    if not isinstance(body, dict):
        return None
    model = body.get("model")
    return str(model) if isinstance(model, str) and model else None


def _sanitize_preview(value: str) -> str:
    return _SENSITIVE_RE.sub("[REDACTED]", value).replace("\n", " ")[:240]


def _sanitized_headers(headers: dict[str, str]) -> dict[str, str]:
    allowed = {"retry-after", "x-request-id", "cf-ray"}
    return {key: value for key, value in headers.items() if key.casefold() in allowed}


def _normalize_model_plan(model_plan: AgentPlan, request: AgentRequest) -> AgentPlan:
    if (
        model_plan.task is AgentTask.UNSUPPORTED
        and _unsupported_is_supported_policy_question(request.question)
    ):
        model_plan = model_plan.model_copy(
            update={
                "task": AgentTask.ANSWER_WORKFLOW_QUESTION,
                "rationale": (
                    "The request asks for a supported negative policy answer from "
                    "LabFlow guardrail or ancestry doctrine."
                ),
                "tool_calls": (),
                "unsupported_reason": None,
            }
        )

    if request.workflow_yaml is not None:
        invalid_model_intents = tuple(
            call for call in model_plan.tool_calls if not _tool_intent_has_safe_shape(call)
        )
        rationale = "Concrete workflow YAML was supplied, so deterministic validation is required."
        if invalid_model_intents:
            rationale = (
                "Model-supplied tool arguments or unsafe intents were rejected; "
                "concrete workflow YAML still requires deterministic validation."
            )
        return AgentPlan(
            task=AgentTask.VALIDATE_BATCH,
            rationale=rationale,
            retrieval_query=model_plan.retrieval_query or request.question,
            tool_calls=(
                ToolCallPlan(
                    tool_name="validate_batch",
                    arguments={
                        "batch_id": request.batch_id,
                        "workflow_yaml": request.workflow_yaml,
                    },
                    mode=ToolCallMode.READ_ONLY,
                    reason="Validate supplied workflow data before making any claim about it.",
                ),
            ),
            diagnostic=(
                _unsafe_tool_intent_diagnostic() if invalid_model_intents else model_plan.diagnostic
            ),
        )

    bound_calls: list[ToolCallPlan] = []
    for call in model_plan.tool_calls:
        bound_call = _bind_tool_intent(call, request)
        if bound_call is None:
            return _unsupported_plan(
                request,
                "Model suggested tools or arguments outside the Stage 18.1 safe intent surface.",
                diagnostic=_unsafe_tool_intent_diagnostic(),
            )
        bound_calls.append(bound_call)

    if model_plan.tool_calls and not bound_calls:
        return _unsupported_plan(
            request,
            "Model suggested tools or arguments outside the Stage 18.1 safe intent surface.",
            diagnostic=_unsafe_tool_intent_diagnostic(),
        )

    return model_plan.model_copy(update={"tool_calls": tuple(bound_calls)})


def _unsupported_is_supported_policy_question(question: str) -> bool:
    concepts = set(domain_concepts_for_text(question))
    lowered = question.casefold()
    negative_policy_terms = (
        "invent",
        "infer",
        "assume",
        "guess",
        "fill in",
        "fabricate",
        "make up",
    )
    if "missing_fact" in concepts:
        return True
    if any(term in lowered for term in negative_policy_terms) and any(
        term in lowered
        for term in (
            "ancestry",
            "parent",
            "child",
            "relationship",
            "concentration",
            "sample",
            "well",
            "blank",
            "standard",
            "janus",
            "worklist",
        )
    ):
        return True
    return False


def _normalize_retrieval_query(model_plan: AgentPlan, request: AgentRequest) -> AgentPlan:
    sanitized = _sanitize_retrieval_expansion(request.question, model_plan.retrieval_query)
    corpus_expansion = _corpus_retrieval_expansion(request.question, model_plan.retrieval_query)
    accepted_terms = _dedupe_terms((*sanitized["accepted_terms"], *corpus_expansion["accepted_terms"]))
    if not sanitized["accepted_terms"]:
        if not corpus_expansion["accepted_terms"]:
            return model_plan.model_copy(update={"retrieval_query": request.question})
    retrieval_query = f"{request.question} {' '.join(accepted_terms)}"
    if sanitized["rejected_terms"]:
        policy_action = "accepted_with_rejections"
    elif corpus_expansion["accepted_terms"] and not sanitized["accepted_terms"]:
        policy_action = "corpus_expanded"
    elif corpus_expansion["accepted_terms"]:
        policy_action = "accepted_with_corpus_expansion"
    else:
        policy_action = "accepted"
    diagnostic = _diagnostic(
        "model_retrieval_query_sanitized",
        "Model retrieval query expansion was sanitized before retrieval.",
        details={
            "retrieval_query_source": "model_sanitized",
            "retrieval_query_policy_action": policy_action,
            "model_retrieval_query_preview": retrieval_query[:_RETRIEVAL_MAX_CHARS],
            "accepted_terms": ",".join(accepted_terms),
            "rejected_terms": ",".join(sanitized["rejected_terms"]),
            "corpus_expansion_terms": ",".join(corpus_expansion["accepted_terms"]),
            "corpus_expansion_families": ",".join(corpus_expansion["family_ids"]),
            "corpus_expansion_source_documents": ",".join(corpus_expansion["source_document_ids"]),
            "corpus_expansion_doctrine_rules": ",".join(corpus_expansion["doctrine_rules"]),
            "corpus_expansion_supporting_phrases": " | ".join(
                corpus_expansion["supporting_phrases"]
            ),
        },
    )
    return model_plan.model_copy(
        update={
            "retrieval_query": retrieval_query,
            "diagnostic": diagnostic,
        }
    )


def _sanitize_retrieval_expansion(question: str, retrieval_query: str) -> dict[str, tuple[str, ...]]:
    if not retrieval_query or retrieval_query.strip() == question.strip():
        return {"accepted_terms": (), "rejected_terms": ()}
    raw_terms = _retrieval_terms(retrieval_query)
    question_terms = set(_retrieval_terms(question))
    accepted: list[str] = []
    rejected: list[str] = []
    for term in raw_terms:
        if term in question_terms:
            continue
        if _retrieval_term_is_unsafe(term):
            rejected.append(term)
            continue
        if term not in _RETRIEVAL_ALLOWED_TERMS:
            rejected.append(term)
            continue
        if term not in accepted:
            accepted.append(term)
        if len(accepted) >= _RETRIEVAL_MAX_TOKENS:
            break
    expansion = " ".join(accepted)
    if len(expansion) > _RETRIEVAL_MAX_CHARS:
        accepted = _retrieval_terms(expansion[:_RETRIEVAL_MAX_CHARS])
    return {"accepted_terms": tuple(accepted), "rejected_terms": tuple(rejected)}


def _corpus_retrieval_expansion(question: str, retrieval_query: str) -> dict[str, tuple[str, ...]]:
    """Return deterministic corpus-approved retrieval expansion terms."""

    query_text = " ".join((question, retrieval_query))
    query_terms = set(_retrieval_terms(query_text.replace("-", " ")))
    query_concepts = set(domain_concepts_for_text(query_text))
    accepted_terms: list[str] = []
    family_ids: list[str] = []
    source_document_ids: list[str] = []
    doctrine_rules: list[str] = []
    supporting_phrases: list[str] = []
    for family in _CORPUS_RETRIEVAL_EXPANSIONS:
        all_terms = {
            str(term).casefold().replace("-", " ")
            for term in family.get("all_terms", ())
        }
        any_terms = {
            str(term).casefold().replace("-", " ")
            for term in family.get("any_terms", ())
        }
        any_term_groups = tuple(
            {
                str(term).casefold().replace("-", " ")
                for term in group
            }
            for group in family.get("any_term_groups", ())
        )
        concept_groups = tuple(
            {str(concept).casefold() for concept in group}
            for group in family.get("concept_groups", ())
        )
        term_match = True
        if all_terms and not all_terms.issubset(query_terms):
            term_match = False
        if any_terms and not query_terms.intersection(any_terms):
            term_match = False
        if any_term_groups and not all(query_terms.intersection(group) for group in any_term_groups):
            term_match = False
        concept_match = bool(concept_groups) and all(
            query_concepts.intersection(group) for group in concept_groups
        )
        if concept_groups:
            matched = concept_match or (
                term_match and (bool(all_terms) or bool(any_terms) or bool(any_term_groups))
            )
        else:
            matched = term_match
        if not matched:
            continue
        family_ids.append(str(family["family_id"]))
        for source_id in family["source_document_ids"]:
            if str(source_id) not in source_document_ids:
                source_document_ids.append(str(source_id))
        for rule in family.get("doctrine_rules", ()):
            if str(rule) not in doctrine_rules:
                doctrine_rules.append(str(rule))
        for phrase in family.get("supporting_phrases", ()):
            if str(phrase) not in supporting_phrases:
                supporting_phrases.append(str(phrase))
        for term in family["terms"]:
            term_text = str(term)
            if _retrieval_term_is_unsafe(term_text):
                continue
            if term_text not in _RETRIEVAL_ALLOWED_TERMS:
                continue
            if term_text not in accepted_terms:
                accepted_terms.append(term_text)
    return {
        "accepted_terms": tuple(accepted_terms),
        "family_ids": tuple(family_ids),
        "source_document_ids": tuple(source_document_ids),
        "doctrine_rules": tuple(doctrine_rules),
        "supporting_phrases": tuple(supporting_phrases),
    }


def _dedupe_terms(terms: tuple[str, ...]) -> tuple[str, ...]:
    deduped: list[str] = []
    for term in terms:
        if term not in deduped:
            deduped.append(term)
        if len(deduped) >= _RETRIEVAL_MAX_TOKENS:
            break
    expansion = " ".join(deduped)
    if len(expansion) > _RETRIEVAL_MAX_CHARS:
        return tuple(_retrieval_terms(expansion[:_RETRIEVAL_MAX_CHARS]))
    return tuple(deduped)


def _retrieval_terms(text: str) -> list[str]:
    normalized = text.casefold().replace("_", " ")
    return [
        term.strip("?:.,;!()[]{}\"'")
        for term in normalized.split()
        if term.strip("?:.,;!()[]{}\"'")
    ]


def _retrieval_term_is_unsafe(term: str) -> bool:
    if _MEASURE_LIKE(term) or _WELL_LIKE(term) or "/" in term or "\\" in term:
        return True
    if "token" in term or "key" in term:
        return True
    return False


def _MEASURE_LIKE(term: str) -> bool:
    return bool(re.search(r"\d+(?:\.\d+)?(?:ng|ul|µl|ng/ul|ng_per_ul)?", term))


def _WELL_LIKE(term: str) -> bool:
    return bool(re.fullmatch(r"[a-h](?:[1-9]|1[0-2])", term))


def _bind_tool_intent(call: ToolCallPlan, request: AgentRequest) -> ToolCallPlan | None:
    if not _tool_intent_has_safe_shape(call):
        return None

    if call.tool_name == "validate_batch":
        if request.workflow_yaml is None:
            return None
        return ToolCallPlan(
            tool_name="validate_batch",
            arguments={"batch_id": request.batch_id, "workflow_yaml": request.workflow_yaml},
            reason=call.reason,
        )

    if call.tool_name == "explain_exception_code":
        if request.diagnostic_code is None:
            return None
        return ToolCallPlan(
            tool_name="explain_exception_code",
            arguments={"exception_code": request.diagnostic_code},
            reason=call.reason,
        )

    return None


def _tool_intent_has_safe_shape(call: ToolCallPlan) -> bool:
    return (
        call.tool_name in _ALLOWED_MODEL_TOOL_INTENTS
        and call.mode is ToolCallMode.READ_ONLY
        and not call.arguments
    )


def _unsupported_plan(
    request: AgentRequest,
    reason: str,
    *,
    diagnostic: PlanDiagnostic | None = None,
) -> AgentPlan:
    return AgentPlan(
        task=AgentTask.UNSUPPORTED,
        rationale=reason,
        retrieval_query=request.question,
        unsupported_reason=reason,
        diagnostic=diagnostic,
    )


def _diagnostic(
    code: str,
    message: str,
    *,
    http_status: int | None = None,
    details: dict[str, str | int | float | bool | None] | None = None,
) -> PlanDiagnostic:
    return PlanDiagnostic(
        code=code,
        message=message,
        provider="openrouter",
        http_status=http_status,
        details=details or {},
    )


def _unsafe_tool_intent_diagnostic() -> PlanDiagnostic:
    return _diagnostic(
        "model_tool_intent_unsafe",
        "Model suggested tools, modes, or arguments outside the Stage 18.1 safe intent surface.",
    )
