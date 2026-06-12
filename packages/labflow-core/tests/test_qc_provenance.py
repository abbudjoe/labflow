from __future__ import annotations

import json
from pathlib import Path

from labflow_core.domain.statuses import ExceptionCode
from labflow_core.qc import (
    NgsQcResult,
    QcProvenanceStatus,
    QcStatus,
    QcThresholds,
    UpstreamLineageRecord,
    parse_ngs_qc_csv,
    read_lineage_manifest,
    validate_qc_provenance_records,
)
from labflow_core.tools import (
    call_tool,
    explain_qc_failure,
    generate_lab_to_analysis_lineage,
    ingest_ngs_qc_results,
    list_tools,
    validate_qc_provenance,
)


QC_CSV = Path("examples/qc/synthetic_ngs_qc_results.csv")
LINEAGE_CSV = Path("examples/qc/synthetic_lab_lineage_manifest.csv")


def test_parse_synthetic_ngs_qc_csv() -> None:
    rows = parse_ngs_qc_csv(QC_CSV)

    assert len(rows) == 7
    passing = next(row for row in rows if row.sample_id == "RNA_DEMO_STD_001")
    assert passing.qc_batch_id == "QC_BATCH_001"
    assert passing.read_count == 2_500_000
    assert passing.q30_percent == 91.2


def test_threshold_evaluation_flags_low_read_count_and_low_q30() -> None:
    report = validate_qc_provenance_records(
        parse_ngs_qc_csv(QC_CSV),
        read_lineage_manifest(LINEAGE_CSV),
        QcThresholds(min_read_count=1_000_000, min_q30_percent=80.0),
    )
    records = {record.sample_id: record for record in report.records}

    assert records["RNA_DEMO_STD_001"].qc_status is QcStatus.PASS
    assert ExceptionCode.QC_RESULT_FAILED in records["RNA_DEMO_LOW_READS_001"].exception_codes
    assert ExceptionCode.QC_RESULT_FAILED in records["RNA_DEMO_LOW_Q30_001"].exception_codes
    assert records["RNA_DEMO_FAILED_VALID_UPSTREAM_001"].lineage is not None
    assert records["RNA_DEMO_FAILED_VALID_UPSTREAM_001"].lineage.upstream_workflow_valid is True
    assert "cannot infer a lab root cause" in records[
        "RNA_DEMO_FAILED_VALID_UPSTREAM_001"
    ].safe_interpretation


def test_unmatched_missing_ancestry_missing_qc_and_invalid_upstream_are_flagged() -> None:
    report = validate_qc_provenance_records(
        parse_ngs_qc_csv(QC_CSV),
        read_lineage_manifest(LINEAGE_CSV),
    )
    records = {record.sample_id: record for record in report.records}

    assert ExceptionCode.UNMATCHED_QC_SAMPLE_ID in records["RNA_QC_UNKNOWN_001"].exception_codes
    assert ExceptionCode.QC_PROVENANCE_GAP in records[
        "RNA_DEMO_MISSING_ANCESTRY_001"
    ].exception_codes
    assert ExceptionCode.MISSING_QC_RESULT in records["RNA_DEMO_MISSING_QC_001"].exception_codes
    assert ExceptionCode.QC_PROVENANCE_GAP in records[
        "RNA_DEMO_UPSTREAM_INVALID_001"
    ].exception_codes
    assert "cannot retroactively validate" in records[
        "RNA_DEMO_UPSTREAM_INVALID_001"
    ].safe_interpretation


