"""Batch-level standard curve fitting."""

from __future__ import annotations

from dataclasses import dataclass

from labflow_core.domain.exceptions import ExceptionRecord
from labflow_core.domain.statuses import ExceptionCode, ExceptionSeverity
from labflow_core.domain.wells import WellCoordinate, default_standard_wells, parse_well
from labflow_core.quant.varioskan import VarioskanReading


@dataclass(frozen=True)
class StandardCurve:
    slope: float
    intercept: float
    zero_standard_reading: float
    min_corrected_reading: float
    max_corrected_reading: float
    min_concentration_ng_per_ul: float
    max_concentration_ng_per_ul: float

    def concentration_for_corrected_reading(self, blank_corrected_reading: float) -> float:
        return (blank_corrected_reading - self.intercept) / self.slope

    def is_reading_in_range(self, blank_corrected_reading: float) -> bool:
        return self.min_corrected_reading <= blank_corrected_reading <= self.max_corrected_reading

    def to_summary(self) -> dict[str, float]:
        return {
            "slope": self.slope,
            "intercept": self.intercept,
            "zero_standard_reading": self.zero_standard_reading,
            "min_corrected_reading": self.min_corrected_reading,
            "max_corrected_reading": self.max_corrected_reading,
            "min_concentration_ng_per_ul": self.min_concentration_ng_per_ul,
            "max_concentration_ng_per_ul": self.max_concentration_ng_per_ul,
        }


@dataclass(frozen=True)
class StandardCurveFitResult:
    curve: StandardCurve | None
    exceptions: tuple[ExceptionRecord, ...]


def default_standard_well_labels() -> tuple[str, ...]:
    return tuple(str(well) for well in default_standard_wells())


def fit_linear_standard_curve(
    readings: list[VarioskanReading],
    standard_concentrations_ng_per_ul: dict[str, float],
    *,
    batch_id: str | None = None,
) -> StandardCurveFitResult:
    layout_exception = _validate_standard_concentration_layout(
        standard_concentrations_ng_per_ul,
        batch_id=batch_id,
    )
    if layout_exception is not None:
        return StandardCurveFitResult(curve=None, exceptions=(layout_exception,))

    reading_by_well = {str(reading.well): reading for reading in readings}
    expected_wells = set(standard_concentrations_ng_per_ul)
    missing = sorted(expected_wells - set(reading_by_well), key=lambda well: parse_well(well).sort_key)
    if missing:
        return StandardCurveFitResult(
            curve=None,
            exceptions=(
                ExceptionRecord(
                    exception_code=ExceptionCode.MISSING_BATCH_STANDARD_CURVE,
                    severity=ExceptionSeverity.BLOCKING,
                    batch_id=batch_id,
                    message=f"Missing standard wells: {', '.join(missing)}.",
                    suggested_action="Reprocess the standards plate or update the standard layout.",
                    blocks_robot_transfer=True,
                ),
            ),
        )

    zero_well = _zero_standard_well(standard_concentrations_ng_per_ul)
    zero_reading = reading_by_well[str(zero_well)].reading if zero_well else 0.0
    points = [
        (
            concentration,
            reading_by_well[well].reading - zero_reading,
        )
        for well, concentration in sorted(
            standard_concentrations_ng_per_ul.items(),
            key=lambda item: parse_well(item[0]).sort_key,
        )
    ]
    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    slope, intercept = _linear_regression(x_values, y_values)
    if slope <= 0:
        return StandardCurveFitResult(
            curve=None,
            exceptions=(
                ExceptionRecord(
                    exception_code=ExceptionCode.INVALID_BATCH_STANDARD_CURVE,
                    severity=ExceptionSeverity.BLOCKING,
                    batch_id=batch_id,
                    message="Standard curve slope must be positive.",
                    suggested_action="Review standards plate readings and concentration mapping.",
                    blocks_robot_transfer=True,
                ),
            ),
        )
    return StandardCurveFitResult(
        curve=StandardCurve(
            slope=slope,
            intercept=intercept,
            zero_standard_reading=zero_reading,
            min_corrected_reading=min(y_values),
            max_corrected_reading=max(y_values),
            min_concentration_ng_per_ul=min(x_values),
            max_concentration_ng_per_ul=max(x_values),
        ),
        exceptions=(),
    )


def _validate_standard_concentration_layout(
    standard_concentrations_ng_per_ul: dict[str, float],
    *,
    batch_id: str | None,
) -> ExceptionRecord | None:
    expected = set(default_standard_well_labels())
    configured = set(standard_concentrations_ng_per_ul)
    invalid = sorted(well for well in configured if not _is_valid_well_label(well))
    if invalid:
        return ExceptionRecord(
            exception_code=ExceptionCode.INVALID_BATCH_STANDARD_CURVE,
            severity=ExceptionSeverity.BLOCKING,
            batch_id=batch_id,
            message=(
                "Standard concentration layout contains invalid well labels: "
                f"{', '.join(invalid)}."
            ),
            suggested_action="Use exactly the eight standards in wells A1-H1.",
            blocks_robot_transfer=True,
        )
    missing = sorted(expected - configured, key=lambda well: parse_well(well).sort_key)
    extra = sorted(configured - expected, key=lambda well: parse_well(well).sort_key)
    if missing:
        return ExceptionRecord(
            exception_code=ExceptionCode.MISSING_BATCH_STANDARD_CURVE,
            severity=ExceptionSeverity.BLOCKING,
            batch_id=batch_id,
            message=(
                "Standard concentration layout must define all A1-H1 standards; "
                f"missing: {', '.join(missing)}."
            ),
            suggested_action="Define exactly the eight standards in wells A1-H1.",
            blocks_robot_transfer=True,
        )
    if extra:
        return ExceptionRecord(
            exception_code=ExceptionCode.INVALID_BATCH_STANDARD_CURVE,
            severity=ExceptionSeverity.BLOCKING,
            batch_id=batch_id,
            message=(
                "Standard concentration layout must not include wells outside A1-H1; "
                f"extra: {', '.join(extra)}."
            ),
            suggested_action="Use exactly the eight standards in wells A1-H1.",
            blocks_robot_transfer=True,
        )
    return None


def _is_valid_well_label(well: str) -> bool:
    try:
        parse_well(well)
    except ValueError:
        return False
    return True


def _zero_standard_well(concentrations: dict[str, float]) -> WellCoordinate | None:
    for well, concentration in concentrations.items():
        if concentration == 0:
            return parse_well(well)
    return None


def _linear_regression(x_values: list[float], y_values: list[float]) -> tuple[float, float]:
    if len(x_values) != len(y_values) or len(x_values) < 2:
        msg = "At least two standard points are required."
        raise ValueError(msg)
    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)
    denominator = sum((x - x_mean) ** 2 for x in x_values)
    if denominator == 0:
        msg = "Standard concentrations must not all be identical."
        raise ValueError(msg)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values, strict=True))
    slope = numerator / denominator
    intercept = y_mean - slope * x_mean
    return slope, intercept
