from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil

from pytest import MonkeyPatch

from labflow_rag.backends import (
    BackendRetrieverAdapter,
    PineconeBackend,
    PineconeBackendConfig,
    build_retriever_from_env,
    retriever_runtime_metadata,
)
from labflow_rag.backends.pinecone import DEFAULT_PINECONE_DIMENSION
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


def test_pinecone_retriever_adapter_reports_skipped_live_query(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("PINECONE_API_KEY", raising=False)
    index = RagIndex.from_corpus("knowledge")
    backend = PineconeBackend(PineconeBackendConfig.from_env(), index=index)
    retriever = BackendRetrieverAdapter(backend)

    results = retriever.retrieve("robot readiness", top_k=3)
    metadata = retriever.metadata()

    assert results == ()
    assert retriever.query_count == 1
    assert retriever.skipped_count == 1
    assert metadata["last_query_skipped"] is True
    assert metadata["last_query_skip_reason"] == "PINECONE_API_KEY is absent."


def test_retriever_factory_defaults_to_local_without_credentials(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("LABFLOW_RAG_BACKEND", raising=False)
    monkeypatch.delenv("PINECONE_API_KEY", raising=False)
    index = RagIndex.from_corpus("knowledge")

    build = build_retriever_from_env(index)
    results = build.retriever.retrieve("robot readiness", top_k=3)
    metadata = retriever_runtime_metadata(build.retriever, build.metadata)

    assert build.backend_name == "local"
    assert metadata["live"] is False
    assert results


def test_retriever_factory_requires_confirmation_for_pinecone(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("LABFLOW_RAG_BACKEND", "pinecone")
    index = RagIndex.from_corpus("knowledge")

    try:
        build_retriever_from_env(index)
    except ValueError as exc:
        assert "confirm-live-pinecone" in str(exc)
    else:  # pragma: no cover - keeps the assertion message useful.
        raise AssertionError("Pinecone backend should require explicit live confirmation.")


def test_pinecone_dimension_default_matches_indexer_contract(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("PINECONE_DIMENSION", raising=False)

    config = PineconeBackendConfig.from_env()

    assert config.dimension == DEFAULT_PINECONE_DIMENSION
    assert DEFAULT_PINECONE_DIMENSION == 384


def test_pinecone_backend_hydrates_live_matches_from_local_index() -> None:
    index = RagIndex.from_corpus("knowledge")
    expected_chunk = index.chunks[0]
    backend = PineconeBackend(
        PineconeBackendConfig(
            api_key="test-key",
            index_name="labflow",
            namespace="labflow-test",
            cloud="aws",
            region="us-east-1",
            dimension=16,
            metric="cosine",
        ),
        index=index,
        client=_FakePineconeClient(
            matches=[
                {
                    "id": expected_chunk.chunk_id,
                    "score": 0.87,
                    "metadata": {
                        "corpus_fingerprint": "sha256:current",
                        "chunker_version": "chunker-v1",
                    },
                }
            ]
        ),
        expected_corpus_fingerprint="sha256:current",
        expected_chunker_version="chunker-v1",
    )

    result = backend.query("robot readiness", top_k=3)

    assert result.skipped is False
    result_by_id = {item.chunk_id: item for item in result.results}
    assert expected_chunk.chunk_id in result_by_id
    assert result_by_id[expected_chunk.chunk_id].chunk.text == expected_chunk.text
    assert result.metadata is not None
    assert result.metadata["match_count"] == 1
    assert result.metadata["local_hybrid_rerank_enabled"] is True


def test_pinecone_backend_filters_hosted_metadata_mismatches() -> None:
    index = RagIndex.from_corpus("knowledge")
    expected_chunk = index.chunks[0]
    backend = PineconeBackend(
        PineconeBackendConfig(
            api_key="test-key",
            index_name="labflow",
            namespace="labflow-test",
            cloud="aws",
            region="us-east-1",
            dimension=16,
            metric="cosine",
        ),
        index=index,
        client=_FakePineconeClient(
            matches=[
                {
                    "id": expected_chunk.chunk_id,
                    "score": 0.87,
                    "metadata": {
                        "corpus_fingerprint": "sha256:old",
                        "chunker_version": "chunker-v1",
                    },
                }
            ]
        ),
        expected_corpus_fingerprint="sha256:current",
        expected_chunker_version="chunker-v1",
    )

    result = backend.query("robot readiness", top_k=3)

    assert result.skipped is False
    assert result.metadata is not None
    assert result.metadata["metadata_mismatch_count"] == 1
    assert all(item.chunk_id != expected_chunk.chunk_id for item in result.results)
    assert all(item.retrieval_mode == "pinecone_local_hybrid" for item in result.results)


def test_pinecone_backend_reports_missing_local_chunks() -> None:
    index = RagIndex.from_corpus("knowledge")
    backend = PineconeBackend(
        PineconeBackendConfig(
            api_key="test-key",
            index_name="labflow",
            namespace="labflow-test",
            cloud="aws",
            region="us-east-1",
            dimension=16,
            metric="cosine",
        ),
        index=index,
        client=_FakePineconeClient(matches=[{"id": "stale_chunk_999", "score": 0.5}]),
    )

    result = backend.query("robot readiness", top_k=3)

    assert result.skipped is False
    assert result.metadata is not None
    assert result.metadata["missing_local_chunk_count"] == 1
    assert result.results
    assert all(item.chunk_id != "stale_chunk_999" for item in result.results)


def test_live_pinecone_upsert_contract_uses_metadata_and_configured_dimension() -> None:
    index = RagIndex.from_corpus("knowledge")
    client = _FakePineconeClient(matches=[])
    upsert_knowledge_index = _load_index_script().upsert_knowledge_index

    upserted = upsert_knowledge_index(
        index=index,
        corpus_fingerprint="sha256:test",
        index_name="labflow",
        namespace="labflow-test",
        dimension=16,
        batch_size=50,
        client=client,
    )

    assert upserted == index.chunk_count
    assert client.index.upserts
    first_record = client.index.upserts[0][0]
    assert len(first_record["values"]) == 16
    assert first_record["metadata"]["chunk_id"] == first_record["id"]
    assert first_record["metadata"]["corpus_fingerprint"] == "sha256:test"
    assert first_record["metadata"]["source_family"]
    assert client.index.namespaces == ["labflow-test"] * len(client.index.upserts)


class _FakePineconeClient:
    def __init__(self, *, matches: list[dict[str, object]]) -> None:
        self.index = _FakePineconeIndex(matches=matches)

    def Index(self, _name: str) -> "_FakePineconeIndex":  # noqa: N802
        return self.index


class _FakePineconeIndex:
    def __init__(self, *, matches: list[dict[str, object]]) -> None:
        self._matches = matches
        self.upserts: list[list[dict[str, object]]] = []
        self.namespaces: list[str] = []

    def query(
        self,
        *,
        vector: list[float],
        top_k: int,
        include_metadata: bool,
        namespace: str,
    ) -> dict[str, object]:
        assert vector
        assert top_k > 0
        assert include_metadata is True
        assert namespace
        return {"matches": self._matches[:top_k]}

    def upsert(self, *, vectors: list[dict[str, object]], namespace: str) -> None:
        for vector in vectors:
            metadata = vector["metadata"]
            assert isinstance(metadata, dict)
            for value in metadata.values():
                assert value is not None
                assert isinstance(value, (str, int, float, bool, list))
                if isinstance(value, list):
                    assert all(isinstance(item, str) for item in value)
        self.upserts.append(vectors)
        self.namespaces.append(namespace)


def _load_index_script() -> object:
    script_path = Path("scripts/index_knowledge_pinecone.py").resolve()
    spec = importlib.util.spec_from_file_location("index_knowledge_pinecone_test", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
