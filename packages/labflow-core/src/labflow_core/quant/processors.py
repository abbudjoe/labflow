"""Quantification batch processor and output writers."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from labflow_core.domain.exceptions import ExceptionRecord
from labflow_core.domain.statuses import (
    AncestryEventType,
    ExceptionCode,
    ExceptionSeverity,
    Status,
    WorkflowType,
)
from labflow_core.domain.wells import WellCoordinate, all_plate_wells
from labflow_core.lims.ancestry import ANCESTRY_COLUMNS, AncestryRecord
from labflow_core.lims.manifests import write_csv_rows, write_exception_report
from labflow_core.quant.standards import StandardCurve, fit_linear_standard_curve
from labflow_core.quant.varioskan import VarioskanSchemaMapping, parse_varioskan_tsv

QUANT_RESULT_COLUMNS = [
    "batch_id",
    "plate_id",
    "well",
    "sample_id",
    "raw_reading",
    "blank_reading",
    "blank_corrected_reading",
    "assay_well_concentration_ng_per_ul",
    "dilution_factor",
    "stock_concentration_ng_per_ul",
    "status",
]

STOCK_MANIFEST_COLUMNS = [
    "batch_id",
    "sample_id",
    "source_container_id",
    "plate_id",
    "well",
    "stock_concentration_ng_per_ul",
    "source_assay",
    "standard_curve_context",
]

SAMPLE_PLATE_SAMPLE_COUNT = 95


class SamplePlateConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    plate_id: str = Field(min_length=1)
    source_container_id: str = Field(min_length=1)
    tsv: Path
    blank_well: WellCoordinate
    dilution_factor: float = Field(gt=0)

    @field_validator("blank_well", mode="before")
    @classmethod
    def parse_blank_well(cls, value: Any) -> Any:
        return WellCoordinate.model_validate(value)


class QuantificationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    batch_id: str = Field(min_length=1)
    workflow_type: WorkflowType = WorkflowType.DNA_QUANT
    assay: str
    instrument: str = "Varioskan"
    standards_tsv: Path
    sample_plates: tuple[SamplePlateConfig, ...]
    standard_concentrations_ng_per_ul: dict[str, float]
    schema_mapping: VarioskanSchemaMapping = Field(default_factory=VarioskanSchemaMapping)


@dataclass(frozen=True)
class QuantResultRow:
    batch_id: str
    plate_id: str
    well: WellCoordinate
    sample_id: str
    raw_reading: float
    blank_reading: float
    blank_corrected_reading: float
    assay_well_concentration_ng_per_ul: float
    dilution_factor: float
    stock_concentration_ng_per_ul: float
    status: Status

    def to_csv_row(self) -> dict[str, str]:
        return {
            "batch_id": self.batch_id,
            "plate_id": self.plate_id,
            "well": str(self.well),
            "sample_id": self.sample_id,
            "raw_reading": _fmt4(self.raw_reading),
            "blank_reading": _fmt4(self.blank_reading),
            "blank_corrected_reading": _fmt4(self.blank_corrected_reading),
            "assay_well_concentration_ng_per_ul": _fmt4(
                self.assay_well_concentration_ng_per_ul
            ),
            "dilution_factor": _fmt4(self.dilution_factor),
            "stock_concentration_ng_per_ul": _fmt4(self.stock_concentration_ng_per_ul),
            "status": self.status.value,
        }


@dataclass(frozen=True)
class QuantificationResult:
    rows: tuple[QuantResultRow, ...]
    standard_curve: StandardCurve | None
    exceptions: tuple[ExceptionRecord, ...]
    ancestry_records: tuple[AncestryRecord, ...]


def process_quantification(config: QuantificationConfig) -> QuantificationResult:
    standards = parse_varioskan_tsv(config.standards_tsv, config.schema_mapping)
    fit = fit_linear_standard_curve(
        standards,
        config.standard_concentrations_ng_per_ul,
        batch_id=config.batch_id,
    )
    if fit.curve is None:
        return QuantificationResult(
            rows=(),
            standard_curve=None,
            exceptions=fit.exceptions,
            ancestry_records=(),
        )

    rows: list[QuantResultRow] = []
    exceptions: list[ExceptionRecord] = list(fit.exceptions)
    ancestry: list[AncestryRecord] = []

    for plate in config.sample_plates:
        readings = parse_varioskan_tsv(plate.tsv, config.schema_mapping)
        readings_by_well = {str(reading.well): reading for reading in readings}
        blank = readings_by_well.get(str(plate.blank_well))
        if blank is None:
            exceptions.append(
                ExceptionRecord(
                    exception_code=ExceptionCode.MISSING_PLATE_BLANK,
                    severity=ExceptionSeverity.BLOCKING,
                    batch_id=config.batch_id,
                    source_well=plate.blank_well,
                    message=f"Plate {plate.plate_id} is missing blank well {plate.blank_well}.",
                    suggested_action="Provide a sample-plate blank reading before quantification.",
                    blocks_robot_transfer=True,
                )
            )
            continue

        sample_readings = [
            reading
            for reading in readings
            if reading.well != plate.blank_well and reading.sample_id
        ]
        sample_wells = [reading.well for reading in sample_readings]
        expected_sample_wells = set(all_plate_wells()) - {plate.blank_well}
        sample_well_counts = Counter(sample_wells)
        duplicate_wells = sorted(
            (well for well, count in sample_well_counts.items() if count > 1),
            key=lambda well: well.sort_key,
        )
        missing_wells = sorted(
            expected_sample_wells - set(sample_wells),
            key=lambda well: well.sort_key,
        )
        extra_wells = sorted(
            set(sample_wells) - expected_sample_wells,
            key=lambda well: well.sort_key,
        )
        if (
            len(sample_readings) != SAMPLE_PLATE_SAMPLE_COUNT
            or duplicate_wells
            or missing_wells
            or extra_wells
        ):
            exceptions.append(
                ExceptionRecord(
                    exception_code=ExceptionCode.INVALID_SAMPLE_PLATE_LAYOUT,
                    severity=ExceptionSeverity.BLOCKING,
                    batch_id=config.batch_id,
                    source_well=plate.blank_well,
                    message=(
                        f"Plate {plate.plate_id} must contain "
                        f"{SAMPLE_PLATE_SAMPLE_COUNT} sample readings plus one blank. "
                        f"Missing wells: {_format_wells(missing_wells)}. "
                        f"Duplicate wells: {_format_wells(duplicate_wells)}. "
                        f"Unexpected wells: {_format_wells(extra_wells)}."
                    ),
                    suggested_action=(
                        "Provide a complete 96-well sample plate with 95 samples "
                        "and the configured blank well."
                    ),
                    blocks_robot_transfer=True,
                )
            )
            continue

        for reading in sample_readings:
            sample_id = reading.sample_id
            if sample_id is None:
                continue
            blank_corrected = reading.reading - blank.reading
            assay_concentration = fit.curve.concentration_for_corrected_reading(blank_corrected)
            stock_concentration = assay_concentration * plate.dilution_factor
            status = Status.VALID
            if not fit.curve.is_reading_in_range(blank_corrected):
                status = Status.OUT_OF_RANGE
                exceptions.append(
                    ExceptionRecord(
                        exception_code=ExceptionCode.QC_STATUS_FAILED,
                        severity=ExceptionSeverity.WARNING,
                        batch_id=config.batch_id,
                        sample_id=sample_id,
                        source_well=reading.well,
                        message=(
                            f"Blank-corrected reading {blank_corrected:.4f} is outside "
                            "the standard curve range."
                        ),
                        suggested_action="Dilute and rerun quantification for this sample.",
                        blocks_robot_transfer=True,
                    )
                )
            rows.append(
                QuantResultRow(
                    batch_id=config.batch_id,
                    plate_id=plate.plate_id,
                    well=reading.well,
                    sample_id=sample_id,
                    raw_reading=reading.reading,
                    blank_reading=blank.reading,
                    blank_corrected_reading=blank_corrected,
                    assay_well_concentration_ng_per_ul=assay_concentration,
                    dilution_factor=plate.dilution_factor,
                    stock_concentration_ng_per_ul=stock_concentration,
                    status=status,
                )
            )
            ancestry.append(
                AncestryRecord(
                    child_sample_id=sample_id,
                    event_type=AncestryEventType.QUANTIFIED,
                    source_container_id=plate.source_container_id,
                    source_well=reading.well,
                    batch_id=config.batch_id,
                    workflow_type=config.workflow_type,
                    metadata_json=json.dumps(
                        {
                            "assay": config.assay,
                            "instrument": config.instrument,
                            "plate_id": plate.plate_id,
                            "dilution_factor": plate.dilution_factor,
                        },
                        sort_keys=True,
                    ),
                )
            )
    return QuantificationResult(
        rows=tuple(sorted(rows, key=lambda row: (row.plate_id, row.well.sort_key, row.sample_id))),
        standard_curve=fit.curve,
        exceptions=tuple(exceptions),
        ancestry_records=tuple(ancestry),
    )


def write_quantification_outputs(result: QuantificationResult, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv_rows(
        out_dir / "quant_results.csv",
        QUANT_RESULT_COLUMNS,
        [row.to_csv_row() for row in result.rows],
    )
    write_exception_report(out_dir / "quant_exception_report.csv", result.exceptions)
    write_csv_rows(
        out_dir / "lims_stock_concentration_manifest.csv",
        STOCK_MANIFEST_COLUMNS,
        [
            {
                "batch_id": row.batch_id,
                "sample_id": row.sample_id,
                "source_container_id": next(
                    (
                        record.source_container_id
                        for record in result.ancestry_records
                        if record.child_sample_id == row.sample_id
                    ),
                    "",
                )
                or "",
                "plate_id": row.plate_id,
                "well": str(row.well),
                "stock_concentration_ng_per_ul": _fmt4(row.stock_concentration_ng_per_ul),
                "source_assay": "Quant-iT PicoGreen",
                "standard_curve_context": "batch_level_separate_standards_plate",
            }
            for row in result.rows
            if row.status is Status.VALID
        ],
    )
    write_csv_rows(
        out_dir / "sample_ancestry.csv",
        ANCESTRY_COLUMNS,
        [record.to_row() for record in result.ancestry_records],
    )
    summary = result.standard_curve.to_summary() if result.standard_curve else {}
    (out_dir / "standard_curve_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )


def _fmt4(value: float) -> str:
    return f"{value:.4f}"


def _format_wells(wells: list[WellCoordinate]) -> str:
    if not wells:
        return "none"
    return ", ".join(str(well) for well in wells)
