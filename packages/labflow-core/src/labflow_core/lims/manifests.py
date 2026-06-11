"""Manifest validation and deterministic CSV helpers."""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from labflow_core.domain.exceptions import EXCEPTION_REPORT_COLUMNS, ExceptionRecord
from labflow_core.domain.samples import NormalizationSampleInput
from labflow_core.domain.statuses import ExceptionCode, ExceptionSeverity, NormalizationMode


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv_rows(path: Path, fieldnames: list[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_exception_report(path: Path, exceptions: Iterable[ExceptionRecord]) -> None:
    write_csv_rows(path, EXCEPTION_REPORT_COLUMNS, [exc.to_report_row() for exc in exceptions])


def validate_duplicate_manifest_rows(
    rows: Iterable[NormalizationSampleInput],
    *,
    batch_id: str,
) -> list[ExceptionRecord]:
    materialized_rows = list(rows)
    exceptions: list[ExceptionRecord] = []
    sample_counts = Counter(row.sample_id for row in materialized_rows)
    source_counts = Counter((row.source_container_id, row.source_well) for row in materialized_rows)
    destination_counts = Counter(
        (row.destination_container_id, row.destination_well)
        for row in materialized_rows
        if row.destination_container_id and row.destination_well
    )

    for row in materialized_rows:
        if sample_counts[row.sample_id] > 1:
            exceptions.append(
                ExceptionRecord(
                    exception_code=ExceptionCode.DUPLICATE_SAMPLE_ID,
                    severity=ExceptionSeverity.BLOCKING,
                    batch_id=batch_id,
                    sample_id=row.sample_id,
                    source_container_id=row.source_container_id,
                    source_well=row.source_well,
                    message=f"Duplicate sample ID {row.sample_id} in batch.",
                    suggested_action="Resolve sample identity before planning transfers.",
                    blocks_robot_transfer=True,
                )
            )

        source_key = (row.source_container_id, row.source_well)
        if source_counts[source_key] > 1:
            exceptions.append(
                ExceptionRecord(
                    exception_code=ExceptionCode.DUPLICATE_SOURCE_LOCATION,
                    severity=ExceptionSeverity.BLOCKING,
                    batch_id=batch_id,
                    sample_id=row.sample_id,
                    source_container_id=row.source_container_id,
                    source_well=row.source_well,
                    message=f"Duplicate source location {row.source_container_id}:{row.source_well}.",
                    suggested_action="Assign each source well to at most one sample.",
                    blocks_robot_transfer=True,
                )
            )

        if row.destination_container_id and row.destination_well:
            destination_key = (row.destination_container_id, row.destination_well)
            if destination_counts[destination_key] > 1:
                exceptions.append(
                    ExceptionRecord(
                        exception_code=ExceptionCode.DUPLICATE_DESTINATION_LOCATION,
                        severity=ExceptionSeverity.BLOCKING,
                        batch_id=batch_id,
                        sample_id=row.sample_id,
                        source_container_id=row.source_container_id,
                        source_well=row.source_well,
                        destination_container_id=row.destination_container_id,
                        destination_well=row.destination_well,
                        message=(
                            "Duplicate destination location "
                            f"{row.destination_container_id}:{row.destination_well}."
                        ),
                        suggested_action="Assign each destination well to at most one transfer.",
                        blocks_robot_transfer=True,
                    )
                )

    return exceptions


def validate_mode_location_contract(
    row: NormalizationSampleInput,
    mode: NormalizationMode,
) -> ExceptionRecord | None:
    if mode is NormalizationMode.STANDARD_NEW_CONTAINER:
        if not row.destination_container_id or row.destination_well is None:
            return ExceptionRecord(
                exception_code=ExceptionCode.MISSING_DESTINATION_LOCATION,
                severity=ExceptionSeverity.BLOCKING,
                sample_id=row.sample_id,
                source_container_id=row.source_container_id,
                source_well=row.source_well,
                message="Standard normalization requires a destination container and well.",
                suggested_action="Assign a destination location or choose in-place mode.",
                blocks_robot_transfer=True,
            )
    if mode is NormalizationMode.IN_PLACE:
        if row.destination_container_id or row.destination_well is not None:
            return ExceptionRecord(
                exception_code=ExceptionCode.DESTINATION_SUPPLIED_FOR_IN_PLACE,
                severity=ExceptionSeverity.BLOCKING,
                sample_id=row.sample_id,
                source_container_id=row.source_container_id,
                source_well=row.source_well,
                destination_container_id=row.destination_container_id,
                destination_well=row.destination_well,
                message="In-place normalization must not provide a destination location.",
                suggested_action="Remove destination fields for in-place mode.",
                blocks_robot_transfer=True,
            )
    return None
