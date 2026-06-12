"""Human-readable synthetic QC provenance reports."""

from __future__ import annotations

from typing import Any

from labflow_core.qc.models import QcProvenanceRecord, QcProvenanceReport


def build_qc_summary_report(report: QcProvenanceReport) -> dict[str, Any]:
    """Return a structured downstream QC summary."""

    return {
        "synthetic": True,
        "pipeline_scope": "summary_metrics_only",
        "thresholds": report.thresholds.model_dump(mode="json"),
        "summary": report.summary,
        "records": [_record_to_summary(record) for record in report.records],
        "safe_interpretation": (
            "Downstream QC results summarize synthetic analysis metrics and lineage links. "
            "They do not infer lab root cause and do not validate invalid upstream batches."
        ),
    }


def lineage_report_markdown(report: QcProvenanceReport) -> str:
    """Render a compact lab-to-analysis lineage report."""

    lines = [
        "# Lab-To-Analysis Lineage Report",
        "",
        "Synthetic downstream QC provenance summary. This is not a clinical, diagnostic, production, or root-cause report.",
        "",
        "## Thresholds",
        "",
        f"- Minimum read count: `{report.thresholds.min_read_count}`",
        f"- Minimum Q30 percent: `{report.thresholds.min_q30_percent}`",
        "",
        "## Summary",
        "",
        f"- Records: `{report.summary['record_count']}`",
        f"- Manual review required: `{report.summary['manual_review_count']}`",
        "",
        "## Lineage",
        "",
        "| Sample | Quant Batch | Normalization Batch | Re-Quant Batch | QC Batch | QC Status | Provenance Status | Exceptions |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for record in report.records:
        lineage = record.lineage
        qc = record.qc_result
        lines.append(
            "| {sample} | {quant} | {norm} | {requant} | {qc_batch} | {qc_status} | {prov_status} | {codes} |".format(
                sample=record.sample_id,
                quant=lineage.quant_batch_id if lineage and lineage.quant_batch_id else "",
                norm=lineage.normalization_batch_id if lineage and lineage.normalization_batch_id else "",
                requant=lineage.requant_batch_id if lineage and lineage.requant_batch_id else "",
                qc_batch=qc.qc_batch_id if qc else "",
                qc_status=record.qc_status.value,
                prov_status=record.provenance_status.value,
                codes=", ".join(code.value for code in record.exception_codes),
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "- Failed downstream QC requires review, but does not identify a lab root cause by itself.",
            "- Passing downstream QC does not retroactively validate an invalid or incomplete upstream lab batch.",
            "- Unmatched sample IDs and provenance gaps require manual review.",
        ]
    )
    return "\n".join(lines) + "\n"


def _record_to_summary(record: QcProvenanceRecord) -> dict[str, Any]:
    lineage = record.lineage
    qc = record.qc_result
    return {
        "sample_id": record.sample_id,
        "lab_batch_id": lineage.lab_batch_id if lineage else None,
        "quant_batch_id": lineage.quant_batch_id if lineage else None,
        "normalization_batch_id": lineage.normalization_batch_id if lineage else None,
        "requant_batch_id": lineage.requant_batch_id if lineage else None,
        "qc_batch_id": qc.qc_batch_id if qc else None,
        "analysis_id": qc.analysis_id if qc else None,
        "read_count": qc.read_count if qc else None,
        "q30_percent": qc.q30_percent if qc else None,
        "qc_status": record.qc_status.value,
        "provenance_status": record.provenance_status.value,
        "exception_codes": [code.value for code in record.exception_codes],
        "manual_review_required": record.manual_review_required,
        "safe_interpretation": record.safe_interpretation,
    }
