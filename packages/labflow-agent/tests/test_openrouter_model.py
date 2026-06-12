from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from labflow_agent import AgentRequest, AgentTask, ToolCallMode
from labflow_agent.intent_router import EvidenceIntent, apply_tool_intent_overlay, decide_tool_intent
from labflow_agent.models import AgentPlan
from labflow_agent.openrouter import (
    OpenRouterConfig,
    OpenRouterError,
    OpenRouterHTTPResponse,
    OpenRouterModelAdapter,
    UrlLibOpenRouterClient,
    _CORPUS_RETRIEVAL_EXPANSIONS,
    _corpus_retrieval_expansion,
    _http_response_from_raw,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


class StubClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.messages: list[dict[str, Any]] = []

    def complete(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        self.messages = messages
        return {"choices": [{"message": {"content": self.content}}]}


class StubPayloadClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def complete(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        return self.payload


class StubErrorClient:
    def complete(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        raise OpenRouterError(
            "openrouter_timeout",
            "OpenRouter request timed out after 20 seconds.",
        )


class SequenceClient:
    def __init__(self, responses: list[dict[str, Any] | OpenRouterHTTPResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any] | OpenRouterHTTPResponse:
        self.calls.append({"messages": messages, "model": model, "response_format": response_format})
        return self.responses.pop(0)


def _adapter_for_plan(plan: dict[str, Any]) -> OpenRouterModelAdapter:
    return OpenRouterModelAdapter(
        OpenRouterConfig(api_key="test-key"),
        client=StubClient(json.dumps(plan)),
    )


def test_openrouter_config_repr_does_not_expose_api_key() -> None:
    config = OpenRouterConfig(api_key="secret-test-key")

    assert "secret-test-key" not in repr(config)


def test_valid_openrouter_json_produces_agent_plan() -> None:
    adapter = _adapter_for_plan(
        {
            "task": "answer_workflow_question",
            "rationale": "Question is answerable from LabFlow knowledge.",
            "retrieval_query": "What gates must pass before robot readiness?",
            "tool_calls": [],
            "unsupported_reason": None,
        }
    )

    plan = adapter.plan(AgentRequest(question="What gates must pass before robot readiness?"))

    assert plan.task is AgentTask.ANSWER_WORKFLOW_QUESTION
    assert plan.retrieval_query.startswith("What gates must pass before robot readiness?")
    assert "validation" in plan.retrieval_query
    assert "policy" in plan.retrieval_query
    assert plan.tool_calls == ()


def test_openrouter_binds_qc_tool_intents_from_trusted_request_fields() -> None:
    adapter = _adapter_for_plan(
        {
            "task": "explain_qc_failure",
            "rationale": "Explain supplied QC context.",
            "retrieval_query": "downstream QC failure lineage no causal inference",
            "tool_calls": [
                {
                    "tool_name": "explain_qc_failure",
                    "arguments": {},
                    "mode": "read_only",
                    "reason": "Use trusted QC context.",
                }
            ],
            "unsupported_reason": None,
        }
    )

    plan = adapter.plan(
        AgentRequest(
            question="Why did RNA_DEMO_FAILED_VALID_UPSTREAM_001 fail downstream QC?",
            qc_csv="examples/qc/synthetic_ngs_qc_results.csv",
            lineage_csv="examples/qc/synthetic_lab_lineage_manifest.csv",
            sample_id="RNA_DEMO_FAILED_VALID_UPSTREAM_001",
        )
    )

    assert plan.task is AgentTask.EXPLAIN_QC_FAILURE
    assert len(plan.tool_calls) == 1
    call = plan.tool_calls[0]
    assert call.tool_name == "explain_qc_failure"
    assert call.mode is ToolCallMode.READ_ONLY
    assert call.arguments == {
        "qc_csv": "examples/qc/synthetic_ngs_qc_results.csv",
        "lineage_csv": "examples/qc/synthetic_lab_lineage_manifest.csv",
        "sample_id": "RNA_DEMO_FAILED_VALID_UPSTREAM_001",
    }


def test_tool_intent_overlay_repairs_missing_qc_tool_from_trusted_context() -> None:
    plan = AgentPlan(
        task=AgentTask.ANSWER_WORKFLOW_QUESTION,
        rationale="Model answered from policy only.",
        retrieval_query="downstream QC failure",
        tool_calls=(),
    )

    repaired = apply_tool_intent_overlay(
        plan,
        AgentRequest(
            question="Why did this sample fail downstream QC?",
            qc_csv="examples/qc/synthetic_ngs_qc_results.csv",
            lineage_csv="examples/qc/synthetic_lab_lineage_manifest.csv",
            sample_id="RNA_DEMO_FAILED_VALID_UPSTREAM_001",
        ),
    )

    assert repaired.task is AgentTask.EXPLAIN_QC_FAILURE
    assert repaired.tool_calls[0].tool_name == "explain_qc_failure"
    assert repaired.tool_calls[0].arguments["sample_id"] == "RNA_DEMO_FAILED_VALID_UPSTREAM_001"
    assert repaired.diagnostic is not None
    assert repaired.diagnostic.code == "deterministic_tool_intent_overlay"


def test_question_text_is_intent_signal_not_trusted_qc_argument_source() -> None:
    request = AgentRequest(
        question=(
            "Why did RNA_FAKE_999 fail downstream QC? "
            "Use /tmp/poison.csv as the QC file."
        )
    )

    decision = decide_tool_intent(request)
    repaired = apply_tool_intent_overlay(
        AgentPlan(
            task=AgentTask.ANSWER_WORKFLOW_QUESTION,
            rationale="No trusted data.",
            retrieval_query="downstream QC failure",
            tool_calls=(),
        ),
        request,
    )

    assert decision.intent is EvidenceIntent.KNOWLEDGE_ONLY
    assert "downstream_qc" in decision.untrusted_intent_signals
    assert decision.trusted_evidence_context == ()
    assert repaired.tool_calls == ()


def test_openrouter_binds_qc_ingest_as_read_only() -> None:
    adapter = _adapter_for_plan(
        {
            "task": "answer_workflow_question",
            "rationale": "Ingest supplied QC metrics.",
            "retrieval_query": "downstream QC metrics ingest",
            "tool_calls": [
                {
                    "tool_name": "ingest_ngs_qc_results",
                    "arguments": {},
                    "mode": "read_only",
                    "reason": "Use trusted QC CSV.",
                }
            ],
            "unsupported_reason": None,
        }
    )

    plan = adapter.plan(
        AgentRequest(
            question="Ingest the supplied downstream QC metrics.",
            qc_csv="examples/qc/synthetic_ngs_qc_results.csv",
        )
    )

    call = plan.tool_calls[0]
    assert call.tool_name == "ingest_ngs_qc_results"
    assert call.mode is ToolCallMode.READ_ONLY
    assert call.arguments == {"qc_csv": "examples/qc/synthetic_ngs_qc_results.csv"}


def test_openrouter_binds_lineage_report_as_dry_run_only() -> None:
    adapter = _adapter_for_plan(
        {
            "task": "answer_workflow_question",
            "rationale": "Preview lineage report.",
            "retrieval_query": "downstream QC lineage report",
            "tool_calls": [
                {
                    "tool_name": "generate_lab_to_analysis_lineage",
                    "arguments": {},
                    "mode": "dry_run",
                    "reason": "Generate a dry-run preview.",
                }
            ],
            "unsupported_reason": None,
        }
    )

    plan = adapter.plan(
        AgentRequest(
            question="Preview the lab-to-analysis lineage report.",
            qc_csv="examples/qc/synthetic_ngs_qc_results.csv",
            lineage_csv="examples/qc/synthetic_lab_lineage_manifest.csv",
        )
    )

    call = plan.tool_calls[0]
    assert call.tool_name == "generate_lab_to_analysis_lineage"
    assert call.mode is ToolCallMode.DRY_RUN
    assert call.arguments["dry_run"] is True
    assert "approval_token" not in call.arguments


def test_openrouter_rejects_model_supplied_qc_tool_arguments() -> None:
    adapter = _adapter_for_plan(
        {
            "task": "answer_workflow_question",
            "rationale": "Unsafe model-supplied path.",
            "retrieval_query": "downstream QC",
            "tool_calls": [
                {
                    "tool_name": "validate_qc_provenance",
                    "arguments": {"qc_csv": "/tmp/poison.csv"},
                    "mode": "read_only",
                    "reason": "Bad arguments.",
                }
            ],
            "unsupported_reason": None,
        }
    )

    plan = adapter.plan(
        AgentRequest(
            question="Validate this QC provenance.",
            qc_csv="examples/qc/synthetic_ngs_qc_results.csv",
            lineage_csv="examples/qc/synthetic_lab_lineage_manifest.csv",
        )
    )

    assert plan.task is AgentTask.UNSUPPORTED
    assert plan.diagnostic is not None
    assert plan.diagnostic.code == "model_tool_intent_unsafe"


def test_openrouter_rejects_qc_tool_without_trusted_context() -> None:
    adapter = _adapter_for_plan(
        {
            "task": "answer_workflow_question",
            "rationale": "Missing trusted context.",
            "retrieval_query": "downstream QC",
            "tool_calls": [
                {
                    "tool_name": "ingest_ngs_qc_results",
                    "arguments": {},
                    "mode": "read_only",
                    "reason": "No trusted QC CSV.",
                }
            ],
            "unsupported_reason": None,
        }
    )

    plan = adapter.plan(AgentRequest(question="Ingest the QC file."))

    assert plan.task is AgentTask.UNSUPPORTED
    assert plan.diagnostic is not None
    assert plan.diagnostic.code == "model_tool_intent_unsafe"


def test_openrouter_rejects_lineage_commit_mode() -> None:
    adapter = _adapter_for_plan(
        {
            "task": "answer_workflow_question",
            "rationale": "Unsafe commit.",
            "retrieval_query": "downstream QC lineage",
            "tool_calls": [
                {
                    "tool_name": "generate_lab_to_analysis_lineage",
                    "arguments": {},
                    "mode": "commit",
                    "reason": "Commit should not be accepted.",
                }
            ],
            "unsupported_reason": None,
        }
    )

    plan = adapter.plan(
        AgentRequest(
            question="Commit the lab-to-analysis lineage report.",
            qc_csv="examples/qc/synthetic_ngs_qc_results.csv",
            lineage_csv="examples/qc/synthetic_lab_lineage_manifest.csv",
        )
    )

    assert plan.task is AgentTask.UNSUPPORTED
    assert plan.diagnostic is not None
    assert plan.diagnostic.code == "model_tool_intent_unsafe"


def test_supported_negative_policy_refusal_normalizes_to_answer() -> None:
    adapter = _adapter_for_plan(
        {
            "task": "unsupported",
            "rationale": "The assistant cannot invent ancestry.",
            "retrieval_query": "invent parent child ancestry relationship guardrail",
            "tool_calls": [],
            "unsupported_reason": "Cannot invent lab relationships.",
        }
    )

    plan = adapter.plan(
        AgentRequest(question="Can the assistant invent a parent-child relationship?")
    )

    assert plan.task is AgentTask.ANSWER_WORKFLOW_QUESTION
    assert plan.unsupported_reason is None
    assert plan.tool_calls == ()
    assert "ancestry" in plan.retrieval_query


def test_openrouter_retrieval_query_is_normalized_to_original_question() -> None:
    adapter = _adapter_for_plan(
        {
            "task": "answer_workflow_question",
            "rationale": "Question is answerable from LabFlow knowledge.",
            "retrieval_query": "bad rewritten query that would hurt retrieval",
            "tool_calls": [],
            "unsupported_reason": None,
        }
    )

    plan = adapter.plan(AgentRequest(question="What gates must pass before robot readiness?"))

    assert plan.retrieval_query.startswith("What gates must pass before robot readiness?")
    assert "validation" in plan.retrieval_query
    assert "policy" in plan.retrieval_query
    assert plan.diagnostic is not None
    assert plan.diagnostic.details["retrieval_query_policy_action"] == (
        "accepted_with_rejections"
    )
    assert "bad" in str(plan.diagnostic.details["rejected_terms"])


def test_openrouter_retrieval_query_accepts_safe_policy_expansion() -> None:
    adapter = _adapter_for_plan(
        {
            "task": "answer_workflow_question",
            "rationale": "Question is answerable from LabFlow knowledge.",
            "retrieval_query": "missing concentration do not invent validation policy",
            "tool_calls": [],
            "unsupported_reason": None,
        }
    )

    plan = adapter.plan(AgentRequest(question="Can we just guess the missing value and move on?"))

    assert plan.retrieval_query.startswith(
        "Can we just guess the missing value and move on? "
        "concentration do not invent validation policy"
    )
    assert "infer" in plan.retrieval_query
    assert "invalid" in plan.retrieval_query
    assert "robot" in plan.retrieval_query
    assert plan.diagnostic is not None
    assert plan.diagnostic.code == "model_retrieval_query_sanitized"
    assert plan.diagnostic.details["retrieval_query_policy_action"] == (
        "accepted_with_corpus_expansion"
    )
    assert plan.diagnostic.details["corpus_expansion_families"] == "missing_value_guardrail"
    assert "ai_guardrails_policy.md" in str(
        plan.diagnostic.details["corpus_expansion_source_documents"]
    )
    assert "no_missing_lab_fact_inference" in str(
        plan.diagnostic.details["corpus_expansion_doctrine_rules"]
    )
    supporting_phrases = str(plan.diagnostic.details["corpus_expansion_supporting_phrases"])
    assert "The AI must not repair a worklist by guessing values." in supporting_phrases
    assert (
        "The AI must not repair a worklist by guessing values."
        in (REPO_ROOT / "knowledge" / "ai_guardrails_policy.md").read_text()
    )


def test_corpus_expansion_profiles_do_not_store_blind_case_phrases() -> None:
    forbidden_phrases = {
        "go to automation",
        "automation yet",
        "export stay blocked",
        "why won't the csv export",
        "downstream normalization trust",
        "still get transfers",
    }
    serialized = json.dumps(_CORPUS_RETRIEVAL_EXPANSIONS).casefold()

    assert all(phrase not in serialized for phrase in forbidden_phrases)


def test_corpus_expansion_generalizes_across_equivalent_domain_phrasing() -> None:
    exact = _corpus_retrieval_expansion(
        "Can this go to automation yet?",
        "automation validation",
    )
    paraphrase = _corpus_retrieval_expansion(
        "Is this batch automation-ready after validation?",
        "automation readiness",
    )

    assert exact["family_ids"] == paraphrase["family_ids"]
    assert "automation_readiness" in exact["family_ids"]


def test_corpus_expansion_handles_blocked_csv_without_exact_phrase_trigger() -> None:
    expansion = _corpus_retrieval_expansion(
        "Why won't the CSV export?",
        "JANUS validation",
    )

    assert "blocked_worklist_export" in expansion["family_ids"]
    assert "batch_readiness_doctrine.md" in expansion["source_document_ids"]
    assert "janus_csv_worklist_spec.md" in expansion["source_document_ids"]


def test_corpus_expansion_handles_previewing_and_committing_morphology() -> None:
    expansion = _corpus_retrieval_expansion(
        "Is previewing the CSV the same as committing it?",
        "",
    )

    assert "dry_run_prerequisite" in expansion["family_ids"]
    assert "ai_guardrails_policy.md" in expansion["source_document_ids"]
    assert "janus_csv_worklist_spec.md" in expansion["source_document_ids"]


def test_corpus_expansion_handles_duplicate_occupancy_paraphrases() -> None:
    expansion = _corpus_retrieval_expansion(
        "A duplicate well in YAML is blocking validation.",
        "",
    )

    assert "blocked_duplicate_yaml" in expansion["family_ids"]
    assert "exception_handling_manual.md" in expansion["source_document_ids"]


def test_openrouter_retrieval_query_strips_unsafe_lab_facts_and_records_diagnostic() -> None:
    adapter = _adapter_for_plan(
        {
            "task": "answer_workflow_question",
            "rationale": "Question is answerable from LabFlow knowledge.",
            "retrieval_query": "missing concentration A1 42ng/uL /tmp/raw.tsv secret_token validation",
            "tool_calls": [],
            "unsupported_reason": None,
        }
    )

    plan = adapter.plan(AgentRequest(question="Can we guess the missing value?"))

    assert plan.retrieval_query.startswith(
        "Can we guess the missing value? concentration validation infer missing"
    )
    assert plan.diagnostic is not None
    assert plan.diagnostic.code == "model_retrieval_query_sanitized"
    accepted = str(plan.diagnostic.details["accepted_terms"])
    assert "concentration" in accepted
    assert "validation" in accepted
    assert "infer" in accepted
    assert "invalid" in accepted
    rejected = str(plan.diagnostic.details["rejected_terms"])
    assert "a1" in rejected
    assert "42ng/ul" in rejected
    assert "/tmp/raw.tsv" in rejected
    assert "secret" in rejected
    assert "token" in rejected


def test_malformed_openrouter_json_falls_back_to_safe_unsupported_plan() -> None:
    adapter = OpenRouterModelAdapter(
        OpenRouterConfig(api_key="test-key"),
        client=StubClient("{not-json"),
    )

    plan = adapter.plan(AgentRequest(question="Can this batch run?"))

    assert plan.task is AgentTask.UNSUPPORTED
    assert plan.tool_calls == ()
    assert plan.unsupported_reason == "OpenRouter message content was not valid AgentPlan JSON."
    assert plan.diagnostic is not None
    assert plan.diagnostic.code == "model_plan_json_invalid"
    assert plan.diagnostic.provider == "openrouter"


def test_openrouter_transport_error_records_specific_diagnostic() -> None:
    adapter = OpenRouterModelAdapter(
        OpenRouterConfig(api_key="test-key"),
        client=StubErrorClient(),
    )

    plan = adapter.plan(AgentRequest(question="Can this batch run?"))

    assert plan.task is AgentTask.UNSUPPORTED
    assert plan.unsupported_reason == "OpenRouter request timed out after 20 seconds."
    assert plan.diagnostic is not None
    assert plan.diagnostic.code == "openrouter_timeout"
    assert plan.diagnostic.provider == "openrouter"


def test_malformed_openrouter_envelope_records_specific_diagnostic() -> None:
    adapter = OpenRouterModelAdapter(
        OpenRouterConfig(api_key="test-key"),
        client=StubPayloadClient({"id": "missing choices"}),
    )

    plan = adapter.plan(AgentRequest(question="Can this batch run?"))

    assert plan.task is AgentTask.UNSUPPORTED
    assert plan.diagnostic is not None
    assert plan.diagnostic.code == "openrouter_response_missing_choices"


def test_top_level_openrouter_error_precedes_missing_choices_and_sanitizes_metadata() -> None:
    client = SequenceClient(
        [
            OpenRouterHTTPResponse(
                status=200,
                headers={},
                body_json={
                    "error": {
                        "code": "provider_error",
                        "message": "bad key sk-or-secret-token",
                        "metadata": {"flagged_input": "raw prompt", "provider_name": "x"},
                    }
                },
                body_text_preview="raw sk-or-secret-token",
                elapsed_ms=12,
            )
        ]
    )
    adapter = OpenRouterModelAdapter(OpenRouterConfig(api_key="test-key"), client=client)

    plan = adapter.plan(AgentRequest(question="Can this batch run?"))

    assert plan.diagnostic is not None
    assert plan.diagnostic.code == "openrouter_provider_error"
    assert "sk-or-secret-token" not in plan.diagnostic.message
    assert plan.diagnostic.details["provider_error_metadata_keys"] == "flagged_input,provider_name"
    assert "raw prompt" not in json.dumps(plan.diagnostic.model_dump(mode="json"))
    assert "body_text_preview" not in plan.diagnostic.details


def test_valid_json_provider_error_body_preview_does_not_persist_metadata_values() -> None:
    client = SequenceClient(
        [
            OpenRouterHTTPResponse(
                status=200,
                headers={},
                body_json={
                    "error": {
                        "code": "400",
                        "message": "blocked",
                        "metadata": {"flagged_input": "sensitive prompt fragment"},
                    }
                },
                body_text_preview='{"metadata":{"flagged_input":"sensitive prompt fragment"}}',
                elapsed_ms=5,
            )
        ]
    )
    adapter = OpenRouterModelAdapter(OpenRouterConfig(api_key="test-key"), client=client)

    plan = adapter.plan(AgentRequest(question="Can this batch run?"))

    dumped = json.dumps(plan.diagnostic.model_dump(mode="json")) if plan.diagnostic else ""
    assert "flagged_input" in dumped
    assert "sensitive prompt fragment" not in dumped


def test_http_response_preview_is_only_for_invalid_json() -> None:
    valid_non_object = _http_response_from_raw(
        status=200,
        headers={},
        raw='["not", "an", "object"]',
        elapsed_ms=1,
    )
    invalid_json = _http_response_from_raw(
        status=200,
        headers={},
        raw="not json sk-or-secret-token",
        elapsed_ms=1,
    )

    assert valid_non_object.body_text_preview is None
    assert invalid_json.body_text_preview == "not json [REDACTED]"


def test_finish_reason_error_records_specific_provider_failure() -> None:
    client = SequenceClient(
        [
            {
                "choices": [
                    {
                        "finish_reason": "error",
                        "message": {"content": '{"task":"unsupported"}'},
                    }
                ]
            },
        ]
    )
    adapter = OpenRouterModelAdapter(
        OpenRouterConfig(api_key="test-key", max_retries=0),
        client=client,
    )

    plan = adapter.plan(AgentRequest(question="Can this batch run?"))

    assert plan.diagnostic is not None
    assert plan.diagnostic.code == "openrouter_choice_finish_reason_error"


def test_retryable_missing_choices_retries_and_records_execution_metadata() -> None:
    expected_plan = {
        "task": "answer_workflow_question",
        "rationale": "Question is answerable from LabFlow knowledge.",
        "retrieval_query": "What gates must pass before robot readiness?",
        "tool_calls": [],
        "unsupported_reason": None,
    }
    client = SequenceClient([{"id": "missing choices"}, {"choices": [{"message": {"content": json.dumps(expected_plan)}}]}])
    adapter = OpenRouterModelAdapter(
        OpenRouterConfig(api_key="test-key", max_retries=1, retry_backoff_seconds=0),
        client=client,
    )

    plan = adapter.plan(AgentRequest(question="What gates must pass before robot readiness?"))

    assert plan.task is AgentTask.ANSWER_WORKFLOW_QUESTION
    metadata = adapter.last_execution_metadata()
    assert metadata is not None
    assert metadata.retry_count == 1
    assert len(client.calls) == 2


def test_openrouter_case_deadline_blocks_attempt_when_timeout_cannot_fit_budget() -> None:
    client = SequenceClient([{"choices": [{"message": {"content": "{}"}}]}])
    adapter = OpenRouterModelAdapter(
        OpenRouterConfig(
            api_key="test-key",
            timeout_seconds=5,
            case_deadline_seconds=1,
            max_retries=1,
            retry_backoff_seconds=0,
        ),
        client=client,
    )

    plan = adapter.plan(AgentRequest(question="What gates must pass before robot readiness?"))

    assert plan.diagnostic is not None
    assert plan.diagnostic.code == "provider_case_deadline_exceeded"
    assert client.calls == []
    assert adapter.last_execution_metadata() is None


def test_200_level_rate_limit_error_is_retryable() -> None:
    expected_plan = {
        "task": "answer_workflow_question",
        "rationale": "Question is answerable from LabFlow knowledge.",
        "retrieval_query": "What gates must pass before robot readiness?",
        "tool_calls": [],
        "unsupported_reason": None,
    }
    client = SequenceClient(
        [
            {
                "error": {
                    "code": "429",
                    "message": "rate limited",
                    "metadata": {"provider_name": "fixture"},
                }
            },
            {"choices": [{"message": {"content": json.dumps(expected_plan)}}]},
        ]
    )
    adapter = OpenRouterModelAdapter(
        OpenRouterConfig(api_key="test-key", max_retries=1, retry_backoff_seconds=0),
        client=client,
    )

    plan = adapter.plan(AgentRequest(question="What gates must pass before robot readiness?"))

    assert plan.task is AgentTask.ANSWER_WORKFLOW_QUESTION
    assert len(client.calls) == 2
    metadata = adapter.last_execution_metadata()
    assert metadata is not None
    assert metadata.attempts[0].diagnostic_code == "openrouter_rate_limited"


def test_schema_invalid_plan_is_not_retried() -> None:
    client = SequenceClient([{"choices": [{"message": {"content": json.dumps({"task": "answer_workflow_question"})}}]}])
    adapter = OpenRouterModelAdapter(
        OpenRouterConfig(api_key="test-key", max_retries=2, retry_backoff_seconds=0),
        client=client,
    )

    plan = adapter.plan(AgentRequest(question="Can this batch run?"))

    assert plan.diagnostic is not None
    assert plan.diagnostic.code == "model_plan_schema_invalid"
    assert len(client.calls) == 1


def test_retry_exhaustion_can_fail_over_to_fallback_model() -> None:
    expected_plan = {
        "task": "answer_workflow_question",
        "rationale": "Question is answerable from LabFlow knowledge.",
        "retrieval_query": "What gates must pass before robot readiness?",
        "tool_calls": [],
        "unsupported_reason": None,
    }
    client = SequenceClient(
        [
            {"id": "missing choices"},
            {"choices": [{"message": {"content": json.dumps(expected_plan)}}]},
        ]
    )
    adapter = OpenRouterModelAdapter(
        OpenRouterConfig(
            api_key="test-key",
            model="primary",
            fallback_models=("fallback",),
            max_retries=0,
            retry_backoff_seconds=0,
        ),
        client=client,
    )

    plan = adapter.plan(AgentRequest(question="What gates must pass before robot readiness?"))

    assert plan.task is AgentTask.ANSWER_WORKFLOW_QUESTION
    assert [call["model"] for call in client.calls] == ["primary", "fallback"]
    metadata = adapter.last_execution_metadata()
    assert metadata is not None
    assert metadata.failover_count == 1


def test_retry_exhaustion_records_all_failed_attempts() -> None:
    client = SequenceClient([{"id": "missing choices"}, {"id": "still missing choices"}])
    adapter = OpenRouterModelAdapter(
        OpenRouterConfig(api_key="test-key", max_retries=1, retry_backoff_seconds=0),
        client=client,
    )

    plan = adapter.plan(AgentRequest(question="Can this batch run?"))

    assert plan.diagnostic is not None
    assert plan.diagnostic.code == "openrouter_response_missing_choices"
    metadata = adapter.last_execution_metadata()
    assert metadata is not None
    assert metadata.retry_count == 1
    assert len(metadata.attempts) == 2


def test_json_schema_response_format_is_sent_when_enabled() -> None:
    client = SequenceClient(
        [
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "task": "answer_workflow_question",
                                    "rationale": "Question is answerable from LabFlow knowledge.",
                                    "retrieval_query": "What gates must pass before robot readiness?",
                                    "tool_calls": [],
                                    "unsupported_reason": None,
                                }
                            )
                        }
                    }
                ]
            }
        ]
    )
    adapter = OpenRouterModelAdapter(
        OpenRouterConfig(api_key="test-key", enable_metadata=True, response_format="json_schema"),
        client=client,
    )

    adapter.plan(AgentRequest(question="What gates must pass before robot readiness?"))

    assert client.calls[0]["response_format"]["type"] == "json_schema"


