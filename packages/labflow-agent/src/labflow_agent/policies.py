"""Policy classification and enforcement helpers for LabFlow agent tools."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from labflow_agent.models import ToolCallMode, ToolCallPlan


class ActionClass(StrEnum):
    """Guardrail class for an agent-visible action."""

    READ_ONLY = "read_only"
    DRY_RUN_ARTIFACT = "dry_run_artifact"
    COMMIT = "commit"


class PolicyDecision(BaseModel):
    """Result of classifying a planned tool call."""

    model_config = ConfigDict(frozen=True)

    action_class: ActionClass
    tool_name: str = Field(min_length=1)
    mode: ToolCallMode
    requires_dry_run: bool = False
    requires_approval: bool = False
    creates_artifact_record: bool = False


class ToolPolicyError(ValueError):
    """Raised when a planned tool call violates agent guardrails."""


class ToolPolicy:
    """Classify and validate tool calls against the Stage 10 guardrail contract."""

    _DRY_RUN_ARTIFACT_TOOLS = frozenset({"generate_janus_csv"})

    def __init__(self, tool_definitions: dict[str, dict[str, Any]]) -> None:
        self._tool_definitions = tool_definitions

    def classify(self, planned: ToolCallPlan) -> PolicyDecision:
        definition = self._tool_definitions.get(planned.tool_name)
        if definition is None:
            msg = f"Unknown LabFlow tool: {planned.tool_name}"
            raise ToolPolicyError(msg)

        if bool(definition["read_only"]):
            if planned.mode is not ToolCallMode.READ_ONLY:
                msg = f"Read-only tool {planned.tool_name} must run in read_only mode."
                raise ToolPolicyError(msg)
            return PolicyDecision(
                action_class=ActionClass.READ_ONLY,
                tool_name=planned.tool_name,
                mode=planned.mode,
            )

        if planned.tool_name in self._DRY_RUN_ARTIFACT_TOOLS:
            return self._classify_artifact_tool(planned)

        msg = f"Non-read-only tool {planned.tool_name} is not allowlisted by policy."
        raise ToolPolicyError(msg)

    def _classify_artifact_tool(self, planned: ToolCallPlan) -> PolicyDecision:
        if planned.mode is ToolCallMode.DRY_RUN:
            if planned.arguments.get("dry_run") is not True:
                msg = f"Tool {planned.tool_name} must be called with dry_run=true in dry_run mode."
                raise ToolPolicyError(msg)
            if planned.arguments.get("approval_token") is not None:
                msg = "Approval tokens are only accepted for commit mode."
                raise ToolPolicyError(msg)
            return PolicyDecision(
                action_class=ActionClass.DRY_RUN_ARTIFACT,
                tool_name=planned.tool_name,
                mode=planned.mode,
            )

        if planned.mode is ToolCallMode.COMMIT:
            if planned.arguments.get("dry_run") is not False:
                msg = f"Tool {planned.tool_name} must be called with dry_run=false in commit mode."
                raise ToolPolicyError(msg)
            return PolicyDecision(
                action_class=ActionClass.COMMIT,
                tool_name=planned.tool_name,
                mode=planned.mode,
                requires_dry_run=True,
                requires_approval=True,
                creates_artifact_record=True,
            )

        msg = f"Tool {planned.tool_name} requires dry_run or commit mode."
        raise ToolPolicyError(msg)
