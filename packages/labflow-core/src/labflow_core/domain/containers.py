"""Container domain records."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from labflow_core.domain.identifiers import require_nonblank_identifier
from labflow_core.domain.units import DEFAULT_MAX_DESTINATION_VOLUME_UL


class ContainerType(BaseModel):
    model_config = ConfigDict(frozen=True)

    container_type_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    format: str = Field(min_length=1)
    rows: int = Field(gt=0)
    columns: int = Field(gt=0)
    nominal_capacity_ul: float = Field(gt=0)
    max_working_volume_ul: float = Field(gt=0)
    closure_type: str = Field(min_length=1)
    vendor: str = "Thermo Fisher"

    @field_validator("container_type_id", "name", "format", "closure_type", "vendor")
    @classmethod
    def require_nonblank_text(cls, value: str, info: ValidationInfo) -> str:
        return require_nonblank_identifier(value, info.field_name)

    @model_validator(mode="after")
    def max_volume_cannot_exceed_nominal(self) -> ContainerType:
        if self.max_working_volume_ul > self.nominal_capacity_ul:
            msg = "max_working_volume_ul cannot exceed nominal_capacity_ul"
            raise ValueError(msg)
        return self

    @field_validator("format")
    @classmethod
    def require_supported_format(cls, value: str) -> str:
        if value != "96_well":
            msg = "Only 96_well containers are supported in v0.1"
            raise ValueError(msg)
        return value


class Container(BaseModel):
    model_config = ConfigDict(frozen=True)

    container_id: str = Field(min_length=1)
    barcode: str = Field(min_length=1)
    container_type_id: str = Field(min_length=1)

    @field_validator("container_id", "barcode", "container_type_id")
    @classmethod
    def require_nonblank_text(cls, value: str, info: ValidationInfo) -> str:
        return require_nonblank_identifier(value, info.field_name)


def matrix_96_1ml_screwtop_type() -> ContainerType:
    return ContainerType(
        container_type_id="matrix_96_1ml_screwtop",
        name="Thermo Fisher Matrix 96 x 1 mL ScrewTop Tube Rack",
        format="96_well",
        rows=8,
        columns=12,
        nominal_capacity_ul=1000.0,
        max_working_volume_ul=DEFAULT_MAX_DESTINATION_VOLUME_UL,
        closure_type="screw_top",
    )


def matrix_96_1ml_rubber_septum_type() -> ContainerType:
    return ContainerType(
        container_type_id="matrix_96_1ml_septum",
        name="Thermo Fisher Matrix 96 x 1 mL Septum/Rubber-Top Tube Rack",
        format="96_well",
        rows=8,
        columns=12,
        nominal_capacity_ul=1000.0,
        max_working_volume_ul=DEFAULT_MAX_DESTINATION_VOLUME_UL,
        closure_type="septum_or_rubber_top",
    )


def matrix_96_1ml_septum_type() -> ContainerType:
    return matrix_96_1ml_rubber_septum_type()