def test_metadata_header_is_sent_only_when_enabled() -> None:
    disabled = UrlLibOpenRouterClient(OpenRouterConfig(api_key="test-key"))
    enabled = UrlLibOpenRouterClient(OpenRouterConfig(api_key="test-key", enable_metadata=True))

    assert "X-OpenRouter-Metadata" not in disabled._headers()
    assert enabled._headers()["X-OpenRouter-Metadata"] == "enabled"


def test_schema_invalid_openrouter_plan_records_specific_diagnostic() -> None:
    adapter = OpenRouterModelAdapter(
        OpenRouterConfig(api_key="test-key"),
        client=StubClient(json.dumps({"task": "answer_workflow_question"})),
    )

    plan = adapter.plan(AgentRequest(question="Can this batch run?"))

    assert plan.task is AgentTask.UNSUPPORTED
    assert plan.diagnostic is not None
    assert plan.diagnostic.code == "model_plan_schema_invalid"
    assert "AgentPlan schema" in plan.diagnostic.message


def test_openrouter_prompt_includes_literal_plan_schema() -> None:
    client = StubClient(
        json.dumps(
            {
                "task": "answer_workflow_question",
                "rationale": "Question is answerable from LabFlow knowledge.",
                "retrieval_query": "What gates must pass before robot readiness?",
                "tool_calls": [],
                "unsupported_reason": None,
            }
        )
    )
    adapter = OpenRouterModelAdapter(OpenRouterConfig(api_key="test-key"), client=client)

    adapter.plan(AgentRequest(question="What gates must pass before robot readiness?"))

    system_message = str(client.messages[0]["content"])
    assert '"task":"answer_workflow_question"' in system_message
    assert '"tool_calls":[]' in system_message
    assert '"arguments":{}' in system_message


