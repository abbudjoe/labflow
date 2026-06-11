"""JANUS-style CSV worklist export."""

from __future__ import annotations

from pathlib import Path

from labflow_core.domain.statuses import NormalizationMode
from labflow_core.lims.manifests import write_csv_rows
from labflow_core.norm.planner import NormalizationPlanRow
from labflow_core.robots.protocol_ir import PROTOCOL_IR_COLUMNS, build_protocol_ir

JANUS_MINIMAL_COLUMNS = ["well", "diluent_volume_ul", "sample_volume_ul"]
JANUS_AUDIT_COLUMNS = [
    "batch_id",
    "sample_id",
    "normalization_mode",
    "source_container_id",
    "source_well",
    "destination_container_id",
    "destination_well",
    "diluent_volume_ul",
    "sample_volume_ul",
    "status",
]


def janus_minimal_rows(rows: list[NormalizationPlanRow]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        if not row.generates_robot_transfer:
            continue
        target_well = (
            row.source_well
            if row.normalization_mode is NormalizationMode.IN_PLACE
            else row.destination_well
        )
        if target_well is None:
            continue
        output.append(
            {
                "well": str(target_well),
                "diluent_volume_ul": f"{row.diluent_volume_ul:.2f}",
                "sample_volume_ul": f"{row.sample_transfer_volume_ul:.2f}",
            }
        )
    return output


def janus_audit_rows(rows: list[NormalizationPlanRow]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        if not row.generates_robot_transfer:
            continue
        destination_container_id = (
            row.source_container_id
            if row.normalization_mode is NormalizationMode.IN_PLACE
            else row.destination_container_id or ""
        )
        destination_well = (
            str(row.source_well)
            if row.normalization_mode is NormalizationMode.IN_PLACE
            else str(row.destination_well) if row.destination_well else ""
        )
        output.append(
            {
                "batch_id": row.batch_id,
                "sample_id": row.sample_id,
                "normalization_mode": row.normalization_mode.value,
                "source_container_id": row.source_container_id,
                "source_well": str(row.source_well),
                "destination_container_id": destination_container_id,
                "destination_well": destination_well,
                "diluent_volume_ul": f"{row.diluent_volume_ul:.2f}",
                "sample_volume_ul": f"{row.sample_transfer_volume_ul:.2f}",
                "status": row.status.value,
            }
        )
    return output


def write_janus_outputs(rows: list[NormalizationPlanRow], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv_rows(
        out_dir / "janus_worklist.csv",
        JANUS_MINIMAL_COLUMNS,
        janus_minimal_rows(rows),
    )
    write_csv_rows(
        out_dir / "janus_audit_worklist.csv",
        JANUS_AUDIT_COLUMNS,
        janus_audit_rows(rows),
    )
    protocol_steps = build_protocol_ir(rows)
    write_csv_rows(
        out_dir / "protocol_ir.csv",
        PROTOCOL_IR_COLUMNS,
        [step.to_csv_row() for step in protocol_steps],
    )
