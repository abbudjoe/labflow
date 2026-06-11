from __future__ import annotations

import json
from typing import Any

from pathlib import Path

from labflow_agent.openrouter import OpenRouterConfig
from labflow_agent.openrouter_answer import OpenRouterAnswerComposer
from test_answer_model import _context


class CapturingClient:
    def __init__(self, draft: dict[str, Any]) -> None:
        self.messages: list[dict[str, Any]] = []
        self._draft = draft

    def complete(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        self.messages = messages
        return {"choices": [{"message": {"content": json.dumps(self._draft)}}]}


def test_openrouter_answer_composer_returns_structured_draft_without_secrets() -> None:
    _validator, context = _context()
    assert context.obligations is not None
    claim_id = context.obligations.compiled_claims[0].claim_id
    client = CapturingClient(
        {
            "rewrites": {
                claim_id: (
                    "Deterministic validation says the batch is not robot-ready and blocks "
                    "readiness because MISSING_CONCENTRATION is present."
                )
            },
            "next_safe_action_rewrite": "Add measured concentration data, then rerun validation.",
        }
    )
    composer = OpenRouterAnswerComposer(
        OpenRouterConfig(api_key="secret-test-key", model="test/model"),
        client=client,
    )

    draft = composer.draft(context)
    prompt_payload = json.dumps(client.messages)

    assert draft.cited_tool_call_ids == ("tool:0:validate_batch",)
    assert draft.claim_citations
    assert composer.metadata.provider == "openrouter-answer"
    assert "secret-test-key" not in prompt_payload
    assert Path("examples/workflows/invalid_rna_norm_requant.workflow.yaml").read_text() not in prompt_payload


def test_openrouter_prompt_lists_tool_inventory_and_empty_tool_rule() -> None:
    _validator, context = _context()
    context = context.model_copy(update={"tool_evidence": ()})
    assert context.obligations is not None
    claim_id = context.obligations.compiled_claims[0].claim_id
    client = CapturingClient(
        {
            "rewrites": {
                claim_id: "Deterministic validation says the batch is not robot-ready and blocks readiness."
            },
            "next_safe_action_rewrite": "Run deterministic validation.",
        }
    )
    composer = OpenRouterAnswerComposer(
        OpenRouterConfig(api_key="secret-test-key", model="test/model"),
        client=client,
    )

    draft = composer.draft(context)
    prompt_payload = json.dumps(client.messages)
    evidence_inventory = json.loads(str(client.messages[1]["content"]))

    assert draft.cited_tool_call_ids == ()
    assert evidence_inventory["prompt_metadata"]["prompt_version"] == "stage18.13"
    assert "Return rewrites only" in prompt_payload
    assert "batch_readiness_doctrine.md#chunk-001" in prompt_payload
    assert "answer_frame" in prompt_payload
    assert "required_claims" not in prompt_payload


def test_openrouter_prompt_lists_valid_tool_evidence_ids() -> None:
    _validator, context = _context()
    assert context.obligations is not None
    claim_id = context.obligations.compiled_claims[0].claim_id
    client = CapturingClient(
        {
            "rewrites": {
                claim_id: (
                    "Deterministic validation says the batch is not robot-ready and blocks "
                    "readiness because MISSING_CONCENTRATION is present."
                )
            },
            "next_safe_action_rewrite": "Fix the error and rerun validation.",
        }
    )
    composer = OpenRouterAnswerComposer(
        OpenRouterConfig(api_key="secret-test-key", model="test/model"),
        client=client,
    )

    composer.draft(context)
    prompt_payload = json.dumps(client.messages)

    assert "tool:0:validate_batch" in prompt_payload
    assert "deterministic renderer owns citations" in prompt_payload
