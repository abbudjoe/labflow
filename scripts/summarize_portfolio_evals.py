#!/usr/bin/env python3
"""Generate a compact portfolio eval summary from curated artifacts."""

from __future__ import annotations

import json
from pathlib import Path
import statistics
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "docs/portfolio_artifact_manifest.json"
OUTPUT_PATH = REPO_ROOT / "docs/eval_summary.md"


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text())
    rows: list[dict[str, Any]] = []
    notes: list[str] = []
    for item in manifest["artifacts"]:
        path = REPO_ROOT / item["path"]
        if not path.exists():
            rows.append(_missing_row(item))
            continue
        payload = json.loads(path.read_text())
        if item["kind"] == "inference_eval_ladder":
            rows.extend(_inference_rows(item, payload))
        elif item["kind"] == "rag_eval":
            rows.append(_rag_row(item, payload))
        notes.append(f"- `{item['id']}`: {item['why_canonical']}")

    markdown = _render_markdown(rows, notes, manifest)
    OUTPUT_PATH.write_text(markdown)
    print(f"Wrote {OUTPUT_PATH}")
    return 0


def _missing_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_id": item["id"],
        "suite": item.get("suite", "unknown"),
        "provider": "n/a",
        "pass_rate": "missing",
        "safety": "missing",
        "provider_failures": "missing",
        "schema_failures": "missing",
        "unsupported_claims": "missing",
        "fallback": "missing",
        "mean_score": "missing",
        "margin": "missing",
        "latency": "missing",
        "source": item["path"],
    }


