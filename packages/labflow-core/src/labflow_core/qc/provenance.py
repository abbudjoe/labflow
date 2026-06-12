"""Deterministic linkage from downstream QC summaries to LabFlow lineage."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from labflow_core.domain.statuses import ExceptionCode
from labflow_core.lims.manifests import read_csv_rows
from labflow_core.qc.models import (
    NgsQcResult,
    QcEvaluation,
    QcProvenanceRecord,
    QcProvenanceReport,
    QcProvenanceStatus,
    QcStatus,
    QcThresholds,
    UpstreamLineageRecord,
)
from labflow_core.qc.processor import evaluate_qc_results


def read_lineage_manifest(path: Path) -> tuple[UpstreamLineageRecord, ...]:
    """Read a synthetic sample lineage manifest."""

    return tuple(
        UpstreamLineageRecord(
            sample_id=(row.get("sample_id") or "").strip(),
            lab_batch_id=(row.get("lab_batch_id") or "").strip(),
            quant_batch_id=(row.get("quant_batch_id") or "").strip() or None,
            normalization_batch_id=(row.get("normalization_batch_id") or "").strip() or None,
            requant_batch_id=(row.get("requant_batch_id") or "").strip() or None,
            upstream_workflow_valid=_parse_bool(row.get("upstream_workflow_valid"), default=True),
            has_ancestry=_parse_bool(row.get("has_ancestry"), default=True),
        )
        for row in read_csv_rows(path)
    )


def validate_qc_provenance_records(
    qc_results: tuple[NgsQcResult, ...],
    lineage_records: tuple[UpstreamLineageRecord, ...],
    thresholds: QcThresholds | None = None,
) -> QcProvenanceReport:
    """Link downstream QC rows to upstream sample lineage."""

    active_thresholds = thresholds or QcThresholds()
    duplicate_qc_sample_ids = _duplicate_sample_ids(result.sample_id for result in qc_results)
    duplicate_lineage_sample_ids = _duplicate_sample_ids(
        record.sample_id for record in lineage_records
    )
    lineage_by_sample: dict[str, UpstreamLineageRecord] = {}
    for record in lineage_records:
        lineage_by_sample.setdefault(record.sample_id, record)
    evaluations = evaluate_qc_results(qc_results, active_thresholds)
    records = [
        _record_for_evaluation(
            evaluation,
            lineage_by_sample.get(evaluation.result.sample_id),
            duplicate_qc_sample=evaluation.result.sample_id in duplicate_qc_sample_ids,
            duplicate_lineage_sample=evaluation.result.sample_id in duplicate_lineage_sample_ids,
        )
        for evaluation in evaluations
    ]

    qc_sample_ids = {result.sample_id for result in qc_results}
    for lineage in sorted(lineage_records, key=lambda record: record.sample_id):
        if lineage.sample_id in qc_sample_ids:
            continue
        records.append(
            _missing_qc_record(
                lineage,
                active_thresholds,
                duplicate_lineage_sample=lineage.sample_id in duplicate_lineage_sample_ids,
            )
        )

    return QcProvenanceReport(
        thresholds=active_thresholds,
        records=tuple(sorted(records, key=lambda record: record.sample_id)),
    )


def _record_for_evaluation(
    evaluation: QcEvaluation,
    lineage: UpstreamLineageRecord | None,
    *,
    duplicate_qc_sample: bool,
    duplicate_lineage_sample: bool,
) -> QcProvenanceRecord:
    codes = list(evaluation.exception_codes)
    provenance_status = QcProvenanceStatus.LINKED
    duplicate_messages: list[str] = []

    if duplicate_qc_sample:
        codes.extend(
            (
                ExceptionCode.DUPLICATE_SAMPLE_ID,
                ExceptionCode.DOWNSTREAM_QC_REVIEW_REQUIRED,
            )
        )
        duplicate_messages.append("multiple downstream QC rows share this sample ID")
    if duplicate_lineage_sample:
        codes.extend(
            (
                ExceptionCode.DUPLICATE_SAMPLE_ID,
                ExceptionCode.DOWNSTREAM_QC_REVIEW_REQUIRED,
            )
        )
        duplicate_messages.append("multiple upstream lineage rows share this sample ID")

    if lineage is None:
        codes.extend(
            (
                ExceptionCode.UNMATCHED_QC_SAMPLE_ID,
                ExceptionCode.DOWNSTREAM_QC_REVIEW_REQUIRED,
            )
        )
        provenance_status = QcProvenanceStatus.UNMATCHED_QC_SAMPLE_ID
        interpretation = (
            "QC result cannot be linked to a known LabFlow sample ID; manual review is required."
        )
    elif not lineage.has_required_ancestry or not lineage.upstream_workflow_valid:
        codes.extend(
            (
                ExceptionCode.QC_PROVENANCE_GAP,
                ExceptionCode.DOWNSTREAM_QC_REVIEW_REQUIRED,
            )
        )
        provenance_status = QcProvenanceStatus.QC_PROVENANCE_GAP
        if not lineage.upstream_workflow_valid:
            interpretation = (
                "Downstream QC cannot retroactively validate an invalid upstream lab workflow."
            )
        else:
            interpretation = (
                "QC result is linked by sample ID but upstream quantification, normalization, "
                "or re-quantification ancestry is incomplete."
            )
    elif evaluation.status is QcStatus.PASS:
        interpretation = (
            "QC metrics pass configured synthetic thresholds and sample lineage is linked; "
            "this does not imply clinical, production, or causal lab conclusions."
        )
    else:
        provenance_status = QcProvenanceStatus.DOWNSTREAM_QC_REVIEW_REQUIRED
        interpretation = (
            "Downstream QC metrics failed configured thresholds; LabFlow cannot infer a lab "
            "root cause from QC metrics alone."
        )

    if duplicate_messages:
        if provenance_status is QcProvenanceStatus.LINKED:
            provenance_status = QcProvenanceStatus.DOWNSTREAM_QC_REVIEW_REQUIRED
        interpretation = (
            "Duplicate sample identity evidence detected: "
            + "; ".join(duplicate_messages)
            + ". Provenance is ambiguous and manual review is required. "
            + interpretation
        )

    deduped_codes = tuple(dict.fromkeys(codes))
    return QcProvenanceRecord(
        sample_id=evaluation.result.sample_id,
        qc_result=evaluation.result,
        lineage=lineage,
        qc_status=evaluation.status,
        provenance_status=provenance_status,
        exception_codes=deduped_codes,
        manual_review_required=bool(deduped_codes),
        safe_interpretation=interpretation,
    )


def _missing_qc_record(
    lineage: UpstreamLineageRecord,
    thresholds: QcThresholds,
    *,
    duplicate_lineage_sample: bool = False,
) -> QcProvenanceRecord:
    _ = thresholds
    codes: tuple[ExceptionCode, ...] = (
        ExceptionCode.MISSING_QC_RESULT,
        ExceptionCode.DOWNSTREAM_QC_REVIEW_REQUIRED,
    )
    if not lineage.has_required_ancestry or not lineage.upstream_workflow_valid:
        codes = (
            *codes,
            ExceptionCode.QC_PROVENANCE_GAP,
        )
    interpretation = (
        "Expected downstream QC result is missing; manual review is required before "
        "using this sample in analysis summaries."
    )
    if duplicate_lineage_sample:
        codes = (
            *codes,
            ExceptionCode.DUPLICATE_SAMPLE_ID,
        )
        interpretation = (
            "Duplicate upstream lineage rows share this sample ID and the expected "
            "downstream QC result is missing; manual review is required before using "
            "this sample in analysis summaries."
        )
    return QcProvenanceRecord(
        sample_id=lineage.sample_id,
        qc_result=None,
        lineage=lineage,
        qc_status=QcStatus.MISSING,
        provenance_status=QcProvenanceStatus.DOWNSTREAM_QC_REVIEW_REQUIRED,
        exception_codes=tuple(dict.fromkeys(codes)),
        manual_review_required=True,
        safe_interpretation=interpretation,
    )


def _duplicate_sample_ids(sample_ids: Iterable[str]) -> set[str]:
    return {sample_id for sample_id, count in Counter(sample_ids).items() if count > 1}


def _parse_bool(value: str | None, *, default: bool) -> bool:
    text = (value or "").strip().casefold()
    if not text:
        return default
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    msg = f"Invalid boolean value in lineage manifest: {value}"
    raise ValueError(msg)
