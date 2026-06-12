from __future__ import annotations

import json
from pathlib import Path
import shutil

from pytest import MonkeyPatch

from labflow_rag.backends import PineconeBackend, PineconeBackendConfig
from labflow_rag.conflict_detection import ConflictResolution, detect_conflicts
from labflow_rag.corpus_manifest import build_corpus_manifest
from labflow_rag.evals import EvalRunConfig, run_eval
from labflow_rag.index import RagIndex
from labflow_rag.retrieval import HybridRetriever


def _copy_corpus(tmp_path: Path) -> Path:
    source = Path("knowledge")
    target = tmp_path / "knowledge"
    shutil.copytree(source, target)
    return target


def test_corpus_fingerprint_is_stable_for_identical_corpus(tmp_path: Path) -> None:
    corpus_a = _copy_corpus(tmp_path / "a")
    corpus_b = _copy_corpus(tmp_path / "b")

    first = build_corpus_manifest(corpus_a)
    second = build_corpus_manifest(corpus_b)

    assert first.corpus_fingerprint == second.corpus_fingerprint
    assert first.to_json_dict()["document_count"] == second.to_json_dict()["document_count"]


def test_corpus_fingerprint_changes_when_content_changes(tmp_path: Path) -> None:
    corpus = _copy_corpus(tmp_path)
    before = build_corpus_manifest(corpus).corpus_fingerprint
    path = corpus / "batch_readiness_doctrine.md"
    path.write_text(path.read_text() + "\n\nSynthetic lifecycle test change.\n")

    after = build_corpus_manifest(corpus).corpus_fingerprint

    assert before != after


def test_corpus_fingerprint_ignores_absolute_path(tmp_path: Path) -> None:
    corpus_a = _copy_corpus(tmp_path / "abs_a")
    corpus_b = _copy_corpus(tmp_path / "abs_b")

    payload_a = build_corpus_manifest(corpus_a).to_json_dict()
    payload_b = build_corpus_manifest(corpus_b).to_json_dict()

    assert payload_a["corpus_fingerprint"] == payload_b["corpus_fingerprint"]
    assert str(corpus_a) not in json.dumps(payload_a)
    assert str(corpus_b) not in json.dumps(payload_b)


def test_eval_report_includes_corpus_fingerprint() -> None:
    report = run_eval(
        EvalRunConfig(top_k=6, retrieval_only=True, eval_run_id="eval_corpus_fingerprint"),
    )
    payload = report.to_json_dict()

    assert payload["corpus_fingerprint"].startswith("sha256:")
    assert payload["corpus_manifest"]["corpus_fingerprint"] == payload["corpus_fingerprint"]


def test_conflicting_lower_authority_source_is_resolved_by_locked_doctrine(tmp_path: Path) -> None:
    corpus = _copy_corpus(tmp_path)
    (corpus / "draft_conflicting_janus_sop.md").write_text(
        "# Draft Conflicting JANUS SOP\n\n"
        "## Retrieval Tags\n\n"
        "`source_family:janus_csv_worklist_spec`, `status:draft`, `authority:current_sop`\n\n"
        "JANUS output can generate for an invalid batch.\n",
    )
    index = RagIndex.from_corpus(corpus)
    results = HybridRetriever(index).retrieve("Can JANUS output generate for an invalid batch?", top_k=12)

    report = detect_conflicts(results)

    assert any(
        conflict.resolution is ConflictResolution.LOCKED_DOCTRINE_RESOLVED
        for conflict in report.conflicts
    )


def test_pinecone_backend_skips_without_configuration(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("PINECONE_API_KEY", raising=False)
    backend = PineconeBackend(PineconeBackendConfig.from_env())

    result = backend.query("robot readiness", top_k=3)

    assert result.skipped is True
    assert result.skip_reason == "PINECONE_API_KEY is absent."