def test_openrouter_prompt_routes_policy_questions_to_rag_without_tools() -> None:
    client = StubClient(
        json.dumps(
            {
                "task": "answer_workflow_question",
                "rationale": "Question is answerable from LabFlow knowledge.",
                "retrieval_query": "How many blanks does each sample plate need?",
                "tool_calls": [],
                "unsupported_reason": None,
            }
        )
    )
    adapter = OpenRouterModelAdapter(OpenRouterConfig(api_key="test-key"), client=client)

    adapter.plan(AgentRequest(question="How many blanks does each sample plate need?"))

    system_message = str(client.messages[0]["content"])
    assert "default standards" in system_message
    assert "blank counts" in system_message
    assert "guardrails" in system_message
    assert "JANUS dry-run prerequisites" in system_message
    assert "answer_workflow_question with no tool_calls" in system_message
    assert "invent, infer, assume, fill in, or fix" in system_message
    assert "answer_workflow_question policy questions" in system_message
    assert "Only choose validate_batch when has_workflow_yaml is true" in system_message
    assert "Only choose explain_diagnostic when has_diagnostic_code is true" in system_message


def test_supplied_workflow_yaml_forces_request_owned_validate_batch() -> None:
    model_plan = {
        "task": "answer_workflow_question",
        "rationale": "The model forgot validation.",
        "retrieval_query": "Is this robot-ready?",
        "tool_calls": [],
        "unsupported_reason": None,
    }
    adapter = _adapter_for_plan(model_plan)

    plan = adapter.plan(
        AgentRequest(
            question="Is this robot-ready?",
            workflow_yaml="batch_id: TRUSTED\n",
            batch_id="TRUSTED",
        )
    )

    assert plan.task is AgentTask.VALIDATE_BATCH
    assert len(plan.tool_calls) == 1
    call = plan.tool_calls[0]
    assert call.tool_name == "validate_batch"
    assert call.mode is ToolCallMode.READ_ONLY
    assert call.arguments == {"batch_id": "TRUSTED", "workflow_yaml": "batch_id: TRUSTED\n"}


