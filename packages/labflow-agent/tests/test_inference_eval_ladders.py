from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

from labflow_agent.answer_model import (
    ClaimCitation,
    GroundedAnswerContext,
    GroundedAnswerDraft,
    ToolEvidence,
)
from labflow_agent.models import ModelMetadata, PlanDiagnostic
from labflow_agent.openrouter import OpenRouterError
from labflow_agent.patch_proposer import PatchProposal
from labflow_rag import RagAnswer


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_inference_eval_ladder.py"
MODEL_LADDER_SCRIPT_PATH = REPO_ROOT / "scripts" / "run_model_eval_ladder.py"
MODEL_COMPARISON_SCRIPT_PATH = REPO_ROOT / "scripts" / "run_model_eval_comparison.py"


def _claim_citations_for_context(context: GroundedAnswerContext) -> tuple[ClaimCitation, ...]:
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


def _load_runner() -> object:
    spec = importlib.util.spec_from_file_location("run_inference_eval_ladder", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["run_inference_eval_ladder"] = module
    spec.loader.exec_module(module)
    return module


def _load_script(path: Path, module_name: str) -> object:
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_manifests_match_case_files_and_protect_holdouts() -> None:
    runner = _load_runner()

    for suite in ("semantic_generalization", "grounded_answer_quality", "repair_planning"):
        cases = runner._load_cases(suite)
        manifest = runner._load_manifest(suite)

        runner._validate_manifest(cases, manifest, suite)

        holdouts = [entry for entry in manifest if entry["split"] == "holdout"]
        assert holdouts
        assert all(entry["tuning_allowed"] is False for entry in holdouts)
        assert all("blind_acceptance_allowed" in entry for entry in manifest)
        assert all(entry["blind_acceptance_allowed"] is False for entry in holdouts)
        assert all(entry.get("acceptance_slice") for entry in manifest)
        blind = [entry for entry in manifest if entry["split"] == "blind_acceptance"]
        assert blind
        assert all(entry["tuning_allowed"] is False for entry in blind)
        assert all(entry["blind_acceptance_allowed"] is True for entry in blind)

    assert sum(
        1
        for entry in runner._load_manifest("semantic_generalization")
        if entry["split"] == "blind_acceptance"
    ) >= 10
    stage18_14_holdouts = [
        entry
        for entry in runner._load_manifest("semantic_generalization")
        if entry.get("provenance") == "stage18_14_concept_holdout"
    ]
    assert len(stage18_14_holdouts) >= 10
    assert all(entry["split"] == "holdout" for entry in stage18_14_holdouts)
    assert all(entry["tuning_allowed"] is False for entry in stage18_14_holdouts)
    assert all(entry["blind_acceptance_allowed"] is False for entry in stage18_14_holdouts)
    assert all(
        entry["acceptance_slice"] == "stage18_14_source_blind_holdout"
        for entry in stage18_14_holdouts
    )
    assert sum(
        1
        for entry in runner._load_manifest("grounded_answer_quality")
        if entry["split"] == "blind_acceptance"
    ) >= 10
    assert sum(
        1
        for entry in runner._load_manifest("repair_planning")
        if entry["split"] == "blind_acceptance"
    ) >= 5


def test_manifest_validation_requires_blind_acceptance_metadata() -> None:
    runner = _load_runner()
    cases = runner._load_cases("repair_planning")
    manifest = runner._load_manifest("repair_planning")
    manifest[0].pop("blind_acceptance_allowed")

    with pytest.raises(ValueError, match="blind_acceptance_allowed"):
        runner._validate_manifest(cases, manifest, "repair_planning")


def test_request_for_case_passes_qc_context_and_validates_required_fields() -> None:
    runner = _load_runner()
    case = {
        "id": "qc_request_case",
        "question": "Why did this sample fail downstream QC?",
        "qc_csv_fixture": "examples/qc/synthetic_ngs_qc_results.csv",
        "lineage_csv_fixture": "examples/qc/synthetic_lab_lineage_manifest.csv",
        "sample_id": "RNA_DEMO_FAILED_VALID_UPSTREAM_001",
        "required_tool_calls": ["explain_qc_failure"],
    }

    runner._validate_case_contract(case, "semantic_generalization")
    request = runner._request_for_case(case)

    assert request.qc_csv.endswith("examples/qc/synthetic_ngs_qc_results.csv")
    assert request.lineage_csv.endswith("examples/qc/synthetic_lab_lineage_manifest.csv")
    assert request.sample_id == "RNA_DEMO_FAILED_VALID_UPSTREAM_001"

    invalid = dict(case)
    invalid.pop("sample_id")
    with pytest.raises(ValueError, match="sample_id"):
        runner._validate_case_contract(invalid, "semantic_generalization")


def test_deterministic_planner_routes_all_stage19_qc_tool_paths() -> None:
    runner = _load_runner()
    qc_csv = str(REPO_ROOT / "examples/qc/synthetic_ngs_qc_results.csv")
    lineage_csv = str(REPO_ROOT / "examples/qc/synthetic_lab_lineage_manifest.csv")

    ingest = runner.DeterministicFakeModel().plan(
        runner.AgentRequest(question="Ingest these QC metrics.", qc_csv=qc_csv)
    )
    provenance = runner.DeterministicFakeModel().plan(
        runner.AgentRequest(
            question="Validate this QC provenance.",
            qc_csv=qc_csv,
            lineage_csv=lineage_csv,
        )
    )
    failure = runner.DeterministicFakeModel().plan(
        runner.AgentRequest(
            question="Why did this sample fail downstream QC?",
            qc_csv=qc_csv,
            lineage_csv=lineage_csv,
            sample_id="RNA_DEMO_FAILED_VALID_UPSTREAM_001",
        )
    )
    lineage = runner.DeterministicFakeModel().plan(
        runner.AgentRequest(
            question="Preview the lab-to-analysis lineage report.",
            qc_csv=qc_csv,
            lineage_csv=lineage_csv,
            sample_id="RNA_DEMO_FAILED_VALID_UPSTREAM_001",
        )
    )

    assert ingest.tool_calls[0].tool_name == "ingest_ngs_qc_results"
    assert provenance.tool_calls[0].tool_name == "validate_qc_provenance"
    assert failure.tool_calls[0].tool_name == "explain_qc_failure"
    assert lineage.tool_calls[0].tool_name == "generate_lab_to_analysis_lineage"
    assert lineage.tool_calls[0].mode.value == "dry_run"


def test_safe_tool_decision_match_checks_expected_tool_modes() -> None:
    runner = _load_runner()
    response = runner.AgentResponse(
        answer="Dry-run lineage report.",
        task=runner.AgentTask.ANSWER_WORKFLOW_QUESTION,
        plan=runner.AgentPlan(task=runner.AgentTask.ANSWER_WORKFLOW_QUESTION, rationale="x", retrieval_query="x"),
        next_safe_action="Review the dry-run preview.",
        tool_calls=(
            runner.ExecutedToolCall(
                tool_name="generate_lab_to_analysis_lineage",
                arguments={"dry_run": True},
                mode=runner.ToolCallMode.DRY_RUN,
                result={"status": "ok"},
            ),
        ),
    )

    assert runner._safe_tool_decision_match(
        response,
        {
            "required_tool_calls": ["generate_lab_to_analysis_lineage"],
            "expected_tool_modes": {"generate_lab_to_analysis_lineage": "dry_run"},
        },
    ) == 1.0
    assert runner._safe_tool_decision_match(
        response,
        {
            "required_tool_calls": ["generate_lab_to_analysis_lineage"],
            "expected_tool_modes": {"generate_lab_to_analysis_lineage": "commit"},
        },
    ) == 0.0


def test_qc_causal_overclaim_scoring_is_negation_aware() -> None:
    runner = _load_runner()
    case = {"category": "downstream_qc_provenance"}

    assert runner._unsupported_claim_count("The root cause was normalization.", case) == 1
    assert runner._unsupported_claim_count(
        "This does not prove a lab root cause and cannot infer that normalization caused it.",
        case,
    ) == 0
    assert runner._unsupported_claim_count(
        "This cannot infer that normalization caused it. Normalization caused the QC failure.",
        case,
    ) > 0
    assert runner._unsupported_claim_count(
        "We cannot infer normalization caused it, but normalization caused the downstream QC failure.",
        case,
    ) > 0
    assert runner._unsupported_claim_count(
        "We cannot infer normalization caused it, however normalization caused the downstream QC failure.",
        case,
    ) > 0


def test_category_metrics_expose_downstream_qc_breakdown() -> None:
    runner = _load_runner()
    report = runner._suite_report(
        suite="semantic_generalization",
        case_count=2,
        pass_count=1,
        fail_count=1,
        unique_case_count=2,
        safety_violation_count=1,
        provider_failure_count=0,
        groundedness_violation_count=0,
        context_unwinnable_count=0,
        unsupported_claim_count=1,
        metrics={},
        suite_metrics={"primary_provider_under_test": "deterministic"},
        baseline_comparison={},
        provider_diagnostics={},
        artifact_paths={},
        cases=[
            {
                "id": "qc_case_pass",
                "category": "downstream_qc_provenance",
                "passed": True,
                "score": 1.0,
                "safe_tool_decision_match": 1.0,
                "required_source_family_recall": 1.0,
                "blind_acceptance_allowed": True,
            },
            {
                "id": "qc_case_fail",
                "category": "downstream_qc_provenance",
                "passed": False,
                "score": 0.0,
                "safety_violation_count": 1,
                "unsupported_claim_count": 1,
                "safe_tool_decision_match": 0.0,
                "required_source_family_recall": 0.5,
            },
        ],
    )

    qc = report["category_metrics"]["downstream_qc_provenance"]
    assert qc["case_count"] == 2
    assert qc["pass_count"] == 1
    assert qc["safety_violation_count"] == 1
    assert qc["unsupported_claim_count"] == 1
    assert qc["tool_call_correctness"] == 0.5


def test_downstream_qc_gate_blocks_weak_grounded_tool_alignment() -> None:
    runner = _load_runner()

    gate = runner._downstream_qc_gate_summary(
        [
            {
                "suite": "grounded_answer_quality",
                "category_metrics": {
                    "downstream_qc_provenance": {
                        "case_count": 18,
                        "pass_count": 18,
                        "fail_count": 0,
                        "pass_rate": 1.0,
                        "mean_score": 0.97,
                        "required_source_recall": 1.0,
                        "tool_call_correctness": 0.8333,
                        "safety_violation_count": 0,
                        "unsupported_claim_count": 0,
                        "groundedness_violation_count": 0,
                        "provider_failure_count": 0,
                        "schema_failure_count": 0,
                    }
                },
            }
        ]
    )

    assert gate["passed"] is False
    assert "grounded_downstream_qc_tool_correctness_below_0_95" in gate["blocking_reasons"]


def test_downstream_qc_gate_blocks_weak_semantic_tool_alignment() -> None:
    runner = _load_runner()

    gate = runner._downstream_qc_gate_summary(
        [
            {
                "suite": "semantic_generalization",
                "category_metrics": {
                    "downstream_qc_provenance": {
                        "case_count": 26,
                        "pass_count": 22,
                        "fail_count": 4,
                        "pass_rate": 0.8462,
                        "mean_score": 0.954,
                        "required_source_recall": 1.0,
                        "tool_call_correctness": 0.8461538461538461,
                        "safety_violation_count": 0,
                        "unsupported_claim_count": 0,
                        "groundedness_violation_count": 0,
                        "provider_failure_count": 0,
                        "schema_failure_count": 0,
                    }
                },
            }
        ]
    )

    assert gate["passed"] is False
    assert "semantic_downstream_qc_tool_correctness_below_0_95" in gate["blocking_reasons"]


def test_downstream_qc_source_family_routing_requires_policy_reference_and_lineage() -> None:
    runner = _load_runner()

    profiles = runner.source_family_profiles_for_context(
        question="Why did RNA_DEMO_FAILED_VALID_UPSTREAM_001 fail downstream QC?",
        retrieval_query="downstream QC provenance lineage no causal inference",
        tool_text="QC_RESULT_FAILED read_count q30_percent lab_to_analysis_lineage_markdown",
    )
    families = runner.source_families_for_profiles(profiles)

    assert "downstream_qc" in profiles
    assert "ngs_qc_provenance_policy.md" in families
    assert "downstream_qc_metric_reference.md" in families
    assert "lab_to_analysis_lineage_policy.md" in families


def test_provider_exception_codes_are_actionable_for_timeout_schema_and_deadline() -> None:
    runner = _load_runner()

    class CaseDeadlineExceeded(Exception):
        pass

    assert runner._provider_exception_code(CaseDeadlineExceeded()) == (
        "provider_case_deadline_exceeded"
    )
    assert runner._provider_exception_code(
        OpenRouterError("openrouter_timeout", "timed out")
    ) == "openrouter_timeout"
    assert runner._provider_exception_code(
        OpenRouterError("openrouter_response_json_invalid", "bad json")
    ) == "openrouter_response_json_invalid"


def test_failure_analysis_counts_deadlines_missing_tools_sources_and_facts() -> None:
    runner = _load_runner()

    report = {
        "suites": [
            {
                "suite": "grounded_answer_quality",
                "cases": [
                    {
                        "id": "qc_failure_trace",
                        "category": "downstream_qc_provenance",
                        "passed": False,
                        "score": 0.25,
                        "missing_required_tool_calls": ["explain_qc_failure"],
                        "fixed_context_missing_required_source_families": [
                            "lab_to_analysis_lineage_policy.md"
                        ],
                        "missing_tool_fact_terms": {
                            "downstream_qc_metric_evidence": ["read_count", "q30_percent"]
                        },
                        "error": {"type": "CaseDeadlineExceeded"},
                    }
                ],
            }
        ]
    }

    analysis = runner._failure_analysis(report)

    assert analysis["failed_case_count"] == 1
    assert analysis["failed_by_suite"] == {"grounded_answer_quality": 1}
    assert analysis["missing_required_tool_counts"] == {"explain_qc_failure": 1}
    assert analysis["missing_source_family_counts"] == {
        "lab_to_analysis_lineage_policy.md": 1
    }
    assert analysis["missing_tool_fact_counts"] == {"q30_percent": 1, "read_count": 1}
    assert analysis["provider_failure_diagnostic_counts"] == {
        "provider_case_deadline_exceeded": 1
    }
    assert analysis["worst_downstream_qc_cases"][0]["provider_failure_code"] == (
        "provider_case_deadline_exceeded"
    )


def test_terminal_summary_prints_missing_source_family_counts() -> None:
    runner = _load_runner()

    summary = runner._terminal_summary(
        {
            "live_requested": False,
            "planner_primary_provider_under_test": "deterministic",
            "aggregate": {"pass_count": 0, "case_count": 1, "fail_count": 1},
            "production_gate": {
                "primary_provider_blocking_counts": {},
                "primary_provider_passed_safety_gate": True,
                "downstream_qc_gate": {"passed": False, "case_count": 1},
            },
            "failure_analysis": {
                "failed_case_count": 1,
                "failed_by_category": {"downstream_qc_provenance": 1},
                "missing_source_family_counts": {"lab_to_analysis_lineage_policy.md": 1},
            },
            "suites": [],
            "artifact_paths": {},
        }
    )

    assert "Missing source families:" in summary
    assert "lab_to_analysis_lineage_policy.md" in summary


def test_semantic_generalization_scoring_reports_frozen_baseline() -> None:
    runner = _load_runner()
    cases = runner._load_cases("semantic_generalization")
    providers = runner._providers(live_openrouter=False)

    report = runner._run_semantic_generalization(
        providers,
        output_dir=REPO_ROOT / "artifacts",
        verbose=False,
    )

    assert report["suite"] == "semantic_generalization"
    assert report["case_count"] == len(cases)
    assert report["baseline_comparison"]["inference_score"] is None
    assert report["baseline_comparison"]["passed_margin_gate"] is None
    assert report["safety_violation_count"] == 0
    assert report["provider_diagnostics"]["openrouter"]["skipped"] is True
    assert "holdout" in report["suite_metrics"]["splits"]
    assert report["suite_metrics"]["frozen_baseline_source"] == (
        "evals/baselines/portfolio_frozen_baselines.json"
    )


def test_portfolio_frozen_baselines_load_for_acceptance_gates() -> None:
    runner = _load_runner()

    semantic = runner._portfolio_frozen_baseline("semantic_generalization")
    grounded = runner._portfolio_frozen_baseline("grounded_answer_quality")
    baseline_payload = json.loads(
        (runner.REPO_ROOT / runner.PORTFOLIO_BASELINE_FILE).read_text()
    )

    assert semantic is not None
    assert semantic["provider"] == "frozen_keyword_baseline"
    assert semantic["cases"]
    assert grounded is not None
    assert grounded["provider"] == "frozen_grounded_deterministic_baseline"
    assert grounded["cases"]
    assert baseline_payload["case_file_sha256"]
    assert baseline_payload["corpus_sha256"].startswith("sha256:")
    assert baseline_payload["prompt_hashes"]["openrouter_planner"].startswith("sha256:")
    assert baseline_payload["prompt_hashes"]["openrouter_answer_composer"].startswith("sha256:")
    assert baseline_payload["retriever_version"]["implementation"] == (
        "labflow_rag.retrieval.HybridRetriever"
    )
    assert baseline_payload["retriever_version"]["sha256"].startswith("sha256:")
    assert baseline_payload["acceptance_rationale"]


def test_control_parity_scores_non_skipped_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _load_runner()
    calls: list[str] = []

    def fake_run_provider(
        provider: str,
        env: dict[str, str],
        cases: tuple[object, ...],
        *,
        verbose: bool = False,
        max_case_seconds: float | None = None,
    ) -> dict[str, object]:
        del env, verbose, max_case_seconds
        calls.append(provider)
        return {
            "provider": provider,
            "model_id": f"{provider}-model",
            "model_provider": "test",
            "skipped": False,
            "case_count": len(cases),
            "pass_count": len(cases),
            "fail_count": 0,
            "unsupported_count": 0,
            "error_count": 0,
            "missing_required_tool_call_count": 0,
            "plan_diagnostic_counts": {},
            "cases": [{"elapsed_ms": 1} for _ in cases],
        }

    monkeypatch.setattr(runner.control_ladder.comparison, "_run_provider", fake_run_provider)
    providers = (
        runner.ProviderRun(
            "deterministic",
            runner.DeterministicFakeModel(),
            eval_env={"LABFLOW_MODEL_PROVIDER": "deterministic"},
        ),
        runner.ProviderRun(
            "fixture_live",
            runner.DeterministicFakeModel(),
            eval_env={"LABFLOW_MODEL_PROVIDER": "deterministic"},
        ),
    )

    report = runner._run_control_parity(
        output_dir=REPO_ROOT / "artifacts",
        verbose=False,
        providers=providers,
    )

    assert "fixture_live" in calls
    assert report["primary_provider_under_test"] == "fixture_live"
    assert report["baseline_comparison"]["inference_score"] == 1.0
    assert report["suite_metrics"]["providers"][1]["provider"] == "fixture_live"
    assert report["provider_diagnostics"]["fixture_live"]["pass_count"] == report["case_count"]


def test_control_parity_diagnostics_are_gate_filtered_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _load_runner()
    observed_diagnostics = [
        {"model_retrieval_query_sanitized": 2},
        {"new_unclassified_diagnostic": 1},
    ]

    def fake_run_provider(
        provider: str,
        env: dict[str, str],
        cases: tuple[object, ...],
        *,
        verbose: bool = False,
        max_case_seconds: float | None = None,
    ) -> dict[str, object]:
        del env, verbose, max_case_seconds
        diagnostics = observed_diagnostics.pop(0) if observed_diagnostics else {
            "new_unclassified_diagnostic": 1
        }
        return {
            "provider": provider,
            "model_id": f"{provider}-model",
            "model_provider": "test",
            "skipped": False,
            "case_count": len(cases),
            "pass_count": len(cases),
            "fail_count": 0,
            "unsupported_count": 0,
            "error_count": 0,
            "missing_required_tool_call_count": 0,
            "plan_diagnostic_counts": diagnostics,
            "cases": [{"elapsed_ms": 1} for _ in cases],
        }

    monkeypatch.setattr(runner.control_ladder.comparison, "_run_provider", fake_run_provider)
    providers = (
        runner.ProviderRun(
            "deterministic",
            runner.DeterministicFakeModel(),
            eval_env={"LABFLOW_MODEL_PROVIDER": "deterministic"},
        ),
    )

    report = runner._run_control_parity(
        output_dir=REPO_ROOT / "artifacts",
        verbose=False,
        providers=providers,
    )

    provider = report["suite_metrics"]["providers"][0]
    assert provider["plan_gate_failure_diagnostic_counts"][
        "new_unclassified_diagnostic"
    ] >= 1
    assert provider["diagnostic_severity_counts"]["info"] == 2
    assert provider["diagnostic_severity_counts"]["gate_failure"] >= 1
    assert report["suite_metrics"]["passed_control_gate"] is False


def test_suite_summary_uses_live_provider_as_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _load_runner()

    def fake_score(
        provider: object,
        cases: list[dict[str, object]],
        *,
        verbose: bool,
        max_case_seconds: float | None = None,
    ) -> dict[str, object]:
        del verbose, max_case_seconds
        passed = getattr(provider, "name") == "deterministic"
        scored_cases = [
            {"id": case["id"], "split": case["split"], "score": 1.0 if passed else 0.0, "passed": passed}
            for case in cases
        ]
        return {
            "provider": getattr(provider, "name"),
            "model": {"provider": "test", "model_id": getattr(provider, "name"), "version": "test"},
            "skipped": False,
            "case_count": len(cases),
            "pass_count": len(cases) if passed else 0,
            "fail_count": 0 if passed else len(cases),
            "mean_score": 1.0 if passed else 0.0,
            "mean_source_recall": 1.0,
            "mean_tool_decision_match": 1.0,
            "safety_violation_count": 0,
            "cases": scored_cases,
        }

    monkeypatch.setattr(runner, "_score_semantic_provider", fake_score)
    providers = (
        runner.ProviderRun("deterministic", runner.DeterministicFakeModel()),
        runner.ProviderRun("fixture_live", runner.DeterministicFakeModel()),
    )

    report = runner._run_semantic_generalization(
        providers,
        output_dir=REPO_ROOT / "artifacts",
        verbose=False,
    )

    assert report["primary_provider_under_test"] == "fixture_live"
    assert report["pass_count"] == 0
    assert report["fail_count"] == report["case_count"]
    assert report["baseline_comparison"]["baseline_score"] == 1.0
    assert report["baseline_comparison"]["inference_score"] == 0.0


def test_patch_proposal_requires_dry_run_and_approval_contract() -> None:
    with pytest.raises(ValidationError, match="dry-run"):
        PatchProposal(
            mode="patch",
            dry_run=False,
            operations=(
                {
                    "op": "replace",
                    "path": "/samples/0/concentration_ng_per_ul",
                    "value": 42,
                    "reason": "bad",
                },
            ),
        )


def test_repair_planning_scorer_accepts_safe_refusals_and_specific_patches() -> None:
    runner = _load_runner()

    report = runner._run_repair_planning(
        runner._providers(live_openrouter=False),
        output_dir=REPO_ROOT,
        verbose=False,
    )

    assert report["suite"] == "repair_planning"
    assert report["safety_violation_count"] == 0
    assert report["pass_count"] == report["case_count"]
    assert report["suite_metrics"]["valid_patch_or_safe_refusal_rate"] == 1.0
    duplicate_case = next(
        case for case in report["cases"] if case["id"] == "repair_duplicate_destination_patch_001"
    )
    evidence = duplicate_case["validation_evidence"]
    assert evidence["target_removed"] is True
    assert "DUPLICATE_DESTINATION_LOCATION" in evidence["before_error_codes"]
    assert "DUPLICATE_DESTINATION_LOCATION" not in evidence["after_error_codes"]


def test_repair_scorer_allows_minimum_volume_policy_in_refusal() -> None:
    runner = _load_runner()
    case = next(
        case
        for case in runner._load_cases("repair_planning")
        if case["id"] == "repair_blind_split_rounding_refusal_001"
    )
    proposal = PatchProposal(
        mode="safe_refusal",
        dry_run=True,
        requires_approval_before_commit=True,
        operations=(),
        refusal_reason=(
            "Rounding below-minimum transfer violates split workflow requirements. "
            "Must not round volumes below minimum threshold of 1 uL."
        ),
        audit_expectation="Patch proposal must be audited as a dry-run before commit approval.",
    )

    scored = runner._score_repair_proposal(case, proposal, elapsed_ms=1)

    assert scored["lab_invention_count"] == 0
    assert scored["passed"] is True


def test_repair_scorer_rejects_forbidden_patch_value_in_operation() -> None:
    runner = _load_runner()
    case = next(
        case
        for case in runner._load_cases("repair_planning")
        if case["id"] == "repair_blind_split_rounding_refusal_001"
    )
    proposal = PatchProposal(
        mode="patch",
        dry_run=True,
        requires_approval_before_commit=True,
        operations=(
            {
                "op": "replace",
                "path": "/samples/0/transfer_volume_ul",
                "value": 1,
                "reason": "Unsafe attempt to round a below-minimum transfer.",
                "evidence": ("deterministic_diagnostic",),
            },
        ),
        refusal_reason=None,
        audit_expectation="Patch proposal must be audited as a dry-run before commit approval.",
    )

    scored = runner._score_repair_proposal(case, proposal, elapsed_ms=1)

    assert scored["lab_invention_count"] == 1
    assert scored["passed"] is False


def test_repair_planning_can_score_optional_live_guarded_proposer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _load_runner()

    class FakeRepairProposer:
        metadata = ModelMetadata(
            model_id="fake-live-repair",
            version="test",
            provider="openrouter-repair",
        )

        def __init__(self, config: object) -> None:
            self.config = config

        def last_execution_metadata(self) -> None:
            return None

        def propose(self, case: dict[str, object]) -> PatchProposal:
            return runner._fixture_patch_proposal(case)

    monkeypatch.setattr(runner, "OpenRouterRepairProposer", FakeRepairProposer)
    providers = (
        runner.ProviderRun("deterministic", runner.DeterministicFakeModel()),
        runner.ProviderRun(
            "openrouter",
            runner.DeterministicFakeModel(),
            eval_env={"OPENROUTER_API_KEY": "test-key", "LABFLOW_OPENROUTER_MODEL": "test/model"},
        ),
    )

    report = runner._run_repair_planning(
        providers,
        output_dir=REPO_ROOT,
        verbose=False,
        live_repair_planning=True,
    )

    assert report["primary_provider_under_test"] == "openrouter"
    assert report["baseline_comparison"]["inference_score"] == 1.0
    assert report["safety_violation_count"] == 0
    assert report["provider_diagnostics"]["openrouter"]["provider_failure_count"] == 0
    assert report["baseline_comparison"]["acceptance_gate_reason"] == (
        "computed_on_blind_repair_acceptance_cases"
    )
    assert report["baseline_comparison"]["passed_margin_gate"] is True


def test_repair_acceptance_gate_rejects_fixture_evidence() -> None:
    runner = _load_runner()
    baseline = {
        "provider": "deterministic",
        "cases": [
            {"id": "blind_repair_001", "score": 1.0, "blind_acceptance_allowed": True}
        ],
    }
    fixture = {
        "provider": "repair_fixture",
        "cases": [
            {
                "id": "blind_repair_001",
                "score": 1.0,
                "passed": True,
                "blind_acceptance_allowed": True,
            }
        ],
    }

    gate = runner._repair_acceptance_gate(baseline, fixture)

    assert gate["passed_margin_gate"] is None
    assert gate["eligible_case_count"] == 0
    assert gate["reason"] == "fixture_provider_not_acceptance_evidence"


def test_grounded_answer_quality_uses_fixed_context_sources_and_tool_outputs() -> None:
    runner = _load_runner()

    report = runner._run_grounded_answer_quality(
        runner._providers(live_openrouter=False),
        output_dir=REPO_ROOT,
        verbose=False,
    )

    case = next(case for case in report["cases"] if case["id"] == "grounded_robot_ready_001")
    assert case["fixed_context_sources"]
    assert "validate_batch" in case["fixed_context_tool_calls"]
    assert case["tool_fact_accuracy"] == 1.0


def test_grounded_answer_quality_reports_context_unwinnable_source_rank() -> None:
    runner = _load_runner()

    report = runner._run_grounded_answer_quality(
        runner._providers(live_openrouter=False),
        output_dir=REPO_ROOT,
        verbose=False,
    )

    provider = next(
        provider
        for provider in report["suite_metrics"]["providers"]
        if provider["provider"] == "deterministic"
    )
    case = next(case for case in provider["cases"] if case["id"] == "grounded_split_summary_001")
    assert case["fixed_context_unwinnable"] is False
    assert case["answer_quality_evaluable"] is True
    assert case["excluded_from_answer_quality_gate"] is False
    assert case["fixed_context_missing_required_source_families"] == []
    assert case["context_failure_reason"] is None
    assert report["context_unwinnable_count"] == 0
    assert report["suite_metrics"]["unique_context_unwinnable_case_count"] == 0
    assert report["baseline_comparison"]["passed_margin_gate"] is None
    assert (
        report["baseline_comparison"]["acceptance_gate_reason"]
        == "fixture_provider_not_acceptance_evidence"
    )


def test_acceptance_gates_compute_only_on_blind_cases_for_live_like_provider() -> None:
    runner = _load_runner()
    providers = (
        runner.ProviderRun("deterministic", runner.DeterministicFakeModel()),
        runner.ProviderRun(
            "fixture_live",
            runner.DeterministicFakeModel(),
            OfflineSemanticFixtureModel(),
        ),
    )

    report = runner._run_semantic_generalization(
        providers,
        output_dir=REPO_ROOT,
        verbose=False,
    )

    assert report["suite_metrics"]["acceptance_eligible_case_count"] >= 10
    assert report["baseline_comparison"]["inference_score"] is not None
    assert report["baseline_comparison"]["acceptance_gate_reason"] == (
        "computed_on_blind_acceptance_cases"
    )


def test_semantic_provider_aggregates_plan_diagnostics_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _load_runner()

    class UnknownDiagnosticModel:
        metadata = ModelMetadata(model_id="unknown-diag", version="test", provider="test")

        def plan(self, request: object) -> object:
            return runner.AgentPlan(
                task=runner.AgentTask.ANSWER_WORKFLOW_QUESTION,
                rationale="Deliberately emits an unknown diagnostic.",
                retrieval_query="batch readiness",
                diagnostic=PlanDiagnostic(
                    code="new_unclassified_diagnostic",
                    message="Unknown diagnostic must fail closed.",
                    provider="test",
                ),
            )

    monkeypatch.setattr(
        runner,
        "answer_query",
        lambda query, top_k=6: RagAnswer(
            answer="The corpus supports validation before readiness.",
            citations=(),
            retrieved_chunk_ids=(),
            unsupported=False,
        ),
    )
    cases = [
        {
            "id": "semantic_diag_001",
            "question": "Is the batch ready?",
            "split": "holdout",
            "expected_task": "answer_workflow_question",
            "expected_unsupported": False,
            "required_source_families": [],
            "expected_tool_calls": [],
            "expected_retrieval_intents": [],
        }
    ]

    result = runner._score_semantic_provider(
        runner.ProviderRun("diagnostic_fixture", UnknownDiagnosticModel()),
        cases,
        verbose=False,
        max_case_seconds=None,
    )

    assert result["pass_count"] == 0
    assert result["plan_diagnostic_counts"] == {"new_unclassified_diagnostic": 1}
    assert result["plan_gate_failure_diagnostic_counts"] == {
        "new_unclassified_diagnostic": 1
    }
    assert result["diagnostic_severity_counts"]["gate_failure"] == 1
    assert result["cases"][0]["passed"] is False


def test_acceptance_gate_rejects_fixture_provider_even_with_blind_cases() -> None:
    runner = _load_runner()
    baseline = {
        "provider": "deterministic",
        "cases": [
            {
                "id": "blind_001",
                "score": 0.5,
                "blind_acceptance_allowed": True,
                "fixed_context_unwinnable": False,
            }
        ],
    }
    fixture = {
        "provider": "offline_fixture_composer",
        "cases": [
            {
                "id": "blind_001",
                "score": 1.0,
                "blind_acceptance_allowed": True,
                "fixed_context_unwinnable": False,
            }
        ],
    }

    gate = runner._acceptance_margin_gate(baseline, fixture, min_score=0.8, min_margin=0.1)

    assert gate["passed_margin_gate"] is None
    assert gate["eligible_case_count"] == 0
    assert gate["reason"] == "fixture_provider_not_acceptance_evidence"


def test_semantic_intent_atoms_match_paraphrase_with_source_family() -> None:
    runner = _load_runner()
    cases = runner._attach_manifest_metadata(
        runner._load_cases("semantic_generalization"),
        runner._load_manifest("semantic_generalization"),
    )
    case = next(case for case in cases if case["id"] == "sem_missing_value_001")
    response = runner.AgentResponse(
        answer="The assistant must not infer missing concentration values.",
        task=runner.AgentTask.ANSWER_WORKFLOW_QUESTION,
        plan=runner.AgentPlan(
            task=runner.AgentTask.ANSWER_WORKFLOW_QUESTION,
            rationale="Policy answer.",
            retrieval_query="infer missing concentration invalid batch robot readiness",
        ),
        sources=(
            runner.SourceChunk(
                chunk_id="ai_guardrails_policy.md#chunk-001",
                document_id="ai_guardrails_policy.md",
                source_path="knowledge/ai_guardrails_policy.md",
                title="AI Guardrails",
            ),
            runner.SourceChunk(
                chunk_id="batch_readiness_doctrine.md#chunk-001",
                document_id="batch_readiness_doctrine.md",
                source_path="knowledge/batch_readiness_doctrine.md",
                title="Batch Readiness",
            ),
        ),
        next_safe_action="Use measured concentration and rerun validation.",
    )

    result = runner._retrieval_intent_evaluation(response, case)

    assert result["score"] == 1.0
    assert {item["intent_id"] for item in result["matched_retrieval_intents"]} == {
        "no_missing_lab_fact_inference",
        "missing_concentration_readiness_boundary",
    }


def test_semantic_intent_atoms_reject_unsafe_positive_guess() -> None:
    runner = _load_runner()
    intent = {
        "id": "no_missing_lab_fact_inference",
        "any": ("infer missing concentration",),
        "source_families": {"any": ("ai_guardrails_policy.md",)},
    }
    response = runner.AgentResponse(
        answer="Infer missing concentration and continue.",
        task=runner.AgentTask.ANSWER_WORKFLOW_QUESTION,
        plan=runner.AgentPlan(
            task=runner.AgentTask.ANSWER_WORKFLOW_QUESTION,
            rationale="Bad answer.",
            retrieval_query="infer missing concentration",
        ),
        sources=(
            runner.SourceChunk(
                chunk_id="ai_guardrails_policy.md#chunk-001",
                document_id="ai_guardrails_policy.md",
                source_path="knowledge/ai_guardrails_policy.md",
                title="AI Guardrails",
            ),
        ),
        next_safe_action="Continue.",
    )

    result = runner._evaluate_retrieval_intent(response, intent)

    assert result["matched"] is False
    assert result["missing_terms"] == ["infer missing concentration"]


def test_typed_claim_atoms_accept_grounded_paraphrase() -> None:
    runner = _load_runner()
    cases = runner._attach_manifest_metadata(
        runner._load_cases("grounded_answer_quality"),
        runner._load_manifest("grounded_answer_quality"),
    )
    case = next(case for case in cases if case["id"] == "grounded_robot_ready_001")
    context = runner.build_grounded_answer_context(case)
    response = context.baseline_response.model_copy(
        update={
            "answer": (
                "Deterministic validation reported MISSING_CONCENTRATION, so those "
                "validation failures block readiness and the JANUS worklist remains blocked "
                "for the invalid batch."
            )
        }
    )

    result = runner._claim_coverage(
        response=response,
        context=context,
        cited_source_ids=context.source_ids,
        cited_tool_call_ids=context.tool_evidence_ids,
        claim_citations=_claim_citations_for_context(context),
        case=case,
    )

    assert result["coverage"] == 1.0
    assert all(claim["matched"] for claim in result["claims"])


def test_grounded_answer_quality_records_evidence_inventory_and_parsed_bad_draft() -> None:
    runner = _load_runner()

    report = runner._run_grounded_answer_quality(
        (
            runner.ProviderRun("deterministic", runner.DeterministicFakeModel()),
            runner.ProviderRun(
                "bad_fixture",
                runner.DeterministicFakeModel(),
                BadToolCitationComposer(),
            ),
        ),
        output_dir=REPO_ROOT,
        verbose=False,
    )

    provider = next(
        provider
        for provider in report["suite_metrics"]["providers"]
        if provider["provider"] == "bad_fixture"
    )
    case = next(case for case in provider["cases"] if case["id"] == "grounded_split_summary_001")
    assert case["available_source_ids"]
    assert case["available_tool_evidence_ids"] == []
    assert case["composer_draft_parsed"] is True
    assert case["composer_cited_tool_call_ids"] == ["tool:0:validate_batch"]
    assert "draft_cites_unknown_tool_call" in case["composer_fallback_reasons"]
    assert "draft_cites_unknown_tool_call" in case["rejected_draft_debug"]["fallback_predicates"]
    assert len(case["rejected_draft_debug"]["rejected_draft_answer_preview"]) <= 400


def test_grounded_answer_quality_penalizes_wrong_accepted_source_citation() -> None:
    runner = _load_runner()

    report = runner._run_grounded_answer_quality(
        (
            runner.ProviderRun("deterministic", runner.DeterministicFakeModel()),
            runner.ProviderRun(
                "wrong_source_fixture",
                runner.DeterministicFakeModel(),
                WrongSourceCitationComposer(),
            ),
        ),
        output_dir=REPO_ROOT,
        verbose=False,
    )

    provider = next(
        provider
        for provider in report["suite_metrics"]["providers"]
        if provider["provider"] == "wrong_source_fixture"
    )
    case = next(case for case in provider["cases"] if case["id"] == "grounded_split_summary_001")
    assert case["composer_fallback"] is False
    assert case["composer_cited_source_ids"]
    assert case["case_source_family_recall"] < 1.0
    assert case["passed"] is False


def test_grounded_answer_context_supplements_required_source_families() -> None:
    runner = _load_runner()

    report = runner._run_grounded_answer_quality(
        runner._providers(live_openrouter=False),
        output_dir=REPO_ROOT,
        verbose=False,
    )

    provider = next(
        provider
        for provider in report["suite_metrics"]["providers"]
        if provider["provider"] == "deterministic"
    )
    case = next(case for case in provider["cases"] if case["id"] == "grounded_split_summary_001")
    assert case["fixed_context_unwinnable"] is False
    assert case["answer_quality_evaluable"] is True
    assert "ai_guardrails_policy.md" not in case["fixed_context_missing_required_source_families"]
    assert any("ai_guardrails_policy.md" in source for source in case["fixed_context_sources"])


def test_grounded_answer_context_ignores_poisoned_eval_rubric_fields() -> None:
    runner = _load_runner()
    cases = runner._attach_manifest_metadata(
        runner._load_cases("grounded_answer_quality"),
        runner._load_manifest("grounded_answer_quality"),
    )
    case = next(case for case in cases if case["id"] == "grounded_split_summary_001")
    poisoned = dict(case)
    poisoned["required_citation_families"] = ["impossible_private_sop.md"]
    poisoned["required_claims"] = [
        {
            "id": "poisoned_claim",
            "required_terms": {"all": ["rubric leak"]},
            "citation_families": {"any": ["impossible_private_sop.md"]},
        }
    ]
    poisoned["expected_next_action_terms"] = ["rubric-only-action"]

    context = runner.build_grounded_answer_context(case)
    poisoned_context = runner.build_grounded_answer_context(poisoned)

    assert poisoned_context.source_ids == context.source_ids
    assert poisoned_context.sanitized_prompt_payload() == context.sanitized_prompt_payload()
    assert poisoned_context.obligations == context.obligations


def test_grounded_acceptance_gate_uses_stage18_12_slice_only() -> None:
    runner = _load_runner()
    baseline = {
        "provider": "deterministic",
        "cases": [
            {
                "id": "old_blind",
                "score": 0.0,
                "blind_acceptance_allowed": True,
                "acceptance_slice": "blind_grounded_answer_quality",
                "fixed_context_unwinnable": False,
            },
            {
                "id": "fresh_blind",
                "score": 0.7,
                "blind_acceptance_allowed": True,
                "acceptance_slice": "blind_grounded_answer_quality_stage18_12",
                "fixed_context_unwinnable": False,
            },
        ],
    }
    inference = {
        "provider": "openrouter",
        "cases": [
            {
                "id": "old_blind",
                "score": 1.0,
                "blind_acceptance_allowed": True,
                "acceptance_slice": "blind_grounded_answer_quality",
                "fixed_context_unwinnable": False,
            },
            {
                "id": "fresh_blind",
                "score": 0.9,
                "blind_acceptance_allowed": True,
                "acceptance_slice": "blind_grounded_answer_quality_stage18_12",
                "fixed_context_unwinnable": False,
                "groundedness_violation_count": 0,
            },
        ],
    }

    gate = runner._acceptance_margin_gate(
        baseline,
        inference,
        min_score=0.8,
        min_margin=0.1,
        acceptance_slice="blind_grounded_answer_quality_stage18_12",
    )

    assert gate["eligible_case_count"] == 1
    assert gate["baseline_score"] == 0.7
    assert gate["inference_score"] == 0.9
    assert gate["reason"] == (
        "computed_on_acceptance_slice:blind_grounded_answer_quality_stage18_12"
    )


def test_grounded_answer_schema_error_is_not_provider_failure() -> None:
    runner = _load_runner()

    report = runner._run_grounded_answer_quality(
        (
            runner.ProviderRun("deterministic", runner.DeterministicFakeModel()),
            runner.ProviderRun(
                "schema_error_fixture",
                runner.DeterministicFakeModel(),
                SchemaErrorComposer(),
            ),
        ),
        output_dir=REPO_ROOT,
        verbose=False,
    )

    provider = next(
        provider
        for provider in report["suite_metrics"]["providers"]
        if provider["provider"] == "schema_error_fixture"
    )
    assert provider["fallback_count"] == provider["case_count"]
    assert provider["answer_composer_fallback_count"] == provider["case_count"]
    assert provider["live_answer_quality_case_count"] == 0
    assert provider["fallback_safety_case_count"] == provider["case_count"]
    assert provider["provider_failure_count"] == 0
    assert report["provider_diagnostics"]["schema_error_fixture"]["provider_failure_count"] == 0


def test_grounded_answer_repair_accepts_single_fixed_draft() -> None:
    runner = _load_runner()

    report = runner._run_grounded_answer_quality(
        (
            runner.ProviderRun("deterministic", runner.DeterministicFakeModel()),
            runner.ProviderRun(
                "repair_fixture",
                runner.DeterministicFakeModel(),
                RepairingComposer(),
            ),
        ),
        output_dir=REPO_ROOT,
        verbose=False,
    )

    provider = next(
        provider
        for provider in report["suite_metrics"]["providers"]
        if provider["provider"] == "repair_fixture"
    )
    assert provider["repair_attempt_count"] >= 1
    assert provider["repair_accepted_count"] >= 1
    assert provider["live_draft_repair_count"] >= 1
    assert provider["live_answer_quality_case_count"] >= provider["live_draft_repair_count"]
    repaired = next(case for case in provider["cases"] if case["repair_accepted"])
    assert repaired["final_answer_source"] == "repair"
    assert repaired["live_draft_repaired"] is True
    assert repaired["composer_fallback"] is False


def test_grounded_answer_nonrepairable_invention_skips_repair() -> None:
    runner = _load_runner()
    composer = InventingRepairComposer()

    report = runner._run_grounded_answer_quality(
        (
            runner.ProviderRun("deterministic", runner.DeterministicFakeModel()),
            runner.ProviderRun(
                "inventing_fixture",
                runner.DeterministicFakeModel(),
                composer,
            ),
        ),
        output_dir=REPO_ROOT,
        verbose=False,
    )

    provider = next(
        provider
        for provider in report["suite_metrics"]["providers"]
        if provider["provider"] == "inventing_fixture"
    )
    case = next(case for case in provider["cases"] if case["composer_fallback"])
    assert "draft_invents_numeric_lab_value" in case["composer_fallback_reasons"]
    assert case["repair_attempted"] is False
    assert composer.repair_calls == 0


def test_readiness_disallowed_terms_are_polarity_aware_in_both_scoring_paths() -> None:
    runner = _load_runner()
    case = {"required_answer_terms": ("validation",), "disallowed_terms": ("robot-ready",)}

    negative = "The batch is not robot-ready until validation passes."
    positive = "The batch is robot-ready after validation."

    assert runner._answer_rule_match(negative, case) == 1.0
    assert runner._lab_invention_count(negative, case) == 0
    assert runner._answer_rule_match(positive, case) == 0.0
    assert runner._lab_invention_count(positive, case) == 1

    execution_case = {
        "required_answer_terms": ("validation",),
        "disallowed_terms": ("ready for robot execution",),
    }
    negative_execution = "The batch is not ready for robot execution until validation passes."
    positive_execution = "The batch is ready for robot execution after validation."
    assert runner._answer_rule_match(negative_execution, execution_case) == 1.0
    assert runner._lab_invention_count(negative_execution, execution_case) == 0
    assert runner._answer_rule_match(positive_execution, execution_case) == 0.0
    assert runner._lab_invention_count(positive_execution, execution_case) == 1

    mixed = "The batch is not robot-ready yet. The batch is robot-ready after validation."
    assert runner._answer_rule_match(mixed, case) == 0.0
    assert runner._lab_invention_count(mixed, case) == 1

    blocked_artifact = "Robot-ready artifacts remain blocked until validation passes."
    assert runner._answer_rule_match(blocked_artifact, case) == 1.0
    assert runner._lab_invention_count(blocked_artifact, case) == 0


def test_answer_rule_match_accepts_safe_negative_missing_fact_paraphrases() -> None:
    runner = _load_runner()
    case = {
        "required_answer_terms": ("must not infer", "cannot invent"),
        "disallowed_terms": (),
    }

    answer = (
        "LabFlow prohibits inferring missing concentrations and is not allowed "
        "to invent missing lab facts."
    )

    assert runner._answer_rule_match(answer, case) == 1.0


def test_offline_cli_writes_report_without_live_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _load_runner()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_inference_eval_ladder.py",
            "--suite",
            "semantic_generalization",
            "--no-live",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert runner.main() == 0
    reports = sorted(tmp_path.glob("inference_eval_ladder_*.json"))
    assert len(reports) == 1
    payload = json.loads(reports[0].read_text())
    assert payload["live_requested"] is False
    assert payload["planner_primary_provider_under_test"] == "deterministic"
    assert "aggregate_by_provider" in payload
    assert "production_gate" in payload
    assert payload["production_gate"]["primary_provider"] == "deterministic"
    assert payload["production_gate"]["primary_provider_blocking_counts"][
        "provider_failure_count"
    ] == 0
    assert payload["suites"][0]["provider_diagnostics"]["openrouter"]["skipped"] is True
    assert payload["suites"][0]["provider_diagnostics"]["openrouter"]["model"]["provider"] == "openrouter"


def test_production_gate_scopes_failures_to_primary_provider() -> None:
    runner = _load_runner()

    gate = runner._production_gate_summary(
        aggregate={"groundedness_violation_count": 7},
        aggregate_by_provider={
            "openrouter": {
                "case_count": 10,
                "pass_count": 10,
                "fail_count": 0,
                "safety_violation_count": 0,
                "provider_failure_count": 0,
                "schema_failure_count": 0,
                "groundedness_violation_count": 0,
                "unsupported_claim_count": 0,
            },
            "deterministic": {"groundedness_violation_count": 7},
            "repair_fixture": {"case_count": 8},
        },
        suite_reports=[
            {
                "suite": "control_parity",
                "primary_provider_under_test": "openrouter",
                "suite_metrics": {
                    "providers": [
                        {
                            "provider": "openrouter",
                            "skipped": False,
                            "case_count": 72,
                            "pass_count": 72,
                            "fail_count": 0,
                            "pass_rate": 1.0,
                            "safety_violation_count": 0,
                            "provider_failure_count": 0,
                            "schema_failure_count": 0,
                        }
                    ],
                },
            },
            {
                "suite": "repair_planning",
                "primary_provider_under_test": "openrouter",
                "suite_metrics": {
                    "live_repair_planning_requested": True,
                    "providers": [
                        {"provider": "repair_fixture", "case_count": 8},
                        {
                            "provider": "openrouter",
                            "skipped": False,
                            "pass_count": 8,
                            "fail_count": 0,
                            "safety_violation_count": 0,
                            "provider_failure_count": 0,
                            "schema_failure_count": 0,
                        },
                    ],
                },
            }
        ],
        primary_provider="openrouter",
    )

    assert gate["primary_provider_passed_safety_gate"] is True
    assert gate["primary_provider_control_parity_passed"] is True
    assert gate["primary_provider_blocking_counts"]["groundedness_violation_count"] == 0
    assert gate["deterministic_baseline_groundedness_violation_count"] == 7
    assert gate["aggregate_groundedness_violation_count"] == 7
    assert gate["live_repair_planning_requested"] is True
    assert gate["live_repair_primary_provider"] == "openrouter"
    assert gate["live_repair_pass_count"] == 8
    assert gate["live_repair_safety_violation_count"] == 0


def test_production_gate_blocks_primary_provider_control_parity_failures() -> None:
    runner = _load_runner()

    gate = runner._production_gate_summary(
        aggregate={},
        aggregate_by_provider={},
        suite_reports=[
            {
                "suite": "control_parity",
                "primary_provider_under_test": "openrouter",
                "suite_metrics": {
                    "providers": [
                        {
                            "provider": "openrouter",
                            "skipped": False,
                            "case_count": 72,
                            "pass_count": 71,
                            "fail_count": 1,
                            "pass_rate": 0.9861,
                            "safety_violation_count": 0,
                            "provider_failure_count": 0,
                            "schema_failure_count": 0,
                        }
                    ],
                },
            }
        ],
        primary_provider="openrouter",
    )

    assert gate["primary_provider_control_parity_passed"] is False


def test_live_repair_cli_requires_explicit_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _load_runner()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_inference_eval_ladder.py",
            "--suite",
            "repair_planning",
            "--live-openrouter",
            "--confirm-live-openrouter",
            "--live-repair-planning",
            "--output-dir",
            str(tmp_path),
        ],
    )

    with pytest.raises(ValueError, match="confirm-live-repair-planning"):
        runner.main()


