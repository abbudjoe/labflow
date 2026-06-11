"""Registry for deterministic LabFlow core tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from labflow_core.tools import core_tools
from labflow_core.tools.schemas import JsonDict

ToolCallable = Callable[..., JsonDict]


class ToolDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    read_only: bool
    parameters: dict[str, str]


_TOOL_DEFINITIONS: dict[str, ToolDefinition] = {
    "validate_workflow": ToolDefinition(
        name="validate_workflow",
        description="Validate a LabFlow workflow YAML document.",
        read_only=True,
        parameters={"workflow_yaml": "string"},
    ),
    "validate_batch": ToolDefinition(
        name="validate_batch",
        description="Validate a batch from workflow YAML and optional batch ID.",
        read_only=True,
        parameters={"batch_id": "string|null", "workflow_yaml": "string"},
    ),
    "parse_varioskan_tsv": ToolDefinition(
        name="parse_varioskan_tsv",
        description="Parse a Varioskan TSV file using an optional schema mapping.",
        read_only=True,
        parameters={"file_path": "string", "schema_mapping": "object|null"},
    ),
    "process_quantification": ToolDefinition(
        name="process_quantification",
        description="Process quantification from an explicit config file.",
        read_only=True,
        parameters={"config_path": "string"},
    ),
    "generate_normalization_plan": ToolDefinition(
        name="generate_normalization_plan",
        description="Generate a deterministic normalization plan preview.",
        read_only=True,
        parameters={"config_path": "string"},
    ),
    "process_rna_requant": ToolDefinition(
        name="process_rna_requant",
        description="Process RNA normalization and re-quantification from config.",
        read_only=True,
        parameters={"config_path": "string"},
    ),
    "generate_janus_csv": ToolDefinition(
        name="generate_janus_csv",
        description="Generate or preview JANUS CSV after deterministic validation.",
        read_only=False,
        parameters={
            "plan_id": "string",
            "dry_run": "boolean",
            "approval_token": "string|null",
            "output_dir": "string|null",
        },
    ),
    "compare_throughput": ToolDefinition(
        name="compare_throughput",
        description="Compare deterministic throughput scenarios.",
        read_only=True,
        parameters={"config_path": "string"},
    ),
    "explain_exception_code": ToolDefinition(
        name="explain_exception_code",
        description="Return deterministic meaning and next action for a LabFlow exception code.",
        read_only=True,
        parameters={"exception_code": "string"},
    ),
}

_TOOL_FUNCTIONS: dict[str, ToolCallable] = {
    "validate_workflow": core_tools.validate_workflow,
    "validate_batch": core_tools.validate_batch,
    "parse_varioskan_tsv": core_tools.parse_varioskan_tsv,
    "process_quantification": core_tools.process_quantification,
    "generate_normalization_plan": core_tools.generate_normalization_plan,
    "process_rna_requant": core_tools.process_rna_requant,
    "generate_janus_csv": core_tools.generate_janus_csv,
    "compare_throughput": core_tools.compare_throughput,
    "explain_exception_code": core_tools.explain_exception_code,
}


def list_tools() -> list[dict[str, Any]]:
    return [
        definition.model_dump(mode="json")
        for _, definition in sorted(_TOOL_DEFINITIONS.items())
    ]


def get_tool(name: str) -> ToolCallable:
    try:
        return _TOOL_FUNCTIONS[name]
    except KeyError as exc:
        msg = f"Unknown LabFlow tool: {name}"
        raise KeyError(msg) from exc


def call_tool(name: str, **kwargs: Any) -> JsonDict:
    return get_tool(name)(**kwargs)
