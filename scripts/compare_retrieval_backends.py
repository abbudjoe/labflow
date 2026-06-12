#!/usr/bin/env python3
"""Compare local and optional Pinecone retrieval backends."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_SRC = REPO_ROOT / "packages" / "labflow-rag" / "src"
if str(RAG_SRC) not in sys.path:
    sys.path.insert(0, str(RAG_SRC))

from labflow_rag.backends import LocalHybridBackend, PineconeBackend  # noqa: E402
from labflow_rag.backends.base import RetrievalBackend  # noqa: E402
from labflow_rag.conflict_detection import detect_conflicts  # noqa: E402
from labflow_rag.corpus_manifest import CHUNKER_VERSION, build_corpus_manifest  # noqa: E402
from labflow_rag.index import RagIndex  # noqa: E402
from labflow_rag.source_precedence import lifecycle_for_chunk_tags  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default="evals/retrieval_backend_cases.yaml")
    parser.add_argument("--corpus", default="knowledge")
    parser.add_argument("--output", default="artifacts/retrieval_backend_comparison/report.json")
    parser.add_argument("--top-k", type=int, default=8)
    args = parser.parse_args()

    cases = _load_cases(_repo_path(args.cases))
    corpus_dir = _repo_path(args.corpus)
    output_path = _repo_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_corpus_manifest(corpus_dir)
    index = RagIndex.from_corpus(corpus_dir)
    backends = (
        LocalHybridBackend(index),
        PineconeBackend(
            index=index,
            expected_corpus_fingerprint=manifest.corpus_fingerprint,
            expected_chunker_version=CHUNKER_VERSION,
        ),
    )
    backend_reports = [_evaluate_backend(backend, cases, top_k=args.top_k) for backend in backends]
    _attach_top_k_overlap(backend_reports)
    report = {
        "corpus_fingerprint": manifest.corpus_fingerprint,
        "top_k": args.top_k,
        "note": (
            "Backend comparison uses fixed-corpus retrieval cases. Corpus lifecycle "
            "variants are covered separately by scripts/run_corpus_drift_evals.py."
        ),
        "backends": backend_reports,
    }
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {output_path}")
    for backend in backend_reports:
        status = "skipped" if backend["skipped"] else "ran"
        recall = _display_metric(backend["required_source_family_recall"])
        exact = _display_metric(backend["exact_required_source_hit_rate"])
        stale = _display_metric(backend["stale_source_retrieval_rate"])
        print(
            "{name}: {status} family_recall={recall} exact_hit={exact} "
            "stale_rate={stale} p50={p50:.3f}ms p95={p95:.3f}ms".format(
                name=backend["backend_name"],
                status=status,
                recall=recall,
                exact=exact,
                stale=stale,
                p50=backend["latency_ms_p50"],
                p95=backend["latency_ms_p95"],
            )
        )
    return 0


def _evaluate_backend(
    backend: RetrievalBackend,
    cases: list[dict[str, object]],
    *,
    top_k: int,
) -> dict[str, object]:
    case_reports = []
    for case in cases:
        result = backend.query(str(case["question"]), top_k=top_k)
        families = tuple(dict.fromkeys(_source_family(item) for item in result.results))
        required = tuple(str(item) for item in case["required_source_families"])
        conflict_report = detect_conflicts(result.results)
        case_reports.append(
            {
                "case_id": case["id"],
                "skipped": result.skipped,
                "skip_reason": result.skip_reason,
                "retrieved_chunk_ids": [item.chunk_id for item in result.results],
                "retrieved_source_families": list(families),
                "required_source_families": list(required),
                "source_family_recall": _recall(required, families),
                "exact_required_source_hit": any(family in required for family in families),
                "stale_source_count": len(conflict_report.stale_sources),
                "conflict_count": len(conflict_report.conflicts),
                "latency_ms": result.latency_ms,
                "backend_metadata": result.metadata or {},
            }
        )
    latencies = [float(case["latency_ms"]) for case in case_reports]
    skipped = all(bool(case["skipped"]) for case in case_reports)
    quality_metrics = _backend_quality_metrics(case_reports, skipped=skipped)
    return {
        "backend_name": backend.backend_name,
        "backend_metadata": case_reports[0]["backend_metadata"] if case_reports else {},
        "skipped": skipped,
        "skip_reason": case_reports[0]["skip_reason"] if skipped and case_reports else None,
        "case_count": len(case_reports),
        "required_source_family_recall": quality_metrics["required_source_family_recall"],
        "exact_required_source_hit_rate": quality_metrics["exact_required_source_hit_rate"],
        "top_k_overlap": 1.0,
        "stale_source_retrieval_rate": quality_metrics["stale_source_retrieval_rate"],
        "conflict_detection_count": sum(int(case["conflict_count"]) for case in case_reports),
        "latency_ms_p50": _percentile(latencies, 50),
        "latency_ms_p95": _percentile(latencies, 95),
        "cases": case_reports,
    }


def _attach_top_k_overlap(backend_reports: list[dict[str, object]]) -> None:
    if len(backend_reports) < 2:
        return
    reference_cases = backend_reports[0]["cases"]
    if not isinstance(reference_cases, list):
        return
    for backend_report in backend_reports[1:]:
        cases = backend_report["cases"]
        if not isinstance(cases, list):
            backend_report["top_k_overlap"] = 0.0
            continue
        overlaps = []
        for reference_case, candidate_case in zip(reference_cases, cases, strict=False):
            if not isinstance(reference_case, dict) or not isinstance(candidate_case, dict):
                continue
            if candidate_case.get("skipped"):
                continue
            reference_ids = set(str(item) for item in reference_case["retrieved_chunk_ids"])
            candidate_ids = set(str(item) for item in candidate_case["retrieved_chunk_ids"])
            denominator = len(reference_ids | candidate_ids)
            overlaps.append(len(reference_ids & candidate_ids) / denominator if denominator else 0.0)
        backend_report["top_k_overlap"] = _mean(overlaps) if overlaps else None


def _backend_quality_metrics(
    case_reports: list[dict[str, object]],
    *,
    skipped: bool,
) -> dict[str, float | None]:
    if skipped:
        return {
            "required_source_family_recall": None,
            "exact_required_source_hit_rate": None,
            "stale_source_retrieval_rate": None,
        }
    return {
        "required_source_family_recall": _mean(
            case["source_family_recall"] for case in case_reports
        ),
        "exact_required_source_hit_rate": _mean(
            1.0 if case["exact_required_source_hit"] else 0.0 for case in case_reports
        ),
        "stale_source_retrieval_rate": _mean(
            1.0 if int(case["stale_source_count"]) > 0 else 0.0 for case in case_reports
        ),
    }


def _display_metric(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.3f}"


def _source_family(result: object) -> str:
    lifecycle = lifecycle_for_chunk_tags(
        document_id=result.document_id,
        tags=result.chunk.tags,
        text=result.chunk.text,
    )
    return lifecycle.source_family


def _recall(required: tuple[str, ...], observed: tuple[str, ...]) -> float:
    if not required:
        return 1.0
    return len(set(required) & set(observed)) / len(set(required))


def _mean(values: object) -> float:
    materialized = [float(value) for value in values]
    return sum(materialized) / len(materialized) if materialized else 0.0


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    quantiles = statistics.quantiles(values, n=100)
    return quantiles[min(98, max(0, percentile - 1))]


def _load_cases(path: Path) -> list[dict[str, object]]:
    payload = yaml.safe_load(path.read_text())
    if not isinstance(payload, list):
        raise ValueError("cases file must contain a list")
    return [dict(item) for item in payload]


def _repo_path(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


if __name__ == "__main__":
    raise SystemExit(main())
