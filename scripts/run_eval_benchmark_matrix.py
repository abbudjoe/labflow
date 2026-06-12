#!/usr/bin/env python3
"""Run a frozen live inference eval matrix across configured model profiles."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "run_inference_eval_ladder.py"
DEFAULT_SUITES = (
    "control_parity",
    "semantic_generalization",
    "grounded_answer_quality",
    "repair_planning",
)
DEFAULT_OPENROUTER_MODELS = (
    "nex-agi/nex-n2-pro:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "qwen/qwen3-coder:free",
    "openai/gpt-oss-120b:free",
    "openai/gpt-oss-20b:free",
)
DEFAULT_OPENAI_MODELS = (
    ("gpt-5.5", "medium"),
    ("gpt-5.4-mini", "medium"),
)


@dataclass(frozen=True)
class MatrixProfile:
    label: str
    provider_profile: str
    model_id: str
    base_url: str
    api_key_env: str
    reasoning_effort: str | None = None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", action="append", choices=DEFAULT_SUITES)
    parser.add_argument("--output-dir", default="artifacts/eval_benchmark_matrices")
    parser.add_argument("--run-output-dir", default=None)
    parser.add_argument("--openrouter-timeout-seconds", type=float, default=20.0)
    parser.add_argument("--max-case-seconds", type=float, default=45.0)
    parser.add_argument("--case-category", action="append")
    parser.add_argument("--limit-cases-per-suite", type=int, default=None)
    parser.add_argument(
        "--skip-deterministic-baseline",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Skip repeated deterministic baseline execution for fast semantic/grounded "
            "slices. Leave off for full-suite runs that include control_parity."
        ),
    )
    parser.add_argument(
        "--profile",
        action="append",
        help=(
            "Run only matching labels/model IDs. May be repeated. "
            "Defaults to the full requested matrix."
        ),
    )
    parser.add_argument(
        "--verbose-runs",
        action="store_true",
        help="Stream each underlying ladder runner's verbose output.",
    )
    parser.add_argument(
        "--continue-on-error",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Continue to later profiles if one profile command exits nonzero.",
    )
    args = parser.parse_args()

    _load_dotenv_defaults(REPO_ROOT / ".env")
    output_dir = _repo_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_root = _repo_path(args.run_output_dir) if args.run_output_dir else output_dir / "runs"
    run_root.mkdir(parents=True, exist_ok=True)

    suites = tuple(args.suite or DEFAULT_SUITES)
    profiles = _filtered_profiles(_default_profiles(), args.profile)
    if not profiles:
        raise SystemExit("No benchmark profiles matched --profile filters.")

    started = _timestamp_slug()
    results: list[dict[str, Any]] = []
    print(
        f"Running {len(profiles)} model profiles across suites: {', '.join(suites)}",
        flush=True,
    )
    for index, profile in enumerate(profiles, start=1):
        print(f"\n[{index}/{len(profiles)}] {profile.label}", flush=True)
        results.append(
            _run_profile(
                profile,
                suites=suites,
                run_root=run_root,
                timeout_seconds=args.openrouter_timeout_seconds,
                max_case_seconds=args.max_case_seconds,
                verbose_runs=args.verbose_runs,
                case_categories=tuple(args.case_category or ()),
                limit_cases=args.limit_cases_per_suite,
                skip_deterministic_baseline=args.skip_deterministic_baseline,
            )
        )
        if results[-1]["returncode"] != 0 and not args.continue_on_error:
            break

    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "runner_version": "0.1.0",
        "suites": list(suites),
        "profile_count": len(profiles),
        "results": results,
    }
    json_path = output_dir / f"eval_benchmark_matrix_{started}.json"
    md_path = output_dir / f"eval_benchmark_matrix_{started}.md"
    report["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    md_path.write_text(_markdown_report(report))

    print("\n" + _terminal_grid(results), flush=True)
    print(f"Wrote {json_path}", flush=True)
    print(f"Wrote {md_path}", flush=True)
    return 0 if all(result["returncode"] == 0 for result in results) else 1


def _default_profiles() -> tuple[MatrixProfile, ...]:
    openrouter = tuple(
        MatrixProfile(
            label=model,
            provider_profile="openrouter",
            model_id=model,
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key_env="OPENROUTER_API_KEY",
        )
        for model in DEFAULT_OPENROUTER_MODELS
    )
    openai = tuple(
        MatrixProfile(
            label=f"{model} ({effort} thinking)",
            provider_profile="openai-chat-compatible",
            model_id=model,
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            api_key_env="OPENAI_API_KEY",
            reasoning_effort=effort,
        )
        for model, effort in DEFAULT_OPENAI_MODELS
    )
    return (*openrouter, *openai)


def _filtered_profiles(
    profiles: tuple[MatrixProfile, ...], filters: list[str] | None
) -> tuple[MatrixProfile, ...]:
    if not filters:
        return profiles
    needles = tuple(item.casefold() for item in filters)
    return tuple(
        profile
        for profile in profiles
        if any(
            needle in profile.label.casefold() or needle in profile.model_id.casefold()
            for needle in needles
        )
    )


def _run_profile(
    profile: MatrixProfile,
    *,
    suites: tuple[str, ...],
    run_root: Path,
    timeout_seconds: float,
    max_case_seconds: float,
    verbose_runs: bool,
    case_categories: tuple[str, ...],
    limit_cases: int | None,
    skip_deterministic_baseline: bool,
) -> dict[str, Any]:
    profile_dir = run_root / _slug(profile.label)
    profile_dir.mkdir(parents=True, exist_ok=True)
    api_key = os.environ.get(profile.api_key_env, "")
    if not api_key.strip():
        return _skipped_profile(profile, profile_dir, f"{profile.api_key_env} is absent.")

    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "PYTHONPATH": _pythonpath(env),
            "LABFLOW_MODEL_PROVIDER": "openrouter",
            "LABFLOW_ANSWER_COMPOSER": "openrouter",
            "LABFLOW_OPENROUTER_MODEL": profile.model_id,
            "OPENROUTER_API_KEY": api_key,
            "OPENROUTER_BASE_URL": profile.base_url,
            "OPENROUTER_TIMEOUT_SECONDS": str(timeout_seconds),
            "OPENROUTER_CASE_DEADLINE_SECONDS": str(max_case_seconds),
        }
    )
    if profile.reasoning_effort:
        env["OPENROUTER_REASONING_EFFORT"] = profile.reasoning_effort
    else:
        env.pop("OPENROUTER_REASONING_EFFORT", None)

    command = [
        sys.executable,
        str(RUNNER),
        "--live-openrouter",
        "--confirm-live-openrouter",
        "--openrouter-timeout-seconds",
        str(timeout_seconds),
        "--max-case-seconds",
        str(max_case_seconds),
        "--output-dir",
        str(profile_dir),
    ]
    if skip_deterministic_baseline:
        command.append("--skip-deterministic-baseline")
    for suite in suites:
        command.extend(["--suite", suite])
    for category in case_categories:
        command.extend(["--case-category", category])
    if limit_cases is not None:
        command.extend(["--limit-cases-per-suite", str(limit_cases)])
    if verbose_runs:
        command.append("--verbose")

    started = datetime.now(UTC)
    proc = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    captured: list[str] = []
    for line in proc.stdout:
        captured.append(line)
        if verbose_runs:
            print(f"[{profile.label}] {line}", end="", flush=True)
    returncode = proc.wait()
    elapsed_seconds = (datetime.now(UTC) - started).total_seconds()
    latest_json = _latest_json(profile_dir)
    summary = _summary_from_artifact(latest_json) if latest_json else {}
    return {
        "label": profile.label,
        "provider_profile": profile.provider_profile,
        "model_id": profile.model_id,
        "reasoning_effort": profile.reasoning_effort,
        "base_url": _redacted_base_url(profile.base_url),
        "returncode": returncode,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "artifact_json": str(latest_json) if latest_json else None,
        "artifact_markdown": str(latest_json.with_suffix(".md")) if latest_json else None,
        "stdout_tail": "".join(captured[-40:]),
        "summary": summary,
    }


def _skipped_profile(profile: MatrixProfile, profile_dir: Path, reason: str) -> dict[str, Any]:
    print(f"  skipped: {reason}", flush=True)
    return {
        "label": profile.label,
        "provider_profile": profile.provider_profile,
        "model_id": profile.model_id,
        "reasoning_effort": profile.reasoning_effort,
        "base_url": _redacted_base_url(profile.base_url),
        "returncode": 0,
        "elapsed_seconds": 0.0,
        "artifact_json": None,
        "artifact_markdown": None,
        "stdout_tail": "",
        "summary": {"skipped": True, "skip_reason": reason},
    }


def _summary_from_artifact(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text())
    gate = report.get("production_gate", {})
    downstream = gate.get("downstream_qc_gate", {})
    suites = downstream.get("suites", {})
    semantic = suites.get("semantic_generalization", {})
    grounded = suites.get("grounded_answer_quality", {})
    control = suites.get("control_parity", {})
    repair = suites.get("repair_planning", {})
    return {
        "primary_pass": gate.get("primary_provider_pass_count"),
        "primary_fail": gate.get("primary_provider_fail_count"),
        "primary_safety_gate": gate.get("primary_provider_passed_safety_gate"),
        "control_parity_passed": gate.get("primary_provider_control_parity_passed"),
        "provider_failures": gate.get("primary_provider_blocking_counts", {}).get(
            "provider_failure_count"
        ),
        "schema_failures": gate.get("primary_provider_blocking_counts", {}).get(
            "schema_failure_count"
        ),
        "groundedness_violations": gate.get("primary_provider_blocking_counts", {}).get(
            "groundedness_violation_count"
        ),
        "safety_violations": gate.get("primary_provider_blocking_counts", {}).get(
            "safety_violation_count"
        ),
        "downstream_qc_passed": downstream.get("passed"),
        "downstream_blocking_reasons": downstream.get("blocking_reasons", []),
        "qc_semantic_pass": semantic.get("pass_count"),
        "qc_semantic_fail": semantic.get("fail_count"),
        "qc_semantic_mean": semantic.get("mean_score"),
        "qc_semantic_tool": semantic.get("tool_call_correctness"),
        "qc_grounded_pass": grounded.get("pass_count"),
        "qc_grounded_fail": grounded.get("fail_count"),
        "qc_grounded_mean": grounded.get("mean_score"),
        "qc_grounded_tool": grounded.get("tool_call_correctness"),
        "qc_grounded_source": grounded.get("required_source_recall"),
        "qc_groundedness": grounded.get("groundedness_violation_count"),
        "qc_control_pass": control.get("pass_count"),
        "qc_control_fail": control.get("fail_count"),
        "qc_repair_pass": repair.get("pass_count"),
        "qc_repair_fail": repair.get("fail_count"),
    }


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# LabFlow Eval Benchmark Matrix",
        "",
        f"Created: `{report['created_at']}`",
        f"Suites: `{', '.join(report['suites'])}`",
        "",
        _terminal_grid(report["results"]),
        "",
        "## Artifacts",
        "",
    ]
    for result in report["results"]:
        artifact = result.get("artifact_json") or "n/a"
        lines.append(f"- `{result['label']}`: `{artifact}`")
    return "\n".join(lines) + "\n"


def _terminal_grid(results: list[dict[str, Any]]) -> str:
    headers = (
        "model",
        "profile",
        "primary",
        "ctrl",
        "safe",
        "prov",
        "schema",
        "grnd",
        "qc",
        "sem",
        "sem_tool",
        "gnd",
        "gnd_src",
        "gnd_tool",
        "sec",
    )
    rows = []
    for result in results:
        summary = result.get("summary", {})
        if summary.get("skipped"):
            rows.append(
                (
                    result["label"],
                    result["provider_profile"],
                    "skipped",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    f"{result['elapsed_seconds']:.0f}",
                )
            )
            continue
        rows.append(
            (
                result["label"],
                result["provider_profile"],
                _ratio(summary.get("primary_pass"), summary.get("primary_fail")),
                _bool(summary.get("control_parity_passed")),
                str(summary.get("safety_violations", "")),
                str(summary.get("provider_failures", "")),
                str(summary.get("schema_failures", "")),
                str(summary.get("groundedness_violations", "")),
                _bool(summary.get("downstream_qc_passed")),
                _ratio(summary.get("qc_semantic_pass"), summary.get("qc_semantic_fail")),
                _pct(summary.get("qc_semantic_tool")),
                _ratio(summary.get("qc_grounded_pass"), summary.get("qc_grounded_fail")),
                _pct(summary.get("qc_grounded_source")),
                _pct(summary.get("qc_grounded_tool")),
                f"{result['elapsed_seconds']:.0f}",
            )
        )
    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row, strict=True)]
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    rendered = [
        "| " + " | ".join(header.ljust(width) for header, width in zip(headers, widths, strict=True)) + " |",
        sep,
    ]
    rendered.extend(
        "| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)) + " |"
        for row in rows
    )
    return "\n".join(rendered)


def _ratio(pass_count: Any, fail_count: Any) -> str:
    if pass_count is None or fail_count is None:
        return "-"
    return f"{pass_count}/{int(pass_count) + int(fail_count)}"


def _bool(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "-"


def _pct(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value):.3f}"


def _latest_json(directory: Path) -> Path | None:
    paths = list(directory.glob("inference_eval_ladder_*.json"))
    return max(paths, key=lambda path: path.stat().st_mtime) if paths else None


def _pythonpath(env: dict[str, str]) -> str:
    local = "packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src"
    current = env.get("PYTHONPATH", "")
    return f"{local}:{current}" if current else local


def _load_dotenv_defaults(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _repo_path(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


def _timestamp_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")[:120]


def _redacted_base_url(base_url: str) -> str:
    return base_url.split("?", 1)[0]


if __name__ == "__main__":
    raise SystemExit(main())
