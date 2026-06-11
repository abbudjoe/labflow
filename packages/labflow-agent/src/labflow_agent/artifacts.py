"""Local artifact records for approved agent commit actions."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from labflow_agent.models import JsonDict


class ArtifactRecord(BaseModel):
    """Record that an artifact was committed to the local artifact store."""

    model_config = ConfigDict(frozen=True)

    artifact_record_id: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    name: str = Field(min_length=1)
    content_type: str = Field(min_length=1)
    source_dry_run_audit_event_id: str = Field(min_length=1)
    commit_audit_event_id: str = Field(min_length=1)
    created_at: str = Field(min_length=1)
    data: Any

    def to_json_dict(self) -> JsonDict:
        return self.model_dump(mode="json")


class ArtifactStore:
    """In-memory artifact record store for Stage 10 commits."""

    def __init__(self) -> None:
        self._records: dict[str, ArtifactRecord] = {}

    def commit_from_tool_result(
        self,
        *,
        result: JsonDict,
        dry_run_audit_event_id: str,
        commit_audit_event_id: str,
    ) -> tuple[ArtifactRecord, ...]:
        artifacts = result.get("artifacts")
        if not isinstance(artifacts, list):
            return ()

        records: list[ArtifactRecord] = []
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            artifact_id = str(artifact["artifact_id"])
            record_id = _record_id(artifact_id, dry_run_audit_event_id, commit_audit_event_id)
            record = ArtifactRecord(
                artifact_record_id=record_id,
                artifact_id=artifact_id,
                artifact_type=str(artifact["artifact_type"]),
                name=str(artifact["name"]),
                content_type=str(artifact.get("content_type", "application/json")),
                source_dry_run_audit_event_id=dry_run_audit_event_id,
                commit_audit_event_id=commit_audit_event_id,
                created_at=datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z"),
                data=artifact.get("data"),
            )
            self._records[record.artifact_record_id] = record
            records.append(record)
        return tuple(records)

    def list_records(self) -> tuple[ArtifactRecord, ...]:
        return tuple(self._records.values())

    def get(self, artifact_record_id: str) -> ArtifactRecord | None:
        return self._records.get(artifact_record_id)


def _record_id(artifact_id: str, dry_run_audit_event_id: str, commit_audit_event_id: str) -> str:
    digest = sha256(
        f"{artifact_id}:{dry_run_audit_event_id}:{commit_audit_event_id}".encode()
    ).hexdigest()[:16]
    return f"artifact_record_{digest}"