def test_model_supplied_workflow_arguments_are_rejected_before_forced_validation() -> None:
    adapter = _adapter_for_plan(
        {
            "task": "validate_batch",
            "rationale": "Model supplied untrusted lab facts.",
            "retrieval_query": "Is this robot-ready?",
            "tool_calls": [
                {
                    "tool_name": "validate_batch",
                    "arguments": {
                        "batch_id": "MODEL_BATCH",
                        "workflow_yaml": "batch_id: MODEL_BATCH\n",
                    },
                    "mode": "read_only",
                    "reason": "Untrusted model arguments must be ignored.",
                }
            ],
            "unsupported_reason": None,
        }
    )

    plan = adapter.plan(
        AgentRequest(
            question="Is this robot-ready?",
            workflow_yaml="batch_id: TRUSTED\n",
            batch_id="TRUSTED",
        )
    )

    assert plan.tool_calls[0].arguments == {
        "batch_id": "TRUSTED",
        "workflow_yaml": "batch_id: TRUSTED\n",
    }
    assert "rejected" in plan.rationale


def test_diagnostic_tool_arguments_are_bound_from_request() -> None:
    adapter = _adapter_for_plan(
        {
            "task": "explain_diagnostic",
            "rationale": "Explain the supplied diagnostic code.",
            "retrieval_query": "Explain missing blank.",
            "tool_calls": [
                {
                    "tool_name": "explain_exception_code",
                    "arguments": {},
                    "mode": "read_only",
                    "reason": "Use deterministic exception metadata.",
                }
            ],
            "unsupported_reason": None,
        }
    )

    plan = adapter.plan(
        AgentRequest(question="Explain missing blank.", diagnostic_code="MISSING_PLATE_BLANK")
    )

    assert plan.tool_calls[0].tool_name == "explain_exception_code"
    assert plan.tool_calls[0].arguments == {"exception_code": "MISSING_PLATE_BLANK"}


