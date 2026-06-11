#!/usr/bin/env python3
"""Run local LabFlow RAG evals and write a JSON report."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_SRC = REPO_ROOT / "packages" / "labflow-rag" / "src"
if str(RAG_SRC) not in sys.path:
    sys.path.insert(0, str(RAG_SRC))

from labflow_rag.evals import EvalRunConfig, run_eval, write_eval_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default="evals/golden_questions.yaml")
    parser.add_argument("--corpus", default="knowledge")
    parser.add_argument("--output-dir", default="artifacts/eval_reports")
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--eval-run-id", default=None)
    parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help="Skip answer composition and evaluate retrieval/citation metadata only.",
    )
    args = parser.parse_args()
    cases_path = _resolve_repo_path(args.cases)
    corpus_dir = _resolve_repo_path(args.corpus)
    output_dir = _resolve_repo_path(args.output_dir)

    report = run_eval(
        EvalRunConfig(
            cases_path=cases_path,
            corpus_dir=corpus_dir,
            top_k=args.top_k,
            retrieval_only=args.retrieval_only,
            eval_run_id=args.eval_run_id,
        )
    )
    report_path = write_eval_report(report, output_dir)
    metrics = report.metrics
    print(f"Wrote RAG eval report: {report_path}")
    print(
        "cases={case_count} passed={passed_count} failed={failed_count} "
        "retrieval_recall_at_k={retrieval:.3f} citation_precision_proxy={citation:.3f} "
        "answer_contains_match={answer:.3f} disallowed_violations={violations}".format(
            case_count=metrics.case_count,
            passed_count=metrics.passed_count,
            failed_count=metrics.failed_count,
            retrieval=metrics.retrieval_recall_at_k,
            citation=metrics.citation_precision_proxy,
            answer=metrics.required_answer_contains_match,
            violations=metrics.disallowed_answer_violations,
        )
    )
    return 0


def _resolve_repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
