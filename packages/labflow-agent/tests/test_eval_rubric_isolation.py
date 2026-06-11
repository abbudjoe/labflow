from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

from labflow_agent.answer_model import build_grounded_answer_frame


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_inference_eval_ladder.py"


def _load_runner() -> object:
    spec = importlib.util.spec_from_file_location("run_inference_eval_ladder", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["run_inference_eval_ladder"] = module
    spec.loader.exec_module(module)
    return module


def test_grounded_context_and_frame_ignore_poisoned_eval_rubric_fields() -> None:
    runner = _load_runner()
    case = runner._load_cases("grounded_answer_quality")[0]
    context = runner.build_grounded_answer_context(case)
    frame = build_grounded_answer_frame(context)

    poisoned = deepcopy(case)
    poisoned["required_claims"] = (
        {
            "claim_id": "rubric_leak",
            "required_terms": {"all": ["rubric-only-claim"]},
            "source_families": {"any": ["rubric_only.md"]},
        },
    )
    poisoned["required_citation_families"] = ["rubric_only.md"]
    poisoned["required_answer_terms"] = ["rubric-only-answer"]
    poisoned["expected_next_action_terms"] = ["rubric-only-action"]

    poisoned_context = runner.build_grounded_answer_context(poisoned)
    poisoned_frame = build_grounded_answer_frame(poisoned_context)

    assert poisoned_context.source_ids == context.source_ids
    assert poisoned_context.obligations == context.obligations
    assert poisoned_frame == frame


def test_semantic_rubric_fields_do_not_drive_source_profiles() -> None:
    runner = _load_runner()
    case = runner._load_cases("semantic_generalization")[0]
    poisoned = deepcopy(case)
    poisoned["required_source_families"] = ["rubric_only.md"]
    poisoned["retrieval_intents"] = [{"id": "poison", "any": ["rubric-only-intent"]}]

    context = runner.build_grounded_answer_context(
        {
            **case,
            "required_claims": (),
            "required_citation_families": (),
            "required_tool_fact_terms": (),
            "required_answer_terms": (),
            "expected_next_action_terms": (),
            "disallowed_terms": (),
        }
    )
    poisoned_context = runner.build_grounded_answer_context(
        {
            **poisoned,
            "required_claims": (),
            "required_citation_families": (),
            "required_tool_fact_terms": (),
            "required_answer_terms": (),
            "expected_next_action_terms": (),
            "disallowed_terms": (),
        }
    )

    assert poisoned_context.source_ids == context.source_ids
    assert poisoned_context.obligations == context.obligations