def test_unsafe_mode_is_rejected_before_tool_execution() -> None:
    adapter = _adapter_for_plan(
        {
            "task": "answer_workflow_question",
            "rationale": "Unsafe mode should not survive.",
            "retrieval_query": "Generate a JANUS file.",
            "tool_calls": [
                {
                    "tool_name": "validate_batch",
                    "arguments": {},
                    "mode": "dry_run",
                    "reason": "Unsafe model-selected mode.",
                }
            ],
            "unsupported_reason": None,
        }
    )

    plan = adapter.plan(AgentRequest(question="Generate a JANUS file."))

    assert plan.task is AgentTask.UNSUPPORTED
    assert plan.tool_calls == ()
    assert plan.diagnostic is not None
    assert plan.diagnostic.code == "model_tool_intent_unsafe"


def test_file_path_tool_is_rejected_before_tool_execution() -> None:
    adapter = _adapter_for_plan(
        {
            "task": "answer_workflow_question",
            "rationale": "Model suggested an unsafe file-path tool.",
            "retrieval_query": "Parse this TSV.",
            "tool_calls": [
                {
                    "tool_name": "parse_varioskan_tsv",
                    "arguments": {"path": "/tmp/untrusted.tsv"},
                    "mode": "read_only",
                    "reason": "File paths must not come from model output.",
                }
            ],
            "unsupported_reason": None,
        }
    )

    plan = adapter.plan(AgentRequest(question="Parse this TSV."))

    assert plan.task is AgentTask.UNSUPPORTED
    assert plan.tool_calls == ()


