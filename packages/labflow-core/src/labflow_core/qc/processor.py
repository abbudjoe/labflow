"""CSV parsing and deterministic threshold evaluation for synthetic NGS QC."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from labflow_core.domain.statuses import ExceptionCode
from labflow_core.lims.manifests import read_csv_rows
from labflow_core.qc.models import NgsQcResult, QcEvaluation, QcStatus, QcThresholds


def parse_ngs_qc_csv(path: Path) -> tuple[NgsQcResult, ...]:
    """Parse synthetic downstream QC summary rows.

    This parser intentionally handles only summary metrics. It does not parse
    FASTQ, alignments, variant calls, or clinical QC artifacts.
    """

    parsed: list[NgsQcResult] = []
    for row_number, row in enumerate(read_csv_rows(path), start=2):
        parsed.append(
            NgsQcResult(
                sample_id=_required_cell(row, "sample_id", row_number),
                qc_batch_id=_required_cell(row, "qc_batch_id", row_number),
                analysis_id=_required_cell(row, "analysis_id", row_number),
                read_count=_optional_int(row.get("read_count"), "read_count", row_number),
                q30_percent=_optional_float(row.get("q30_percent"), "q30_percent", row_number),
            )
        )
    return tuple(parsed)


def evaluate_qc_results(
    results: tuple[NgsQcResult, ...],
    thresholds: QcThresholds | None = None,
) -> tuple[QcEvaluation, ...]:
    """Evaluate simple configured downstream QC thresholds."""

    active_thresholds = thresholds or QcThresholds()
    return tuple(_evaluate_one(result, active_thresholds) for result in results)


def _evaluate_one(result: NgsQcResult, thresholds: QcThresholds) -> QcEvaluation:
    codes: list[ExceptionCode] = []
    status = QcStatus.PASS

    if result.read_count is None or result.q30_percent is None:
        codes.extend(
            (
                ExceptionCode.MISSING_QC_RESULT,
                ExceptionCode.DOWNSTREAM_QC_REVIEW_REQUIRED,
            )
        )
        status = QcStatus.MISSING
    elif (
        result.read_count < thresholds.min_read_count
        or result.q30_percent < thresholds.min_q30_percent
    ):
        codes.extend(
            (
                ExceptionCode.QC_RESULT_FAILED,
                ExceptionCode.DOWNSTREAM_QC_REVIEW_REQUIRED,
            )
        )
        status = QcStatus.FAIL

    return QcEvaluation(
        result=result,
        thresholds=thresholds,
        status=status,
        exception_codes=tuple(dict.fromkeys(codes)),
    )


def thresholds_from_config(raw: Mapping[str, Any] | None) -> QcThresholds:
    """Parse optional threshold mapping from tool arguments."""

    if raw is None:
        return QcThresholds()
    return QcThresholds.model_validate(dict(raw))


def _required_cell(row: Mapping[str, str], field_name: str, row_number: int) -> str:
    value = (row.get(field_name) or "").strip()
    if not value:
        msg = f"Row {row_number} is missing required field {field_name}."
        raise ValueError(msg)
    return value


def _optional_int(value: str | None, field_name: str, row_number: int) -> int | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        parsed = int(text)
    except ValueError as exc:
        msg = f"Row {row_number} has invalid integer field {field_name}: {text}"
        raise ValueError(msg) from exc
    if parsed < 0:
        msg = f"Row {row_number} field {field_name} must be non-negative."
        raise ValueError(msg)
    return parsed


def _optional_float(value: str | None, field_name: str, row_number: int) -> float | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError as exc:
        msg = f"Row {row_number} has invalid numeric field {field_name}: {text}"
        raise ValueError(msg) from exc
    if parsed < 0:
        msg = f"Row {row_number} field {field_name} must be non-negative."
        raise ValueError(msg)
    return parsed