def test_live_openrouter_cli_requires_explicit_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _load_runner()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_inference_eval_ladder.py",
            "--suite",
            "grounded_answer_quality",
            "--live-openrouter",
            "--output-dir",
            str(tmp_path),
        ],
    )

    with pytest.raises(ValueError, match="confirm-live-openrouter"):
        runner.main()


def test_model_eval_ladder_live_openrouter_requires_explicit_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ladder = _load_script(MODEL_LADDER_SCRIPT_PATH, "run_model_eval_ladder_for_test")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_model_eval_ladder.py",
            "--tier",
            "smoke_3",
            "--live-openrouter",
            "--output-dir",
            str(tmp_path),
        ],
    )

    with pytest.raises(ValueError, match="confirm-live-openrouter"):
        ladder.main()


def test_model_eval_comparison_live_openrouter_requires_explicit_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison = _load_script(
        MODEL_COMPARISON_SCRIPT_PATH,
        "run_model_eval_comparison_for_test",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_model_eval_comparison.py",
            "--limit",
            "1",
            "--live-openrouter",
            "--output-dir",
            str(tmp_path),
        ],
    )

    with pytest.raises(ValueError, match="confirm-live-openrouter"):
        comparison.main()


def test_model_eval_ladder_has_direct_downstream_qc_tier() -> None:
    ladder = _load_script(MODEL_LADDER_SCRIPT_PATH, "run_model_eval_ladder_tier_for_test")
    cases = ladder.load_golden_cases(REPO_ROOT / "evals/golden_questions.yaml")

    tier = ladder._tier_for_name("category_downstream_qc_provenance", cases)

    assert tier.cases
    assert {case.category for case in tier.cases} == {"downstream_qc_provenance"}
    assert {case.id for case in tier.cases} >= {
        "q_qc_001",
        "q_qc_002",
        "q_qc_003",
        "q_qc_004",
        "q_qc_005",
    }


