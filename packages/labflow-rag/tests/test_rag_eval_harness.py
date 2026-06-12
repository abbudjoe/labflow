from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import labflow_rag.evals.runner as runner_module
from labflow_rag import RagAnswer
from labflow_rag.evals import EvalCase, EvalRunConfig, load_golden_cases, run_eval, write_eval_report

TARGET_RETRIEVAL_CLEANUP_CASE_IDS = frozenset(
    {
        "q_batch_001",
        "q_split_001",
        "q_split_002",
        "q_rna_003",
        "q_janus_004",
        "q_molar_001",
        "q_molar_002",
        "q_guardrails_001",
        "q_throughput_003",
        "q_sop_alignment_001",
        "q_sop_alignment_002",
        "q_sop_alignment_003",
        "q_qc_001",
        "q_qc_002",
        "q_qc_003",
        "q_qc_004",
        "q_qc_005",
    }
)


def test_load_golden_cases() -> None:
    cases = load_golden_cases("evals/golden_questions.yaml")

    assert len(cases) >= 30
    assert len({case.id for case in cases}) == len(cases)
    split = next(case for case in cases if case.id == "q_split_001")
    assert split.category == "split_workflow"
    assert "dna_normalization_sop.md" in split.required_sources


def test_run_retrieval_only_eval_passes_known_baseline_cases() -> None:
    cases_by_id = {case.id: case for case in load_golden_cases("evals/golden_questions.yaml")}
    baseline_cases = (
        cases_by_id["q_split_001"],
        cases_by_id["q_janus_004"],
    )

    report = run_eval(
        EvalRunConfig(top_k=12, retrieval_only=True, eval_run_id="eval_test_baseline"),
        cases=baseline_cases,
    )

    assert report.metrics.case_count == 2
    assert report.metrics.passed_count == 2
    assert report.metrics.retrieval_recall_at_k == 1.0
    report_json = report.to_json_dict()
    assert report_json["prompt_model"]["prompt_id"] == "rag_answer"
    assert report_json["prompt_model"]["prompt_version"] == "0.1.0"
    assert report_json["prompt_model"]["prompt_sha256"].startswith("sha256:")
    assert report_json["prompt_model"]["model_id"] == "deterministic_rag_eval"
    assert report_json["baseline_comparison"] == {
        "baseline_report_path": None,
        "baseline_metrics": None,
        "metric_deltas": {},
    }
    json.dumps(report_json)


def test_retrieval_only_eval_passes_all_golden_cases_at_top_k_six() -> None:
    report = run_eval(
        EvalRunConfig(top_k=6, retrieval_only=True, eval_run_id="eval_test_all_retrieval")
    )

    results_by_id = {case.case_id: case for case in report.cases}
    expected_case_count = len(load_golden_cases("evals/golden_questions.yaml"))
    assert report.top_k == 6
    assert report.retrieval_only is True
    assert report.metrics.case_count == expected_case_count
    assert report.metrics.failed_count == 0
    assert report.metrics.retrieval_recall_at_k == 1.0
    assert TARGET_RETRIEVAL_CLEANUP_CASE_IDS <= set(results_by_id)
    assert all(results_by_id[case_id].passed for case_id in TARGET_RETRIEVAL_CLEANUP_CASE_IDS)


def test_eval_fails_when_required_source_missing() -> None:
    case = EvalCase(
        id="q_missing_source",
        category="contract",
        question="What happens when transfer volume is below 1 uL?",
        required_sources=("not_a_real_source.md",),
        expected_answer_contains=("split",),
        disallowed_answer_contains=(),
        required_tool_calls=(),
    )

    report = run_eval(
        EvalRunConfig(top_k=6, retrieval_only=True, eval_run_id="eval_missing_source"),
        cases=(case,),
    )

    result = report.cases[0]
    assert result.passed is False
    assert result.missing_required_sources == ("not_a_real_source.md",)
    assert report.metrics.failed_count == 1


def test_full_eval_fails_when_required_citation_is_missing(monkeypatch: Any) -> None:
    case = EvalCase(
        id="q_missing_citation",
        category="contract",
        question="What happens when transfer volume is below 1 uL?",
        required_sources=("dna_normalization_sop.md",),
        expected_answer_contains=("split workflow",),
        disallowed_answer_contains=(),
        required_tool_calls=(),
    )

    def answer_without_citations(*_args: Any, **_kwargs: Any) -> RagAnswer:
        return RagAnswer(
            answer="split workflow",
            citations=(),
            retrieved_chunk_ids=("dna_normalization_sop.md#chunk-001",),
            unsupported=False,
        )

    monkeypatch.setattr(runner_module, "answer_query", answer_without_citations)
    report = run_eval(EvalRunConfig(top_k=6, eval_run_id="eval_missing_citation"), cases=(case,))

    result = report.cases[0]
    assert result.passed is False
    assert result.citation_precision_proxy == 0.0
    assert result.missing_required_citations == ("dna_normalization_sop.md",)


