"""Sample records with explicit units."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from labflow_core.domain.identifiers import (
    optional_nonblank_identifier,
    require_nonblank_identifier,
)
from labflow_core.domain.statuses import AnalyteType
from labflow_core.domain.wells import WellCoordinate


class Sample(BaseModel):
    model_config = ConfigDict(frozen=True)

    sample_id: str = Field(min_length=1)
    analyte_type: AnalyteType
    source_container_id: str = Field(min_length=1)
    source_well: WellCoordinate
    stock_concentration_ng_per_ul: float | None = None
    available_volume_ul: float | None = None

    @field_validator("sample_id", "source_container_id")
    @classmethod
    def required_identifier(cls, value: str, info: ValidationInfo) -> str:
        return require_nonblank_identifier(value, info.field_name)

    @field_validator("source_well", mode="before")
    @classmethod
    def parse_source_well(cls, value: Any) -> Any:
        return WellCoordinate.model_validate(value)


class NormalizationSampleInput(BaseModel):
    """Externally loaded sample row for normalization planning."""

    model_config = ConfigDict(frozen=True)

    sample_id: str = Field(min_length=1)
    analyte_type: AnalyteType = AnalyteType.DS_DNA
    source_container_id: str = Field(min_length=1)
    source_well: WellCoordinate
    stock_concentration_ng_per_ul: float
    available_volume_ul: float
    destination_container_id: str | None = None
    destination_well: WellCoordinate | None = None

    @field_validator("source_well", "destination_well", mode="before")
    @classmethod
    def parse_optional_well(cls, value: Any) -> Any:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return WellCoordinate.model_validate(value)

    @field_validator("sample_id", "source_container_id")
    @classmethod
    def required_identifier(cls, value: str, info: ValidationInfo) -> str:
        return require_nonblank_identifier(value, info.field_name)

    @field_validator("destination_container_id", mode="before")
    @classmethod
    def optional_destination_container_id(cls, value: str | None) -> str | None:
        return optional_nonblank_identifier(value)