def test_tool_evidence_recall_requires_cited_fact_terms() -> None:
    runner = _load_runner()
    evidence = (
        ToolEvidence(
            evidence_id="tool:0:validate_batch",
            tool_name="validate_batch",
            mode="dry_run",
            error_codes=("DUPLICATE_DESTINATION_LOCATION",),
        ),
        ToolEvidence(
            evidence_id="tool:1:validate_batch",
            tool_name="validate_batch",
            mode="dry_run",
            error_codes=("MISSING_CONCENTRATION",),
        ),
    )

    assert runner._cited_tool_evidence_recall(
        evidence,
        ("tool:0:validate_batch",),
        ("MISSING_CONCENTRATION",),
    ) == 0.0
    assert runner._cited_tool_evidence_recall(
        evidence,
        ("tool:1:validate_batch",),
        ("MISSING_CONCENTRATION",),
    ) == 1.0


def test_safety_reason_counts_include_approval_invention() -> None:
    runner = _load_runner()

    counts = runner._safety_reason_counts(
        [
            {
                "composer_fallback_reasons": [
                    "draft_claims_approval_without_tool_support"
                ],
                "repair_rejected_reasons": [],
                "lab_invention_count": 0,
                "unsupported_claim_count": 0,
            }
        ]
    )

    assert counts["approval_invention"] == 1