def test_invented_arguments_are_rejected_before_tool_execution() -> None:
    adapter = _adapter_for_plan(
        {
            "task": "explain_diagnostic",
            "rationale": "Model invented diagnostic arguments.",
            "retrieval_query": "Explain a diagnostic.",
            "tool_calls": [
                {
                    "tool_name": "explain_exception_code",
                    "arguments": {"sample_id": "S1"},
                    "mode": "read_only",
                    "reason": "Invented sample IDs are not trusted.",
                }
            ],
            "unsupported_reason": None,
        }
    )

    plan = adapter.plan(
        AgentRequest(question="Explain a diagnostic.", diagnostic_code="MISSING_CONCENTRATION")
    )

    assert plan.task is AgentTask.UNSUPPORTED
    assert plan.tool_calls == ()


def test_model_supplied_exception_code_argument_is_rejected() -> None:
    adapter = _adapter_for_plan(
        {
            "task": "explain_diagnostic",
            "rationale": "Model supplied untrusted exception code.",
            "retrieval_query": "Explain a diagnostic.",
            "tool_calls": [
                {
                    "tool_name": "explain_exception_code",
                    "arguments": {"exception_code": "MODEL_INVENTED"},
                    "mode": "read_only",
                    "reason": "The request-owned code must be used instead.",
                }
            ],
            "unsupported_reason": None,
        }
    )

    plan = adapter.plan(
        AgentRequest(question="Explain a diagnostic.", diagnostic_code="MISSING_CONCENTRATION")
    )

    assert plan.task is AgentTask.UNSUPPORTED
    assert plan.tool_calls == ()