def test_duplicate_qc_or_lineage_sample_ids_require_manual_review() -> None:
    duplicate_qc_report = validate_qc_provenance_records(
        (
            NgsQcResult(
                sample_id="RNA_DEMO_DUPLICATE_001",
                qc_batch_id="QC_BATCH_DUP",
                analysis_id="ANALYSIS_DUP_A",
                read_count=2_000_000,
                q30_percent=90.0,
            ),
            NgsQcResult(
                sample_id="RNA_DEMO_DUPLICATE_001",
                qc_batch_id="QC_BATCH_DUP",
                analysis_id="ANALYSIS_DUP_B",
                read_count=2_100_000,
                q30_percent=91.0,
            ),
        ),
        (
            UpstreamLineageRecord(
                sample_id="RNA_DEMO_DUPLICATE_001",
                lab_batch_id="RNA_BATCH_FIXED_001",
                quant_batch_id="RNA_QUANT_001",
                normalization_batch_id="RNA_NORM_001",
                requant_batch_id="RNA_REQUANT_001",
            ),
        ),
    )
    duplicate_qc_records = [
        record
        for record in duplicate_qc_report.records
        if record.sample_id == "RNA_DEMO_DUPLICATE_001"
    ]

    assert len(duplicate_qc_records) == 2
    assert all(
        ExceptionCode.DUPLICATE_SAMPLE_ID in record.exception_codes
        for record in duplicate_qc_records
    )
    assert all(record.manual_review_required for record in duplicate_qc_records)
    assert all(
        record.provenance_status is QcProvenanceStatus.DOWNSTREAM_QC_REVIEW_REQUIRED
        for record in duplicate_qc_records
    )

    duplicate_lineage_report = validate_qc_provenance_records(
        (
            NgsQcResult(
                sample_id="RNA_DEMO_DUPLICATE_LINEAGE_001",
                qc_batch_id="QC_BATCH_DUP",
                analysis_id="ANALYSIS_DUP",
                read_count=2_000_000,
                q30_percent=90.0,
            ),
        ),
        (
            UpstreamLineageRecord(
                sample_id="RNA_DEMO_DUPLICATE_LINEAGE_001",
                lab_batch_id="RNA_BATCH_FIXED_001",
                quant_batch_id="RNA_QUANT_001",
                normalization_batch_id="RNA_NORM_001",
                requant_batch_id="RNA_REQUANT_001",
            ),
            UpstreamLineageRecord(
                sample_id="RNA_DEMO_DUPLICATE_LINEAGE_001",
                lab_batch_id="RNA_BATCH_OTHER_001",
                quant_batch_id="RNA_QUANT_002",
                normalization_batch_id="RNA_NORM_002",
                requant_batch_id="RNA_REQUANT_002",
            ),
        ),
    )
    duplicate_lineage = duplicate_lineage_report.records[0]

    assert ExceptionCode.DUPLICATE_SAMPLE_ID in duplicate_lineage.exception_codes
    assert duplicate_lineage.manual_review_required is True
    assert duplicate_lineage.provenance_status is QcProvenanceStatus.DOWNSTREAM_QC_REVIEW_REQUIRED
    assert "Provenance is ambiguous" in duplicate_lineage.safe_interpretation


def test_qc_tools_are_registered_and_return_structured_json() -> None:
    names = {tool["name"] for tool in list_tools()}

    assert {
        "ingest_ngs_qc_results",
        "validate_qc_provenance",
        "explain_qc_failure",
        "generate_lab_to_analysis_lineage",
    } <= names

    ingest = ingest_ngs_qc_results(str(QC_CSV))
    validation = validate_qc_provenance(str(QC_CSV), str(LINEAGE_CSV))
    explanation = explain_qc_failure(
        str(QC_CSV),
        "RNA_DEMO_FAILED_VALID_UPSTREAM_001",
        lineage_csv=str(LINEAGE_CSV),
    )
    lineage = generate_lab_to_analysis_lineage(
        str(QC_CSV),
        str(LINEAGE_CSV),
        dry_run=True,
    )

    assert ingest["status"] == "ok"
    assert validation["status"] == "invalid"
    assert explanation["status"] == "invalid"
    assert "root cause" in explanation["artifacts"][0]["data"]["root_cause_boundary"]
    assert lineage["status"] == "ok"
    assert lineage["audit_event"]["mode"] == "dry_run"
    assert {
        artifact["artifact_type"] for artifact in lineage["artifacts"]
    } >= {"downstream_qc_summary", "lab_to_analysis_lineage_markdown"}
    lineage_markdown = next(
        artifact["data"]
        for artifact in lineage["artifacts"]
        if artifact["artifact_type"] == "lab_to_analysis_lineage_markdown"
    )
    assert "RNA_DEMO_FAILED_VALID_UPSTREAM_001" in lineage_markdown
    json.dumps(ingest)
    json.dumps(validation)
    json.dumps(explanation)
    json.dumps(lineage)


def test_lineage_report_commit_mode_is_blocked_by_tool_and_policy() -> None:
    direct = generate_lab_to_analysis_lineage(str(QC_CSV), str(LINEAGE_CSV), dry_run=False)
    via_registry = call_tool(
        "generate_lab_to_analysis_lineage",
        qc_csv=str(QC_CSV),
        lineage_csv=str(LINEAGE_CSV),
        dry_run=False,
    )

    for result in (direct, via_registry):
        assert result["ok"] is False
        assert result["status"] == "blocked"
        assert {error["code"] for error in result["errors"]} == {"COMMIT_MODE_NOT_AVAILABLE"}