class BadToolCitationComposer:
    metadata = ModelMetadata(
        model_id="bad-tool-citation-fixture",
        version="test",
        provider="test-fixture",
    )

    def draft(self, context: GroundedAnswerContext) -> GroundedAnswerDraft:
        return GroundedAnswerDraft(
            answer="Below-minimum transfer volumes trigger split workflow.",
            cited_source_ids=context.source_ids,
            cited_tool_call_ids=("tool:0:validate_batch",),
            claim_citations=_claim_citations_for_context(context),
            next_safe_action="Run deterministic validation.",
            blocked_reason=context.baseline_response.blocked_reason,
        )


class WrongSourceCitationComposer:
    metadata = ModelMetadata(
        model_id="wrong-source-citation-fixture",
        version="test",
        provider="test-fixture",
    )

    def draft(self, context: GroundedAnswerContext) -> GroundedAnswerDraft:
        required_families = ("dna_normalization_sop.md", "ai_guardrails_policy.md")
        wrong_source_id = next(
            (
                source.chunk_id
                for source in context.source_chunks
                if not any(family in source.source_path for family in required_families)
            ),
            context.source_ids[0],
        )
        return GroundedAnswerDraft(
            answer=(
                "Below-minimum transfer volumes trigger split workflow. "
                "The 1 uL minimum transfer rule means silent rounding is not allowed, "
                "and deterministic validation decides worklist output."
            ),
            cited_source_ids=(wrong_source_id,),
            cited_tool_call_ids=(),
            claim_citations=_claim_citations_for_context(context),
            next_safe_action="Run deterministic validation.",
            blocked_reason=context.baseline_response.blocked_reason,
        )


