"""Robot-agnostic protocol intermediate representation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from labflow_core.domain.statuses import NormalizationMode
from labflow_core.domain.wells import WellCoordinate
from labflow_core.norm.planner import NormalizationPlanRow


class ProtocolStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    batch_id: str
    step_number: int
    operation_type: str
    liquid_type: str
    sample_id: str
    source_container_id: str | None
    source_well: WellCoordinate | None
    destination_container_id: str
    destination_well: WellCoordinate
    volume_ul: float
    tip_policy: str
    mix_after: bool
    normalization_mode: NormalizationMode

    def to_csv_row(self) -> dict[str, str]:
        return {
            "batch_id": self.batch_id,
            "step_number": str(self.step_number),
            "operation_type": self.operation_type,
            "liquid_type": self.liquid_type,
            "sample_id": self.sample_id,
            "source_container_id": self.source_container_id or "",
            "source_well": str(self.source_well) if self.source_well else "",
            "destination_container_id": self.destination_container_id,
            "destination_well": str(self.destination_well),
            "volume_ul": f"{self.volume_ul:.2f}",
            "tip_policy": self.tip_policy,
            "mix_after": str(self.mix_after),
            "normalization_mode": self.normalization_mode.value,
        }


PROTOCOL_IR_COLUMNS = [
    "batch_id",
    "step_number",
    "operation_type",
    "liquid_type",
    "sample_id",
    "source_container_id",
    "source_well",
    "destination_container_id",
    "destination_well",
    "volume_ul",
    "tip_policy",
    "mix_after",
    "normalization_mode",
]


def build_protocol_ir(rows: list[NormalizationPlanRow]) -> list[ProtocolStep]:
    steps: list[ProtocolStep] = []
    step_number = 1
    for row in rows:
        if not row.generates_robot_transfer:
            continue
        if row.normalization_mode is NormalizationMode.IN_PLACE:
            steps.append(
                ProtocolStep(
                    batch_id=row.batch_id,
                    step_number=step_number,
                    operation_type="ADD_DILUENT",
                    liquid_type="diluent",
                    sample_id=row.sample_id,
                    source_container_id=None,
                    source_well=None,
                    destination_container_id=row.source_container_id,
                    destination_well=row.source_well,
                    volume_ul=row.diluent_volume_ul,
                    tip_policy="reuse_diluent_tip_allowed",
                    mix_after=False,
                    normalization_mode=row.normalization_mode,
                )
            )
            step_number += 1
            continue
        if row.destination_container_id is None or row.destination_well is None:
            continue
        steps.append(
            ProtocolStep(
                batch_id=row.batch_id,
                step_number=step_number,
                operation_type="ADD_DILUENT",
                liquid_type="diluent",
                sample_id=row.sample_id,
                source_container_id=None,
                source_well=None,
                destination_container_id=row.destination_container_id,
                destination_well=row.destination_well,
                volume_ul=row.diluent_volume_ul,
                tip_policy="reuse_diluent_tip_allowed",
                mix_after=False,
                normalization_mode=row.normalization_mode,
            )
        )
        step_number += 1
        operation_type = (
            "SPLIT_TRANSFER"
            if row.normalization_mode is NormalizationMode.SPLIT_REQUIRED
            else "ADD_SAMPLE"
        )
        steps.append(
            ProtocolStep(
                batch_id=row.batch_id,
                step_number=step_number,
                operation_type=operation_type,
                liquid_type="sample",
                sample_id=row.sample_id,
                source_container_id=row.source_container_id,
                source_well=row.source_well,
                destination_container_id=row.destination_container_id,
                destination_well=row.destination_well,
                volume_ul=row.sample_transfer_volume_ul,
                tip_policy="discard_sample_tip_after_each_sample",
                mix_after=row.normalization_mode is NormalizationMode.STANDARD_NEW_CONTAINER,
                normalization_mode=row.normalization_mode,
            )
        )
        step_number += 1
        if row.normalization_mode is NormalizationMode.STANDARD_NEW_CONTAINER:
            steps.append(
                ProtocolStep(
                    batch_id=row.batch_id,
                    step_number=step_number,
                    operation_type="MIX",
                    liquid_type="destination_mixture",
                    sample_id=row.sample_id,
                    source_container_id=None,
                    source_well=None,
                    destination_container_id=row.destination_container_id,
                    destination_well=row.destination_well,
                    volume_ul=0.0,
                    tip_policy="use_destination_mix_policy",
                    mix_after=True,
                    normalization_mode=row.normalization_mode,
                )
            )
            step_number += 1
    return steps
