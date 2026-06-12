#!/usr/bin/env python3
"""Compare deterministic and optional live model planning on golden questions."""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from contextlib import contextmanager
import json
import os
import signal
from datetime import UTC, datetime
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for package in ("labflow-core", "labflow-rag", "labflow-agent"):
    src = REPO_ROOT / "packages" / package / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

from labflow_agent import AgentRequest, LabFlowAgentRuntime, model_from_env  # noqa: E402
from labflow_rag.evals import load_golden_cases  # noqa: E402

DEFAULT_OPENROUTER_TIMEOUT_SECONDS = "20"
DEFAULT_ENV_FILE = REPO_ROOT / ".env"

_VALIDATION_FIXTURES = {
    "q_batch_001": ("examples/workflows/invalid_rna_norm_requant.workflow.yaml", "RNA_BATCH_BAD_001"),
    "q_batch_003": ("examples/workflows/valid_dna_normalization.workflow.yaml", "DNA_NORM_BATCH_001"),
    "q_batch_004": ("examples/workflows/invalid_duplicate_well.workflow.yaml", "DNA_NORM_BAD_DUPLICATE"),
}
_QC_FIXTURE = "examples/qc/synthetic_ngs_qc_results.csv"
_QC_LINEAGE_FIXTURE = "examples/qc/synthetic_lab_lineage_manifest.csv"
_QC_SAMPLE_FIXTURES = {
    "q_qc_001": None,
    "q_qc_002": "RNA_DEMO_FAILED_VALID_UPSTREAM_001",
    "q_qc_003": None,
    "q_qc_004": None,
    "q_qc_005": "RNA_DEMO_FAILED_VALID_UPSTREAM_001",
}
_REQUEST_BACKED_TOOLS = frozenset(
    {
        "validate_batch",
        "ingest_ngs_qc_results",
        "validate_qc_provenance",
        "explain_qc_failure",
        "generate_lab_to_analysis_lineage",
    }
)


@dataclass(frozen=True)
class ToolRequirementEvaluation:
    missing_required_tool_calls: list[str]
    not_applicable_required_tool_calls: list[str]
    mode: str


class CaseDeadlineExceeded(RuntimeError):
    """Raised when the eval harness hard per-case deadline expires."""


def main() -> int:
    _load_dotenv_defaults(DEFAULT_ENV_FILE)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default="evals/golden_questions.yaml")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--output-dir", default="artifacts/model_eval_comparisons")
    parser.add_argument("--live-openrouter", action="store_true")
    parser.add_argument(
        "--confirm-live-openrouter",
        action="store_true",
        help="Confirm explicit current-turn approval for live OpenRouter provider calls.",
    )
    parser.add_argument(
        "--openrouter-timeout-seconds",
        type=float,
        default=float(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", DEFAULT_OPENROUTER_TIMEOUT_SECONDS)),
        help="Per-request OpenRouter timeout for live smoke runs.",
    )
    parser.add_argument(
        "--max-case-seconds",
        type=float,
        default=_optional_float_env("LABFLOW_MODEL_EVAL_MAX_CASE_SECONDS"),
        help="Optional hard wall-clock cap per case. Requires Unix SIGALRM support.",
    )
    parser.add_argument("--verbose", action="store_true", help="Print provider and case progress.")
    args = parser.parse_args()
    if args.live_openrouter and not args.confirm_live_openrouter:
        raise ValueError(
            "--live-openrouter requires --confirm-live-openrouter to document explicit "
            "current-turn approval for live provider calls."
        )

    cases = load_golden_cases(_repo_path(args.cases))[: args.limit]
    _verbose(args.verbose, f"Loaded {len(cases)} cases from {args.cases}.")
    runs = [
        _run_provider(
            "deterministic",
            {"LABFLOW_MODEL_PROVIDER": "deterministic"},
            cases,
            verbose=args.verbose,
            max_case_seconds=args.max_case_seconds,
        )
    ]

    if args.live_openrouter:
        if os.environ.get("OPENROUTER_API_KEY"):
            _verbose(args.verbose, "OPENROUTER_API_KEY is present; running live OpenRouter smoke.")
            live_env = {
                "LABFLOW_MODEL_PROVIDER": "openrouter",
                "OPENROUTER_API_KEY": os.environ["OPENROUTER_API_KEY"],
                "LABFLOW_OPENROUTER_MODEL": os.environ.get(
                    "LABFLOW_OPENROUTER_MODEL",
                    "nvidia/nemotron-3-ultra-550b-a55b:free",
                ),
                "OPENROUTER_BASE_URL": os.environ.get(
                    "OPENROUTER_BASE_URL",
                    "https://openrouter.ai/api/v1",
                ),
                "OPENROUTER_HTTP_REFERER": os.environ.get("OPENROUTER_HTTP_REFERER", ""),
                "OPENROUTER_APP_TITLE": os.environ.get(
                    "OPENROUTER_APP_TITLE",
                    "LabFlow AI Studio",
                ),
                "OPENROUTER_TIMEOUT_SECONDS": str(args.openrouter_timeout_seconds),
            }
            runs.append(
                _run_provider(
                    "openrouter",
                    live_env,
                    cases,
                    verbose=args.verbose,
                    max_case_seconds=args.max_case_seconds,
                )
            )
        else:
            _verbose(args.verbose, "OPENROUTER_API_KEY is absent; skipping live OpenRouter run.")
            runs.append(
                {
                    "provider": "openrouter",
                    "skipped": True,
                    "skip_reason": "OPENROUTER_API_KEY is absent.",
                    "cases": [],
                }
            )
    else:
        _verbose(args.verbose, "Live OpenRouter disabled; pass --live-openrouter to run it.")
        runs.append(
            {
                "provider": "openrouter",
                "skipped": True,
                "skip_reason": "Pass --live-openrouter and set OPENROUTER_API_KEY to run live.",
                "cases": [],
            }
        )

    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "case_count": len(cases),
        "gate_policy": "exploratory_report_only",
        "gate_note": "Nonzero fail_count is reported in JSON and does not make this smoke command fail.",
        "runs": runs,
    }
    output_dir = _repo_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"model_eval_comparison_{_timestamp_slug()}.json"
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {output_path}")
    return 0


