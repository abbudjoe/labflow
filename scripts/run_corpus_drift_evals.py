#!/usr/bin/env python3
"""Run corpus lifecycle drift evals without mutating the real knowledge corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from time import perf_counter
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_SRC = REPO_ROOT / "packages" / "labflow-rag" / "src"
if str(RAG_SRC) not in sys.path:
    sys.path.insert(0, str(RAG_SRC))

from labflow_rag.conflict_detection import detect_conflicts  # noqa: E402
from labflow_rag.corpus_manifest import build_corpus_manifest  # noqa: E402
from labflow_rag.index import RagIndex  # noqa: E402
from labflow_rag.retrieval import HybridRetriever  # noqa: E402
from labflow_rag.source_precedence import lifecycle_for_chunk_tags  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default="evals/corpus_drift_cases.yaml")
    parser.add_argument("--corpus", default="knowledge")
    parser.add_argument("--output", default="artifacts/corpus_drift/corpus_drift_report.json")
    parser.add_argument("--top-k", type=int, default=8)
    args = parser.parse_args()

    cases = _load_cases(_repo_path(args.cases))
    source_corpus = _repo_path(args.corpus)
    output_path = _repo_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix="labflow-corpus-drift-") as tmp:
        tmp_root = Path(tmp)
        for case in cases:
            variant_dir = tmp_root / case["variant"]
            shutil.copytree(source_corpus, variant_dir)
            _apply_variant(variant_dir, case["variant"])
            results.append(_run_case(case, variant_dir, top_k=args.top_k))

    passed = sum(1 for result in results if result["passed"])
    report = {
        "case_count": len(results),
        "passed_count": passed,
        "failed_count": len(results) - passed,
        "top_k": args.top_k,
        "cases": results,
    }
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {output_path}")
    print(f"corpus_drift cases={len(results)} passed={passed} failed={len(results) - passed}")
    return 0 if passed == len(results) else 1


def _load_cases(path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text())
    if not isinstance(payload, list):
        raise ValueError("corpus drift cases must be a list")
    return [dict(item) for item in payload]


def _run_case(case: dict[str, Any], corpus_dir: Path, *, top_k: int) -> dict[str, Any]:
    manifest = build_corpus_manifest(corpus_dir)
    index = RagIndex.from_corpus(corpus_dir)
    retriever = HybridRetriever(index)
    start = perf_counter()
    results = retriever.retrieve(case["question"], top_k=top_k)
    latency_ms = (perf_counter() - start) * 1000
    families = tuple(dict.fromkeys(_source_family(result) for result in results))
    required = tuple(case["required_source_families"])
    missing = tuple(family for family in required if family not in families)
    conflict_report = detect_conflicts(results)
    stale_count = len(conflict_report.stale_sources)
    expect_failure = bool(case.get("expect_failure", False))
    source_family_pass = not missing
    if case["variant"] == "removed_source":
        passed = bool(missing) if expect_failure else source_family_pass
    elif case["variant"] == "conflicting_sop":
        passed = source_family_pass and bool(conflict_report.conflicts)
    elif case["variant"] in {"updated_current_sop", "stale_sop"}:
        passed = source_family_pass and stale_count > 0
    else:
        passed = source_family_pass
    return {
        "case_id": case["id"],
        "variant": case["variant"],
        "passed": passed,
        "question": case["question"],
        "required_source_families": list(required),
        "retrieved_source_families": list(families),
        "missing_source_families": list(missing),
        "conflicts": [conflict.to_json_dict() for conflict in conflict_report.conflicts],
        "stale_sources": [source.to_json_dict() for source in conflict_report.stale_sources],
        "latency_ms": round(latency_ms, 3),
        "corpus_fingerprint": manifest.corpus_fingerprint,
        "retrieved_chunk_ids": [result.chunk_id for result in results],
    }


def _source_family(result: Any) -> str:
    lifecycle = lifecycle_for_chunk_tags(
        document_id=result.document_id,
        tags=result.chunk.tags,
        text=result.chunk.text,
    )
    return lifecycle.source_family


def _apply_variant(corpus_dir: Path, variant: str) -> None:
    if variant == "irrelevant_docs":
        (corpus_dir / "irrelevant_facilities_note.md").write_text(
            "# Cafeteria Menu\n\nThis synthetic note is unrelated to LabFlow retrieval.\n",
        )
    elif variant == "renamed_rechunked":
        source = corpus_dir / "dna_normalization_sop.md"
        target = corpus_dir / "renamed_dna_normalization_sop.md"
        target.write_text(
            source.read_text()
            + "\n\n## Retrieval Tags\n\n`source_family:dna_normalization_sop`, `status:current`\n"
        )
        source.unlink()
    elif variant == "conflicting_sop":
        (corpus_dir / "draft_conflicting_janus_sop.md").write_text(
            "# Draft Conflicting JANUS SOP\n\n"
            "version: draft\n"
            "effective_date: 2026-06-01\n\n"
            "## Retrieval Tags\n\n"
            "`source_family:janus_csv_worklist_spec`, `status:draft`, `authority:current_sop`\n\n"
            "## Draft Rule\n\n"
            "This draft says JANUS output can generate for an invalid batch, which conflicts "
            "with locked LabFlow doctrine and must not be trusted without review.\n",
        )
    elif variant == "removed_source":
        (corpus_dir / "dna_normalization_sop.md").unlink(missing_ok=True)
    elif variant == "updated_current_sop":
        original = corpus_dir / "dna_normalization_sop.md"
        retired = corpus_dir / "retired_dna_normalization_sop.md"
        retired.write_text(
            original.read_text()
            + "\n\n## Retrieval Tags\n\n`source_family:dna_normalization_sop`, `status:retired`, `authority:retired_sop`\n"
        )
        original.write_text(
            original.read_text()
            + "\n\nversion: v2\nsupersedes: retired_dna_normalization_sop.md\n"
            "## Retrieval Tags\n\n`source_family:dna_normalization_sop`, `status:current`, `authority:current_sop`\n"
        )
    elif variant == "stale_sop":
        (corpus_dir / "retired_ngs_qc_provenance_policy.md").write_text(
            "# Retired NGS QC Provenance Policy\n\n"
            "version: retired\n"
            "effective_date: 2025-01-01\n\n"
            "## Retrieval Tags\n\n"
            "`source_family:ngs_qc_provenance_policy`, `status:retired`, `authority:retired_sop`\n\n"
            "## Retired Rule\n\n"
            "This retired SOP mentions downstream QC provenance and lab root cause review. "
            "It is stale and should be surfaced as stale when retrieved.\n",
        )


def _repo_path(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


if __name__ == "__main__":
    raise SystemExit(main())