def test_explicit_empty_case_tuple_stays_empty() -> None:
    report = run_eval(EvalRunConfig(eval_run_id="eval_empty_cases"), cases=())

    assert report.metrics.case_count == 0
    assert report.cases == ()


def test_write_eval_report(tmp_path: Path) -> None:
    case = EvalCase(
        id="q_report",
        category="contract",
        question="What happens when transfer volume is below 1 uL?",
        required_sources=("dna_normalization_sop.md",),
        expected_answer_contains=("split",),
        disallowed_answer_contains=(),
        required_tool_calls=(),
    )
    report = run_eval(
        EvalRunConfig(top_k=6, retrieval_only=True, eval_run_id="eval_report_test"),
        cases=(case,),
    )

    path = write_eval_report(report, tmp_path)

    payload = json.loads(path.read_text())
    assert path.name == "eval_report_test.json"
    assert payload["eval_run_id"] == "eval_report_test"
    assert payload["prompt_model"]["prompt_id"] == "rag_answer"
    assert payload["prompt_model"]["model_version"] == "0.1.0"
    assert payload["metrics"]["case_count"] == 1
    assert payload["cases"][0]["case_id"] == "q_report"


def test_eval_report_includes_baseline_comparison(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "metrics": {
                    "case_count": 1,
                    "passed_count": 0,
                    "failed_count": 1,
                    "retrieval_recall_at_k": 0.0,
                }
            }
        )
    )
    case = EvalCase(
        id="q_baseline",
        category="contract",
        question="What happens when transfer volume is below 1 uL?",
        required_sources=("dna_normalization_sop.md",),
        expected_answer_contains=("split",),
        disallowed_answer_contains=(),
        required_tool_calls=(),
    )

    report = run_eval(
        EvalRunConfig(
            top_k=6,
            retrieval_only=True,
            eval_run_id="eval_baseline_test",
            baseline_report_path=baseline_path,
        ),
        cases=(case,),
    )

    comparison = report.to_json_dict()["baseline_comparison"]
    assert comparison["baseline_report_path"] == str(baseline_path)
    assert comparison["baseline_metrics"]["passed_count"] == 0
    assert comparison["metric_deltas"]["passed_count"] == 1.0


def test_cli_runs_from_non_repo_cwd(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "run_rag_evals.py"
    output_dir = tmp_path / "reports"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--retrieval-only",
            "--eval-run-id",
            "cwd_smoke",
            "--output-dir",
            str(output_dir),
        ],
        cwd=tmp_path,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "Wrote RAG eval report" in completed.stdout
    payload = json.loads((output_dir / "cwd_smoke.json").read_text())
    expected_case_count = len(load_golden_cases(repo_root / "evals/golden_questions.yaml"))
    assert payload["eval_run_id"] == "cwd_smoke"
    assert payload["metrics"]["case_count"] == expected_case_count


def test_rag_demo_cli_prints_answer_sources_and_suggested_tools_from_non_repo_cwd(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "rag_demo.py"

    completed = subprocess.run(
        [sys.executable, str(script)],
        input="Can invalid samples appear in JANUS transfer rows?\nquit\n",
        cwd=tmp_path,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "Answer:\n" in completed.stdout
    assert "Sources:\n" in completed.stdout
    assert "- batch_readiness_doctrine.md#chunk-" in completed.stdout
    assert "- janus_csv_worklist_spec.md#chunk-" in completed.stdout
    assert "Suggested tools:\n" in completed.stdout
    assert "- validate_batch" in completed.stdout
    assert "- generate_janus_csv" in completed.stdout


def test_rag_demo_cli_formats_unsupported_answer(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "rag_demo.py"

    completed = subprocess.run(
        [sys.executable, str(script)],
        input="Who won the ice hockey championship on Europa in 2035?\nexit\n",
        cwd=tmp_path,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "I do not have enough support in the LabFlow knowledge corpus" in completed.stdout
    assert "Sources:\n- none" in completed.stdout
    assert "Suggested tools:\n- none" in completed.stdout