def _inference_rows(item: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
    gate = payload.get("production_gate", {})
    rows = []
    for suite in payload.get("suites", []):
        if suite.get("suite") != item.get("suite"):
            continue
        comparison = suite.get("baseline_comparison", {})
        metrics = suite.get("metrics", {})
        provider = suite.get("primary_provider_under_test") or gate.get("primary_provider", "unknown")
        pass_count = int(suite.get("pass_count", 0))
        case_count = int(suite.get("case_count", 0))
        blocking = gate.get("primary_provider_blocking_counts", {})
        rows.append(
            {
                "artifact_id": item["id"],
                "suite": suite["suite"],
                "provider": provider,
                "pass_rate": _ratio(pass_count, case_count),
                "safety": blocking.get("safety_violation_count", suite.get("safety_violation_count", 0)),
                "provider_failures": blocking.get(
                    "provider_failure_count",
                    suite.get("provider_failure_count", 0),
                ),
                "schema_failures": blocking.get("schema_failure_count", 0),
                "unsupported_claims": blocking.get(
                    "unsupported_claim_count",
                    suite.get("unsupported_claim_count", 0),
                ),
                "fallback": _fallback_count(suite),
                "mean_score": _fmt(comparison.get("inference_score") or metrics.get("answer_rule_match")),
                "margin": _fmt(comparison.get("acceptance_absolute_margin")),
                "latency": _latency(metrics),
                "source": item["path"],
            }
        )
    return rows


def _rag_row(item: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics", {})
    pass_count = int(metrics.get("passed_count", 0))
    case_count = int(metrics.get("case_count", 0))
    latencies = [
        float(case.get("latency_ms", 0))
        for case in payload.get("cases", [])
        if isinstance(case.get("latency_ms"), int | float)
    ]
    return {
        "artifact_id": item["id"],
        "suite": item.get("suite", "retrieval_only"),
        "provider": "local_rag",
        "pass_rate": _ratio(pass_count, case_count),
        "safety": len(metrics.get("disallowed_answer_violations", []))
        if isinstance(metrics.get("disallowed_answer_violations"), list)
        else 0,
        "provider_failures": 0,
        "schema_failures": 0,
        "unsupported_claims": 0,
        "fallback": "n/a",
        "mean_score": _fmt(metrics.get("mean_score") or metrics.get("retrieval_recall_at_k")),
        "margin": "n/a",
        "latency": _latency_from_values(latencies),
        "source": item["path"],
    }


def _render_markdown(
    rows: list[dict[str, Any]],
    notes: list[str],
    manifest: dict[str, Any],
) -> str:
    lines = [
        "# Portfolio Eval Summary",
        "",
        "This summary curates the eval evidence a reviewer should read first. Raw JSON artifacts remain available for audit, but the portfolio story should start here.",
        "",
        "## Canonical Artifacts",
        "",
        *notes,
        "",
        "## Results",
        "",
        "| Artifact | Suite | Provider | Pass Rate | Safety | Provider Failures | Schema Failures | Unsupported Claims | Fallback | Mean Score | Acceptance Margin | Latency |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| {artifact_id} | {suite} | {provider} | {pass_rate} | {safety} | {provider_failures} | {schema_failures} | {unsupported_claims} | {fallback} | {mean_score} | {margin} | {latency} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Enterprise RAG Diagnostics",
            "",
            "- The portfolio RAG surface includes `/rag/debug` for retrieval inspection: query normalization, top chunks, source-family counts, stale-source flags, and source-conflict notices.",
            "- `knowledge/legacy_missing_concentration_sop.md` is a synthetic retired fixture used to demonstrate stale SOP handling and policy-vs-SOP precedence without using proprietary lab material.",
            "- Conflict handling is intentionally conservative: when retrieved sources disagree on a policy-critical rule, the answer surfaces the conflict with citations instead of silently picking the convenient source.",
            "- Stage 19 adds downstream QC provenance retrieval cases for synthetic summary metrics, lab-to-analysis lineage, unmatched sample IDs, and no-causal-inference boundaries.",
            "- Stage 20 adds corpus manifests and corpus fingerprints to RAG eval reports, plus a local corpus drift suite for irrelevant additions, source renames, conflicting SOPs, removed sources, updated sources, and stale SOPs.",
            "- Optional Pinecone backend comparison is available for retrieval infrastructure experiments, but local hybrid retrieval remains the default evidence path.",
            "",
            "## Interpretation",
            "",
            "- Portfolio demo bar: safety-control behavior should be perfect, active-provider safety/provider/schema failures should be zero, and any unsupported answer should be explicit rather than fabricated.",
            "- Production bar: this would need broader adversarial coverage, tenant/auth controls, monitored drift, incident playbooks, and baselines promoted through human approval.",
            "- Latency/cost tradeoff: deterministic paths are fastest and free; live OpenRouter evidence demonstrates model compatibility but has variable latency. Cost is not measured in these artifacts because the tested free model/provider path did not emit reliable cost metadata.",
            "- Deterministic baseline and frozen keyword baseline are comparison evidence. The active provider production gate is reported separately to avoid mistaking baseline failures for current model failures.",
            "- Corpus lifecycle evidence is generated separately with `make corpus-drift-eval`. It should pass before treating answer-quality regressions as model-only issues.",
            "",
            "## Residual Risks",
            "",
            "- The curated raw artifacts are local generated evidence and are ignored by Git unless intentionally exported.",
            "- Frozen baseline rotation should remain explicit and human-reviewed so eval targets do not drift with implementation changes.",
            "- Live model behavior can vary by provider availability, model version, and latency.",
            "- Hosted vector indexes can drift from the local corpus if metadata, namespace, or fingerprint checks are not enforced.",
            "",
            "## Manifest",
            "",
            f"- Manifest version: `{manifest.get('manifest_version')}`",
            f"- Manifest path: `{MANIFEST_PATH.relative_to(REPO_ROOT)}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _ratio(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "n/a"
    return f"{numerator}/{denominator} ({numerator / denominator:.1%})"


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int | float):
        return f"{value:.3f}"
    return str(value)


def _fallback_count(suite: dict[str, Any]) -> str:
    metrics = suite.get("suite_metrics", {})
    fallback_counts = metrics.get("fallback_counts")
    if isinstance(fallback_counts, dict):
        return str(sum(int(value) for value in fallback_counts.values()))
    return "0"


def _latency(metrics: dict[str, Any]) -> str:
    values = [
        metrics.get("latency_ms_p50"),
        metrics.get("latency_ms_p95"),
        metrics.get("latency_ms_max"),
    ]
    if not any(value is not None for value in values):
        return "n/a"
    return "p50={}; p95={}; max={}".format(*(_fmt(value) for value in values))


def _latency_from_values(values: list[float]) -> str:
    if not values:
        return "n/a"
    ordered = sorted(values)
    p50 = statistics.median(ordered)
    p95 = ordered[min(len(ordered) - 1, int(0.95 * (len(ordered) - 1)))]
    return f"p50={p50:.1f}ms; p95={p95:.1f}ms; max={max(ordered):.1f}ms"


if __name__ == "__main__":
    sys.exit(main())