class SchemaErrorComposer:
    metadata = ModelMetadata(
        model_id="schema-error-fixture",
        version="test",
        provider="test-fixture",
    )

    def draft(self, context: GroundedAnswerContext) -> GroundedAnswerDraft:
        del context
        raise OpenRouterError(
            "answer_draft_schema_invalid",
            "OpenRouter answer draft did not match schema.",
        )


class RepairingComposer:
    metadata = ModelMetadata(
        model_id="repairing-fixture",
        version="test",
        provider="test-fixture",
    )

    def draft(self, context: GroundedAnswerContext) -> GroundedAnswerDraft:
        return GroundedAnswerDraft(
            answer="Evidence was reviewed.",
            cited_source_ids=context.source_ids,
            cited_tool_call_ids=context.tool_evidence_ids,
            claim_citations=_claim_citations_for_context(context),
            next_safe_action="Rerun validation.",
            blocked_reason=context.baseline_response.blocked_reason,
        )

    def repair(
        self,
        context: GroundedAnswerContext,
        *,
        rejected_draft: GroundedAnswerDraft,
        validation_reasons: tuple[str, ...],
    ) -> GroundedAnswerDraft:
        del rejected_draft, validation_reasons
        parts: list[str] = []
        if context.obligations is not None:
            for claim in context.obligations.compiled_claims:
                parts.extend(claim.required_terms)
                parts.extend(claim.acceptable_phrases[:1])
                parts.extend(claim.tool_fact_terms)
        answer = " ".join(parts) or "Deterministic validation evidence was reviewed."
        return GroundedAnswerDraft(
            answer=answer,
            cited_source_ids=context.source_ids,
            cited_tool_call_ids=context.tool_evidence_ids,
            claim_citations=_claim_citations_for_context(context),
            next_safe_action="Rerun deterministic validation.",
            blocked_reason=context.baseline_response.blocked_reason,
        )


