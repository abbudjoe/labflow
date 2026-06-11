"""JSON Schema helpers for LabFlow workflow DSL."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from labflow_core.dsl.models import LabFlowWorkflow


def workflow_json_schema() -> dict[str, Any]:
    schema = LabFlowWorkflow.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = "LabFlow Workflow DSL"
    return schema


def write_workflow_json_schema(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(workflow_json_schema(), indent=2, sort_keys=True) + "\n")