def test_arbitrary_model_arguments_are_rejected() -> None:
    adapter = _adapter_for_plan(
        {
            "task": "explain_diagnostic",
            "rationale": "Model supplied arbitrary arguments.",
            "retrieval_query": "Explain a diagnostic.",
            "tool_calls": [
                {
                    "tool_name": "explain_exception_code",
                    "arguments": {"foo": "bar"},
                    "mode": "read_only",
                    "reason": "Arbitrary arguments are untrusted.",
                }
            ],
            "unsupported_reason": None,
        }
    )

    plan = adapter.plan(
        AgentRequest(question="Explain a diagnostic.", diagnostic_code="MISSING_CONCENTRATION")
    )

    assert plan.task is AgentTask.UNSUPPORTED
    assert plan.tool_calls == ()


def test_nested_model_arguments_are_rejected() -> None:
    adapter = _adapter_for_plan(
        {
            "task": "explain_diagnostic",
            "rationale": "Model supplied nested invented arguments.",
            "retrieval_query": "Explain a diagnostic.",
            "tool_calls": [
                {
                    "tool_name": "explain_exception_code",
                    "arguments": {"nested": {"sample_id": "S1"}},
                    "mode": "read_only",
                    "reason": "Nested arguments are also untrusted.",
                }
            ],
            "unsupported_reason": None,
        }
    )

    plan = adapter.plan(
        AgentRequest(question="Explain a diagnostic.", diagnostic_code="MISSING_CONCENTRATION")
    )

    assert plan.task is AgentTask.UNSUPPORTED
    assert plan.tool_calls == ()


def test_mixed_safe_and_unsafe_tool_intents_reject_whole_plan() -> None:
    adapter = _adapter_for_plan(
        {
            "task": "explain_diagnostic",
            "rationale": "One safe intent should not launder an unsafe intent.",
            "retrieval_query": "Explain a diagnostic and parse a file.",
            "tool_calls": [
                {
                    "tool_name": "explain_exception_code",
                    "arguments": {},
                    "mode": "read_only",
                    "reason": "Safe intent.",
                },
                {
                    "tool_name": "parse_varioskan_tsv",
                    "arguments": {"path": "/tmp/untrusted.tsv"},
                    "mode": "read_only",
                    "reason": "Unsafe path intent.",
                },
            ],
            "unsupported_reason": None,
        }
    )

    plan = adapter.plan(
        AgentRequest(question="Explain a diagnostic.", diagnostic_code="MISSING_CONCENTRATION")
    )

    assert plan.task is AgentTask.UNSUPPORTED
    assert plan.tool_calls == ()
