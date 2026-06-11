"""Settings and local state for the LabFlow FastAPI app."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from labflow_agent import AgentToolRuntime, LabFlowAgentRuntime
from labflow_agent.artifacts import ArtifactRecord
from labflow_rag import HybridRetriever, RagIndex, answer_query, retrieval_debug_report
from labflow_rag.evals.runner import EvalRunReport


class ApiSettings(BaseModel):
    """Local-first API settings."""

    model_config = ConfigDict(frozen=True)

    corpus_dir: Path = Path("knowledge")
    artifact_store_dir: Path = Path(".codex_build/api_artifacts")
    eval_cases_path: Path = Path("evals/golden_questions.yaml")
    rag_top_k: int = Field(default=6, ge=1)


class LocalFileArtifactStore:
    """Persist committed artifact records as JSON files on local disk."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def persist(self, record: ArtifactRecord) -> Path:
        path = self._path_for(record.artifact_record_id)
        path.write_text(json.dumps(record.to_json_dict(), indent=2, sort_keys=True))
        return path

    def persist_many(self, records: tuple[ArtifactRecord, ...]) -> tuple[Path, ...]:
        return tuple(self.persist(record) for record in records)

    def get(self, artifact_id: str) -> dict[str, Any] | None:
        path = self._path_for(artifact_id)
        if not path.exists():
            return None
        raw = json.loads(path.read_text())
        return raw if isinstance(raw, dict) else None

    def _path_for(self, artifact_id: str) -> Path:
        return self.root / f"{artifact_id}.json"


class ApiState:
    """Shared local runtime state for route handlers."""

    def __init__(self, settings: ApiSettings | None = None) -> None:
        self.settings = settings or ApiSettings()
        self.index = RagIndex.from_corpus(self.settings.corpus_dir)
        self.retriever = HybridRetriever(self.index)
        self.tool_runtime = AgentToolRuntime()
        self.agent_runtime = LabFlowAgentRuntime(
            index=self.index,
            retriever=self.retriever,
            tool_runtime=self.tool_runtime,
            top_k=self.settings.rag_top_k,
        )
        self.file_artifact_store = LocalFileArtifactStore(self.settings.artifact_store_dir)
        self.eval_reports: dict[str, EvalRunReport] = {}

    def rag_query(self, question: str) -> dict[str, Any]:
        return answer_query(
            question,
            self.index,
            retriever=self.retriever,
            top_k=self.settings.rag_top_k,
        ).to_json_dict()

    def rag_debug(self, question: str) -> dict[str, Any]:
        return retrieval_debug_report(
            question,
            self.index,
            retriever=self.retriever,
            top_k=self.settings.rag_top_k,
        ).to_json_dict()