def _run_provider(
    provider: str,
    env: dict[str, str],
    cases: tuple[Any, ...],
    *,
    verbose: bool = False,
    max_case_seconds: float | None = None,
) -> dict[str, Any]:
    _validate_case_deadline(max_case_seconds)
    _verbose(verbose, f"[{provider}] Building model/runtime.")
    model = model_from_env(env)
    runtime = LabFlowAgentRuntime(model=model)
    results = []
    missing_required_tool_calls = 0
    pass_count = 0
    fail_count = 0
    unsupported_count = 0
    error_count = 0
    plan_diagnostic_counts: dict[str, int] = {}

    _verbose(
        verbose,
        f"[{provider}] Running {len(cases)} cases with model {model.metadata.model_id} "
        f"via {model.metadata.provider}.",
    )
    for index, case in enumerate(cases, start=1):
        _verbose(verbose, f"[{provider}] Case {index}/{len(cases)} {case.id}: {case.question}")
        started_at = datetime.now(UTC)
        request = _request_for_case(case)
        try:
            with _case_deadline(max_case_seconds):
                response = runtime.run(request)
        except Exception as exc:  # noqa: BLE001 - eval smoke must record provider errors and continue.
            fail_count += 1
            error_count += 1
            elapsed_ms = _elapsed_ms(started_at)
            tool_evaluation = _evaluate_required_tools(case, (), request)
            _verbose(
                verbose,
                f"[{provider}] Case {case.id} error after {elapsed_ms:.0f} ms: "
                f"{type(exc).__name__}: {exc}",
            )
            results.append(
                {
                    "case_id": case.id,
                    "question": case.question,
                    "tool_requirement_mode": tool_evaluation.mode,
                    "task": None,
                    "plan_diagnostic": None,
                    "unsupported": None,
                    "tool_calls": [],
                    "missing_required_tool_calls": tool_evaluation.missing_required_tool_calls,
                    "not_applicable_required_tool_calls": (
                        tool_evaluation.not_applicable_required_tool_calls
                    ),
                    "error": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "elapsed_ms": elapsed_ms,
                    },
                    "trace": None,
                }
            )
            continue
        elapsed_ms = _elapsed_ms(started_at)
        tool_names = [call.tool_name for call in response.tool_calls]
        plan_diagnostic = (
            response.plan.diagnostic.model_dump(mode="json") if response.plan.diagnostic else None
        )
        if plan_diagnostic is not None:
            diagnostic_code = str(plan_diagnostic["code"])
            plan_diagnostic_counts[diagnostic_code] = (
                plan_diagnostic_counts.get(diagnostic_code, 0) + 1
            )
        if response.unsupported:
            unsupported_count += 1
        tool_evaluation = _evaluate_required_tools(case, tool_names, request)
        if tool_evaluation.missing_required_tool_calls:
            missing_required_tool_calls += 1
        if response.unsupported or tool_evaluation.missing_required_tool_calls:
            fail_count += 1
        else:
            pass_count += 1
        results.append(
            {
                "case_id": case.id,
                "question": case.question,
                "request_has_workflow_yaml": request.workflow_yaml is not None,
                "batch_id": request.batch_id,
                "tool_requirement_mode": tool_evaluation.mode,
                "task": response.task.value,
                "plan_rationale": response.plan.rationale,
                "unsupported_reason": response.plan.unsupported_reason,
                "plan_diagnostic": plan_diagnostic,
                "unsupported": response.unsupported,
                "answer": response.answer,
                "tool_calls": tool_names,
                "missing_required_tool_calls": tool_evaluation.missing_required_tool_calls,
                "not_applicable_required_tool_calls": (
                    tool_evaluation.not_applicable_required_tool_calls
                ),
                "error": None,
                "elapsed_ms": elapsed_ms,
                "trace": response.trace.model_dump(mode="json") if response.trace else None,
            }
        )
        _verbose(
            verbose,
            f"[{provider}] Case {case.id} complete: task={response.task.value}, "
            f"unsupported={response.unsupported}, "
            f"diagnostic={plan_diagnostic['code'] if plan_diagnostic else 'none'}, "
            f"missing_tools={len(tool_evaluation.missing_required_tool_calls)}, "
            f"not_applicable_tools={len(tool_evaluation.not_applicable_required_tool_calls)}, "
            f"elapsed_ms={elapsed_ms:.0f}.",
        )

    _verbose(
        verbose,
        f"[{provider}] Complete: pass={pass_count}, fail={fail_count}, "
        f"unsupported={unsupported_count}, errors={error_count}, "
        f"missing_tool_cases={missing_required_tool_calls}.",
    )
    return {
        "provider": provider,
        "model_id": model.metadata.model_id,
        "model_version": model.metadata.version,
        "model_provider": model.metadata.provider,
        "skipped": False,
        "case_count": len(cases),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "unsupported_count": unsupported_count,
        "error_count": error_count,
        "missing_required_tool_call_count": missing_required_tool_calls,
        "plan_diagnostic_counts": dict(sorted(plan_diagnostic_counts.items())),
        "cases": results,
    }