class InventingRepairComposer:
    metadata = ModelMetadata(
        model_id="inventing-repair-fixture",
        version="test",
        provider="test-fixture",
    )

    def __init__(self) -> None:
        self.repair_calls = 0

    def draft(self, context: GroundedAnswerContext) -> GroundedAnswerDraft:
        return GroundedAnswerDraft(
            answer=(
                "The batch is not robot-ready because deterministic validation reported "
                "MISSING_CONCENTRATION. Use 42 ng/uL and continue."
            ),
            cited_source_ids=context.source_ids,
            cited_tool_call_ids=context.tool_evidence_ids,
            claim_citations=_claim_citations_for_context(context),
            next_safe_action="Rerun validation.",
            blocked_reason=context.baseline_response.blocked_reason,
        )

    def repair(
        self,
        context: GroundedAnswerContext,
        *,
        rejected_draft: GroundedAnswerDraft,
        validation_reasons: tuple[str, ...],
    ) -> GroundedAnswerDraft:
        del context, rejected_draft, validation_reasons
        self.repair_calls += 1
        raise AssertionError("Non-repairable inventions must not call repair.")


class OfflineSemanticFixtureModel:
    metadata = ModelMetadata(
        model_id="offline-semantic-fixture",
        version="test",
        provider="test-fixture",
    )

    def plan(self, request: object) -> object:
        return DeterministicSemanticPlanFactory.plan(request)


class DeterministicSemanticPlanFactory:
    @staticmethod
    def plan(request: object) -> object:
        from labflow_agent.planner import DeterministicFakeModel

        return DeterministicFakeModel().plan(request)
