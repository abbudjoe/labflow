from __future__ import annotations

import json
from typing import Any

import pytest

from labflow_agent.openrouter import OpenRouterConfig, OpenRouterError
from labflow_agent.openrouter_repair import OpenRouterRepairProposer


class CapturingClient:
    def __init__(self, proposal: dict[str, Any]) -> None:
        self.messages: list[dict[str, Any]] = []
        self._proposal = proposal

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del model, response_format
        self.messages = messages
        return {"choices": [{"message": {"content": json.dumps(self._proposal)}}]}


def test_openrouter_repair_proposer_returns_typed_dry_run_patch() -> None:
    client = CapturingClient(
        {
            "mode": "patch",
            "dry_run": True,
            "requires_approval_before_commit": True,
            "operations": [
                {
                    "op": "replace",
                    "path": "/samples/1/destination_well",
                    "value": "H12",
                    "reason": "Address duplicate destination with the specified empty well.",
                    "evidence": ["case_allowed_patch_value"],
                }
            ],
            "refusal_reason": None,
            "audit_expectation": "Patch proposal must be audited as a dry-run before commit approval.",
        }
    )
    proposer = OpenRouterRepairProposer(
        OpenRouterConfig(api_key="test-key", model="test/model"),
        client=client,
    )

    proposal = proposer.propose(
        {
            "id": "repair_duplicate_destination_patch_001",
            "question": "Move the duplicate destination to H12.",
            "target_diagnostic": "DUPLICATE_DESTINATION_LOCATION",
            "expected_mode": "patch",
            "allowed_patch_paths": ["/samples/1/destination_well"],
            "allowed_patch_values": ["H12"],
            "forbidden_patch_values": ["guessed"],
        }
    )
    prompt_payload = json.dumps(client.messages)

    assert proposal.dry_run is True
    assert proposal.requires_approval_before_commit is True
    assert proposal.operations[0].path == "/samples/1/destination_well"
    assert "dry_run=true" in prompt_payload
    assert "Do not create paths or values" in prompt_payload


def test_openrouter_repair_proposer_rejects_commit_mode_schema() -> None:
    client = CapturingClient(
        {
            "mode": "patch",
            "dry_run": False,
            "requires_approval_before_commit": False,
            "operations": [
                {
                    "op": "replace",
                    "path": "/samples/0/concentration_ng_per_ul",
                    "value": 1,
                    "reason": "unsafe",
                }
            ],
        }
    )
    proposer = OpenRouterRepairProposer(
        OpenRouterConfig(api_key="test-key", model="test/model"),
        client=client,
    )

    with pytest.raises(OpenRouterError, match="PatchProposal schema"):
        proposer.propose({"id": "unsafe"})
