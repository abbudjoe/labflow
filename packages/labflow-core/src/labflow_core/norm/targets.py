"""Normalization target canonicalization."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NormalizationTarget(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    target_concentration_ng_per_ul: float | None = Field(default=None, gt=0)
    target_final_volume_ul: float = Field(gt=0)
    target_mass_ng: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def exactly_one_target_mode(self) -> NormalizationTarget:
        has_concentration = self.target_concentration_ng_per_ul is not None
        has_mass = self.target_mass_ng is not None
        if has_concentration == has_mass:
            msg = (
                "Provide exactly one supported target mode: "
                "target_concentration_ng_per_ul or target_mass_ng."
            )
            raise ValueError(msg)
        return self

    @property
    def concentration_ng_per_ul(self) -> float:
        if self.target_concentration_ng_per_ul is not None:
            return self.target_concentration_ng_per_ul
        if self.target_mass_ng is None:
            msg = "target_mass_ng is required to derive concentration."
            raise ValueError(msg)
        return self.target_mass_ng / self.target_final_volume_ul

    @property
    def mass_ng(self) -> float:
        if self.target_mass_ng is not None:
            return self.target_mass_ng
        if self.target_concentration_ng_per_ul is None:
            msg = "target_concentration_ng_per_ul is required to derive mass."
            raise ValueError(msg)
        return self.target_concentration_ng_per_ul * self.target_final_volume_ul

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> NormalizationTarget:
        unsupported = {"nM", "nm", "fmol", "pmol", "molarity", "molecular_weight"}
        if unsupported.intersection(config):
            msg = "Molar and molecule-size target modes are excluded from v0.1."
            raise ValueError(msg)
        return cls(
            target_concentration_ng_per_ul=_optional_float(
                config.get("target_concentration_ng_per_ul")
            ),
            target_final_volume_ul=float(config["target_final_volume_ul"]),
            target_mass_ng=_optional_float(config.get("target_mass_ng")),
        )


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
