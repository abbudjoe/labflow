"""Typed LabFlow workflow DSL models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from labflow_core.domain.identifiers import (
    optional_nonblank_identifier,
    require_nonblank_identifier,
)
from labflow_core.domain.units import (
    DEFAULT_MAX_DESTINATION_VOLUME_UL,
    MINIMUM_TRANSFER_VOLUME_UL,
    ROBOT_ASPIRATION_SAFETY_MARGIN_UL,
    SOURCE_RESIDUAL_DEAD_VOLUME_UL,
)


class WorkflowKind(StrEnum):
    DNA_QUANT = "dna_quant"
    DNA_NORMALIZATION = "dna_normalization"
    RNA_NORM_REQUANT = "rna_norm_requant"


class WorkflowHeader(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    type: WorkflowKind

    @field_validator("name", "version")
    @classmethod
    def required_identifier(cls, value: str, info: ValidationInfo) -> str:
        return require_nonblank_identifier(value, info.field_name)


class BatchConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    batch_id: str = Field(min_length=1)
    containers_per_batch: int = Field(default=1, gt=0)
    plate_format: int = Field(default=96)
    samples_per_plate: int = Field(default=95, gt=0)
    blank_well: str | None = None

    @field_validator("batch_id")
    @classmethod
    def required_identifier(cls, value: str, info: ValidationInfo) -> str:
        return require_nonblank_identifier(value, info.field_name)

    @field_validator("blank_well", mode="before")
    @classmethod
    def optional_blank_well(cls, value: str | None) -> str | None:
        return optional_nonblank_identifier(value)


class StandardsConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    standards_plate_id: str = Field(min_length=1)
    wells: dict[str, str] = Field(default_factory=dict)
    curve_model: str = "linear"

    @field_validator("standards_plate_id", "curve_model")
    @classmethod
    def required_identifier(cls, value: str, info: ValidationInfo) -> str:
        return require_nonblank_identifier(value, info.field_name)


class ContainerRoleConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    registry_container_type: str = Field(min_length=1)

    @field_validator("registry_container_type")
    @classmethod
    def required_identifier(cls, value: str, info: ValidationInfo) -> str:
        return require_nonblank_identifier(value, info.field_name)


class ContainersConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: ContainerRoleConfig
    destination: ContainerRoleConfig | None = None


class NormalizationConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    target_concentration_ng_per_ul: float | None = Field(default=None, gt=0)
    target_final_volume_ul: float | None = Field(default=None, gt=0)
    target_mass_ng: float | None = Field(default=None, gt=0)
    minimum_transfer_volume_ul: float = Field(default=MINIMUM_TRANSFER_VOLUME_UL, gt=0)
    source_residual_dead_volume_ul: float = Field(default=SOURCE_RESIDUAL_DEAD_VOLUME_UL, ge=0)
    robot_aspiration_safety_margin_ul: float = Field(
        default=ROBOT_ASPIRATION_SAFETY_MARGIN_UL,
        ge=0,
    )
    max_destination_volume_ul: float = Field(default=DEFAULT_MAX_DESTINATION_VOLUME_UL, gt=0)
    n_m: float | None = Field(default=None, alias="nM", gt=0)
    fmol: float | None = Field(default=None, gt=0)
    pmol: float | None = Field(default=None, gt=0)
    molarity: float | None = Field(default=None, gt=0)

    @property
    def unsupported_molar_fields(self) -> tuple[str, ...]:
        fields: list[str] = []
        if self.n_m is not None:
            fields.append("nM")
        if self.fmol is not None:
            fields.append("fmol")
        if self.pmol is not None:
            fields.append("pmol")
        if self.molarity is not None:
            fields.append("molarity")
        return tuple(fields)


class RequantConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    assay: str = Field(min_length=1)
    result_handling: str = Field(min_length=1)

    @field_validator("assay", "result_handling")
    @classmethod
    def required_identifier(cls, value: str, info: ValidationInfo) -> str:
        return require_nonblank_identifier(value, info.field_name)


class SampleConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sample_id: str = Field(min_length=1)
    source_container_id: str = Field(min_length=1)
    source_well: str = Field(min_length=1)
    stock_concentration_ng_per_ul: float | None = Field(default=None, gt=0)
    available_volume_ul: float | None = Field(default=None, gt=0)
    destination_container_id: str | None = None
    destination_well: str | None = None

    @field_validator("sample_id", "source_container_id", "source_well")
    @classmethod
    def required_identifier(cls, value: str, info: ValidationInfo) -> str:
        return require_nonblank_identifier(value, info.field_name)

    @field_validator("destination_container_id", "destination_well", mode="before")
    @classmethod
    def optional_identifier(cls, value: str | None) -> str | None:
        return optional_nonblank_identifier(value)


class OutputsConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    janus: bool = False


class LabFlowWorkflow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workflow: WorkflowHeader
    batch: BatchConfig
    standards: StandardsConfig | None = None
    containers: ContainersConfig
    normalization: NormalizationConfig | None = None
    requant: RequantConfig | None = None
    samples: tuple[SampleConfig, ...] = ()
    outputs: OutputsConfig = Field(default_factory=OutputsConfig)