def _verbose(enabled: bool, message: str) -> None:
    if enabled:
        print(message, flush=True)


def _elapsed_ms(started_at: datetime) -> float:
    return (datetime.now(UTC) - started_at).total_seconds() * 1000


def _request_for_case(case: Any) -> AgentRequest:
    if case.id in _QC_SAMPLE_FIXTURES:
        qc_path = _repo_path(_QC_FIXTURE)
        lineage_path = _repo_path(_QC_LINEAGE_FIXTURE)
        if qc_path.exists() and lineage_path.exists():
            return AgentRequest(
                question=case.question,
                qc_csv=str(qc_path),
                lineage_csv=str(lineage_path),
                sample_id=_QC_SAMPLE_FIXTURES[case.id],
            )
    fixture = _VALIDATION_FIXTURES.get(case.id)
    if fixture is None:
        return AgentRequest(question=case.question)

    workflow_path, batch_id = fixture
    resolved = _repo_path(workflow_path)
    if not resolved.exists():
        return AgentRequest(question=case.question)
    return AgentRequest(
        question=case.question,
        workflow_yaml=resolved.read_text(),
        batch_id=batch_id,
    )


def _evaluate_required_tools(
    case: Any,
    tool_names: list[str] | tuple[str, ...],
    request: AgentRequest,
) -> ToolRequirementEvaluation:
    missing: list[str] = []
    not_applicable: list[str] = []
    called = set(tool_names)
    for tool_name in case.required_tool_calls:
        if _tool_requirement_is_applicable(tool_name, request):
            if tool_name not in called:
                missing.append(tool_name)
        else:
            not_applicable.append(tool_name)

    if not case.required_tool_calls:
        mode = "none"
    elif not_applicable and not missing:
        mode = "not_applicable_no_fixture"
    elif request.workflow_yaml is not None:
        mode = "fixture_provided"
    else:
        mode = "strict"
    return ToolRequirementEvaluation(
        missing_required_tool_calls=missing,
        not_applicable_required_tool_calls=not_applicable,
        mode=mode,
    )


def _tool_requirement_is_applicable(tool_name: str, request: AgentRequest) -> bool:
    if tool_name == "validate_batch":
        return request.workflow_yaml is not None
    if tool_name == "ingest_ngs_qc_results":
        return request.qc_csv is not None
    if tool_name == "validate_qc_provenance":
        return request.qc_csv is not None and request.lineage_csv is not None
    if tool_name == "explain_qc_failure":
        return request.qc_csv is not None and request.sample_id is not None
    if tool_name == "generate_lab_to_analysis_lineage":
        return request.qc_csv is not None and request.lineage_csv is not None
    return False


def _optional_float_env(name: str) -> float | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return None
    return float(value)


def _load_dotenv_defaults(path: Path) -> None:
    """Load simple KEY=VALUE entries from .env without overriding the shell environment."""

    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = _dotenv_value(value.strip())


def _dotenv_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _validate_case_deadline(max_case_seconds: float | None) -> None:
    if max_case_seconds is None:
        return
    if max_case_seconds <= 0:
        raise ValueError("--max-case-seconds must be greater than 0.")
    if not hasattr(signal, "SIGALRM") or not hasattr(signal, "setitimer"):
        raise ValueError("--max-case-seconds requires Unix SIGALRM support.")


@contextmanager
def _case_deadline(max_case_seconds: float | None) -> Iterator[None]:
    if max_case_seconds is None:
        yield
        return

    def _raise_timeout(signum: int, frame: object) -> None:
        raise CaseDeadlineExceeded(f"Case exceeded --max-case-seconds={max_case_seconds}.")

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, 0)
    started_at = datetime.now(UTC)
    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, max_case_seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if previous_timer[0] > 0:
            elapsed_seconds = (datetime.now(UTC) - started_at).total_seconds()
            remaining_seconds = max(0.001, previous_timer[0] - elapsed_seconds)
            signal.setitimer(signal.ITIMER_REAL, remaining_seconds, previous_timer[1])
        signal.signal(signal.SIGALRM, previous_handler)


def _repo_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _timestamp_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
