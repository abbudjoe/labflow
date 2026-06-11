#!/usr/bin/env python3
"""Run laddered LabFlow model eval comparison tiers."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for package in ("labflow-core", "labflow-rag", "labflow-agent"):
    src = REPO_ROOT / "packages" / package / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

import run_model_eval_comparison as comparison  # noqa: E402
from labflow_rag.evals import EvalCase, load_golden_cases  # noqa: E402

DEFAULT_TIERS = (
    "smoke_3",
    "confidence_10",
    "category_batch_readiness",
    "category_guardrails",
    "full_golden",
)


@dataclass(frozen=True)
class LadderTier:
    name: str
    cases: tuple[EvalCase, ...]
    description: str


def main() -> int:
    comparison._load_dotenv_defaults(comparison.DEFAULT_ENV_FILE)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default="evals/golden_questions.yaml")
    parser.add_argument("--output-dir", default="artifacts/model_eval_ladders")
    parser.add_argument("--comparison-output-dir", default="artifacts/model_eval_comparisons")
    parser.add_argument("--tier", action="append", choices=DEFAULT_TIERS)
    parser.add_argument("--skip-full", action="store_true")
    parser.add_argument("--live-openrouter", action="store_true")
    parser.add_argument(
        "--openrouter-timeout-seconds",
        type=float,
        default=float(
            os.environ.get(
                "OPENROUTER_TIMEOUT_SECONDS",
                comparison.DEFAULT_OPENROUTER_TIMEOUT_SECONDS,
            )
        ),
    )
    parser.add_argument(
        "--max-case-seconds",
        type=float,
        default=comparison._optional_float_env("LABFLOW_MODEL_EVAL_MAX_CASE_SECONDS"),
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    all_cases = load_golden_cases(_repo_path(args.cases))
    selected_tiers = _select_tiers(
        all_cases,
        requested_tiers=tuple(args.tier or ()),
        skip_full=args.skip_full,
    )
    if not selected_tiers:
        raise ValueError("No ladder tiers selected.")

    _verbose(args.verbose, f"Running {len(selected_tiers)} ladder tiers.")
    comparison_output_dir = _repo_path(args.comparison_output_dir)
    comparison_output_dir.mkdir(parents=True, exist_ok=True)

    tier_reports: list[dict[str, Any]] = []
    for index, tier in enumerate(selected_tiers, start=1):
        _verbose(
            args.verbose,
            f"[ladder] Tier {index}/{len(selected_tiers)} {tier.name}: "
            f"{len(tier.cases)} cases.",
        )
        tier_report = _run_tier(
            tier,
            live_openrouter=args.live_openrouter,
            openrouter_timeout_seconds=args.openrouter_timeout_seconds,
            max_case_seconds=args.max_case_seconds,
            verbose=args.verbose,
            comparison_output_dir=comparison_output_dir,
        )
        tier_reports.append(tier_report)

    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "cases_path": str(_repo_path(args.cases)),
        "live_openrouter_requested": args.live_openrouter,
        "aggregate_note": (
            "Aggregate counts are tier executions and may count the same golden case more than once "
            "when tiers overlap."
        ),
        "selected_tiers": [tier.name for tier in selected_tiers],
        "tier_count": len(tier_reports),
        "aggregate_by_provider": _aggregate_by_provider(tier_reports),
        "tiers": tier_reports,
    }
    output_dir = _repo_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _timestamp_slug()
    json_path = output_dir / f"model_eval_ladder_{timestamp}.json"
    markdown_path = output_dir / f"model_eval_ladder_{timestamp}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    markdown_path.write_text(_markdown_report(report))
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    return 0


def _run_tier(
    tier: LadderTier,
    *,
    live_openrouter: bool,
    openrouter_timeout_seconds: float,
    max_case_seconds: float | None,
    verbose: bool,
    comparison_output_dir: Path,
) -> dict[str, Any]:
    runs = [
        comparison._run_provider(
            "deterministic",
            {"LABFLOW_MODEL_PROVIDER": "deterministic"},
            tier.cases,
            verbose=verbose,
            max_case_seconds=max_case_seconds,
        )
    ]

    if live_openrouter:
        if os.environ.get("OPENROUTER_API_KEY"):
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
                "OPENROUTER_TIMEOUT_SECONDS": str(openrouter_timeout_seconds),
            }
            runs.append(
                comparison._run_provider(
                    "openrouter",
                    live_env,
                    tier.cases,
                    verbose=verbose,
                    max_case_seconds=max_case_seconds,
                )
            )
        else:
            runs.append(
                {
                    "provider": "openrouter",
                    "skipped": True,
                    "skip_reason": "OPENROUTER_API_KEY is absent.",
                    "cases": [],
                }
            )
    else:
        runs.append(
            {
                "provider": "openrouter",
                "skipped": True,
                "skip_reason": "Pass --live-openrouter and set OPENROUTER_API_KEY to run live.",
                "cases": [],
            }
        )

    comparison_report = {
        "created_at": datetime.now(UTC).isoformat(),
        "case_count": len(tier.cases),
        "gate_policy": "exploratory_report_only",
        "gate_note": "Nonzero fail_count is reported in JSON and does not make this smoke command fail.",
        "tier": {
            "name": tier.name,
            "description": tier.description,
            "case_ids": [case.id for case in tier.cases],
        },
        "runs": runs,
    }
    comparison_path = comparison_output_dir / (
        f"model_eval_comparison_{tier.name}_{_timestamp_slug()}.json"
    )
    comparison_path.write_text(json.dumps(comparison_report, indent=2, sort_keys=True) + "\n")
    return {
        "name": tier.name,
        "description": tier.description,
        "case_count": len(tier.cases),
        "case_ids": [case.id for case in tier.cases],
        "comparison_report_path": str(comparison_path),
        "runs": [_summarize_run(run) for run in runs],
    }


def _select_tiers(
    cases: tuple[EvalCase, ...],
    *,
    requested_tiers: tuple[str, ...],
    skip_full: bool,
) -> tuple[LadderTier, ...]:
    tier_names = requested_tiers or DEFAULT_TIERS
    if skip_full:
        tier_names = tuple(name for name in tier_names if name != "full_golden")
    return tuple(_tier_for_name(name, cases) for name in tier_names)


def _tier_for_name(name: str, cases: tuple[EvalCase, ...]) -> LadderTier:
    if name == "smoke_3":
        return LadderTier(name=name, cases=cases[:3], description="First three golden cases.")
    if name == "confidence_10":
        return LadderTier(name=name, cases=cases[:10], description="First ten golden cases.")
    if name == "full_golden":
        return LadderTier(name=name, cases=cases, description="All golden cases.")
    if name.startswith("category_"):
        category = name.removeprefix("category_")
        category_cases = tuple(case for case in cases if case.category == category)
        if not category_cases:
            raise ValueError(f"No golden cases found for category tier {name!r}.")
        return LadderTier(
            name=name,
            cases=category_cases,
            description=f"Golden cases in category {category}.",
        )
    raise ValueError(f"Unknown ladder tier: {name}")


def _summarize_run(run: dict[str, Any]) -> dict[str, Any]:
    if run.get("skipped") is True:
        return {
            "provider": run["provider"],
            "skipped": True,
            "skip_reason": run.get("skip_reason"),
        }
    return {
        "provider": run["provider"],
        "model_id": run.get("model_id"),
        "model_provider": run.get("model_provider"),
        "case_count": run.get("case_count", 0),
        "pass_count": run.get("pass_count", 0),
        "fail_count": run.get("fail_count", 0),
        "unsupported_count": run.get("unsupported_count", 0),
        "error_count": run.get("error_count", 0),
        "missing_required_tool_call_count": run.get("missing_required_tool_call_count", 0),
        "plan_diagnostic_counts": run.get("plan_diagnostic_counts", {}),
        "skipped": False,
    }


def _aggregate_by_provider(tier_reports: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    aggregate: dict[str, dict[str, Any]] = {}
    for tier_report in tier_reports:
        for run in tier_report["runs"]:
            provider = str(run["provider"])
            provider_totals = aggregate.setdefault(
                provider,
                {
                    "tier_count": 0,
                    "case_count": 0,
                    "pass_count": 0,
                    "fail_count": 0,
                    "unsupported_count": 0,
                    "error_count": 0,
                    "missing_required_tool_call_count": 0,
                    "plan_diagnostic_counts": {},
                    "skipped_tier_count": 0,
                },
            )
            provider_totals["tier_count"] += 1
            if run.get("skipped") is True:
                provider_totals["skipped_tier_count"] += 1
                continue
            for key in (
                "case_count",
                "pass_count",
                "fail_count",
                "unsupported_count",
                "error_count",
                "missing_required_tool_call_count",
            ):
                provider_totals[key] += int(run.get(key, 0))
            for code, count in run.get("plan_diagnostic_counts", {}).items():
                diagnostic_counts = provider_totals["plan_diagnostic_counts"]
                diagnostic_counts[code] = diagnostic_counts.get(code, 0) + int(count)
    for provider_totals in aggregate.values():
        provider_totals["plan_diagnostic_counts"] = dict(
            sorted(provider_totals["plan_diagnostic_counts"].items())
        )
    return aggregate


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# LabFlow Model Eval Ladder",
        "",
        f"Created: `{report['created_at']}`",
        f"Live OpenRouter requested: `{report['live_openrouter_requested']}`",
        "",
        str(report["aggregate_note"]),
        "",
        "## Aggregate",
        "",
        "| Provider | Tiers | Skipped | Cases | Pass | Fail | Unsupported | Errors | Missing Tool Cases | Plan Diagnostics |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for provider, totals in sorted(report["aggregate_by_provider"].items()):
        lines.append(
            "| "
            f"{provider} | {totals['tier_count']} | {totals['skipped_tier_count']} | "
            f"{totals['case_count']} | {totals['pass_count']} | {totals['fail_count']} | "
            f"{totals['unsupported_count']} | {totals['error_count']} | "
            f"{totals['missing_required_tool_call_count']} | "
            f"{_format_diagnostic_counts(totals.get('plan_diagnostic_counts', {}))} |"
        )

    lines.extend(["", "## Tiers", ""])
    for tier in report["tiers"]:
        lines.extend(
            [
                f"### {tier['name']}",
                "",
                tier["description"],
                "",
                f"Cases: `{tier['case_count']}`",
                f"Comparison report: `{tier['comparison_report_path']}`",
                "",
                "| Provider | Cases | Pass | Fail | Unsupported | Errors | Missing Tool Cases | Plan Diagnostics | Status |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
            ]
        )
        for run in tier["runs"]:
            if run.get("skipped") is True:
                lines.append(
                    f"| {run['provider']} | 0 | 0 | 0 | 0 | 0 | 0 | none | "
                    f"skipped: {run.get('skip_reason')} |"
                )
            else:
                lines.append(
                    "| "
                    f"{run['provider']} | {run['case_count']} | {run['pass_count']} | "
                    f"{run['fail_count']} | {run['unsupported_count']} | {run['error_count']} | "
                    f"{run['missing_required_tool_call_count']} | "
                    f"{_format_diagnostic_counts(run.get('plan_diagnostic_counts', {}))} | ran |"
                )
        lines.append("")
    return "\n".join(lines)


def _format_diagnostic_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{code}: {count}" for code, count in sorted(counts.items()))


def _repo_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _timestamp_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def _verbose(enabled: bool, message: str) -> None:
    if enabled:
        print(message, flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
