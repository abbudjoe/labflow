"""Sample ancestry tracking by sample ID."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from labflow_core.domain.identifiers import (
    optional_nonblank_identifier,
    require_nonblank_identifier,
)
from labflow_core.domain.statuses import AncestryEventType, WorkflowType
from labflow_core.domain.wells import WellCoordinate

JsonMapping = Mapping[str, Any]


class AncestryRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    parent_sample_id: str | None = None
    child_sample_id: str = Field(min_length=1)
    event_type: AncestryEventType
    source_container_id: str | None = None
    source_well: WellCoordinate | None = None
    destination_container_id: str | None = None
    destination_well: WellCoordinate | None = None
    batch_id: str = Field(min_length=1)
    workflow_type: WorkflowType
    metadata_json: str = "{}"

    @field_validator("source_well", "destination_well", mode="before")
    @classmethod
    def parse_optional_well(cls, value: Any) -> Any:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return WellCoordinate.model_validate(value)

    @field_validator("child_sample_id", "batch_id")
    @classmethod
    def required_identifier(cls, value: str, info: ValidationInfo) -> str:
        return require_nonblank_identifier(value, info.field_name)

    @field_validator(
        "parent_sample_id",
        "source_container_id",
        "destination_container_id",
        mode="before",
    )
    @classmethod
    def optional_identifier(cls, value: str | None) -> str | None:
        return optional_nonblank_identifier(value)

    def to_row(self) -> dict[str, str]:
        return {
            "parent_sample_id": self.parent_sample_id or "",
            "child_sample_id": self.child_sample_id,
            "event_type": self.event_type.value,
            "source_container_id": self.source_container_id or "",
            "source_well": str(self.source_well) if self.source_well else "",
            "destination_container_id": self.destination_container_id or "",
            "destination_well": str(self.destination_well) if self.destination_well else "",
            "batch_id": self.batch_id,
            "workflow_type": self.workflow_type.value,
            "metadata_json": self.metadata_json,
        }


ANCESTRY_COLUMNS = [
    "parent_sample_id",
    "child_sample_id",
    "event_type",
    "source_container_id",
    "source_well",
    "destination_container_id",
    "destination_well",
    "batch_id",
    "workflow_type",
    "metadata_json",
]


class AncestryTracker:
    def __init__(self) -> None:
        self._records: list[AncestryRecord] = []

    @property
    def records(self) -> tuple[AncestryRecord, ...]:
        return tuple(self._records)

    def add(self, record: AncestryRecord) -> None:
        self._records.append(record)

    def record_split(
        self,
        *,
        parent_sample_id: str,
        child_sample_id: str,
        source_container_id: str,
        source_well: WellCoordinate,
        destination_container_id: str,
        destination_well: WellCoordinate,
        batch_id: str,
        workflow_type: WorkflowType,
        expected_child_concentration_ng_per_ul: float,
    ) -> AncestryRecord:
        record = AncestryRecord(
            parent_sample_id=parent_sample_id,
            child_sample_id=child_sample_id,
            event_type=AncestryEventType.SPLIT_CREATED,
            source_container_id=source_container_id,
            source_well=source_well,
            destination_container_id=destination_container_id,
            destination_well=destination_well,
            batch_id=batch_id,
            workflow_type=workflow_type,
            metadata_json=json.dumps(
                {
                    "expected_child_concentration_ng_per_ul": round(
                        expected_child_concentration_ng_per_ul,
                        6,
                    ),
                    "requires_requant": True,
                },
                sort_keys=True,
            ),
        )
        self.add(record)
        return record

    def record_event(
        self,
        *,
        sample_id: str,
        event_type: AncestryEventType,
        batch_id: str,
        workflow_type: WorkflowType,
        metadata: JsonMapping | None = None,
    ) -> AncestryRecord:
        record = AncestryRecord(
            child_sample_id=sample_id,
            event_type=event_type,
            batch_id=batch_id,
            workflow_type=workflow_type,
            metadata_json=json.dumps(dict(metadata or {}), sort_keys=True),
        )
        self.add(record)
        return record
