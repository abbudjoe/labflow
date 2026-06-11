"""Schema-mapped Varioskan TSV ingestion."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from labflow_core.domain.wells import WellCoordinate


class VarioskanSchemaMapping(BaseModel):
    model_config = ConfigDict(frozen=True)

    well: str = "Well"
    reading: str = "Reading"
    plate_id: str = "Plate ID"
    sample_id: str = "Sample ID"

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> VarioskanSchemaMapping:
        if not config:
            return cls()
        columns = config.get("columns", config)
        if not isinstance(columns, dict):
            return cls()
        return cls(
            well=str(columns.get("well", "Well")),
            reading=str(columns.get("reading", "Reading")),
            plate_id=str(columns.get("plate_id", "Plate ID")),
            sample_id=str(columns.get("sample_id", "Sample ID")),
        )


class VarioskanReading(BaseModel):
    model_config = ConfigDict(frozen=True)

    plate_id: str = Field(min_length=1)
    well: WellCoordinate
    reading: float
    sample_id: str | None = None

    @field_validator("well", mode="before")
    @classmethod
    def parse_well(cls, value: Any) -> Any:
        return WellCoordinate.model_validate(value)


def parse_varioskan_tsv(path: Path, mapping: VarioskanSchemaMapping) -> list[VarioskanReading]:
    readings: list[VarioskanReading] = []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            sample_id = row.get(mapping.sample_id) or None
            readings.append(
                VarioskanReading(
                    plate_id=str(row[mapping.plate_id]),
                    well=WellCoordinate.model_validate(row[mapping.well]),
                    reading=float(row[mapping.reading]),
                    sample_id=sample_id.strip() if sample_id else None,
                )
            )
    return sorted(readings, key=lambda reading: (reading.plate_id, reading.well.sort_key))
