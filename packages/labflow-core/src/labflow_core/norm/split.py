"""Split workflow calculations."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SplitConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    split_source_transfer_volume_ul: float = Field(default=1.0, ge=1.0)
    split_final_volume_ul: float = Field(default=50.0, gt=0)

    @model_validator(mode="after")
    def validate_split_contract(self) -> SplitConfig:
        if self.split_source_transfer_volume_ul != 1.0:
            msg = "Split workflow must use exactly 1 uL source transfer in v0.1."
            raise ValueError(msg)
        if self.split_final_volume_ul <= self.split_source_transfer_volume_ul:
            msg = "split_final_volume_ul must exceed split_source_transfer_volume_ul."
            raise ValueError(msg)
        return self

    @property
    def split_diluent_volume_ul(self) -> float:
        return self.split_final_volume_ul - self.split_source_transfer_volume_ul

    def expected_child_concentration_ng_per_ul(
        self,
        source_concentration_ng_per_ul: float,
    ) -> float:
        return (
            source_concentration_ng_per_ul
            * self.split_source_transfer_volume_ul
            / self.split_final_volume_ul
        )
