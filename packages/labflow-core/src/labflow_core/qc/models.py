"""Typed models for synthetic downstream NGS QC provenance."""

from __future__ import annotations

from collections import Counter
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from labflow_core.domain.identifiers import optional_nonblank_identifier, require_nonblank_identifier
from labflow_core.domain.statuses import ExceptionCode


class QcStatus(StrEnum):
    """Deterministic downstream QC threshold status."""

    PASS = "PASS"
    FAIL = "FAIL"
    MISSING = "MISSING"


class QcProvenanceStatus(StrEnum):
    """Deterministic lineage status for downstream QC rows."""

    LINKED = "LINKED"
    UNMATCHED_QC_SAMPLE_ID = "UNMATCHED_QC_SAMPLE_ID"
    QC_PROVENANCE_GAP = "QC_PROVENANCE_GAP"
    DOWNSTREAM_QC_REVIEW_REQUIRED = "DOWNSTREAM_QC_REVIEW_REQUIRED"


class QcThresholds(BaseModel):
    """Small configurable synthetic QC thresholds."""

    model_config = ConfigDict(frozen=True)

    min_read_count: int = Field(default=1_000_000, ge=0)
    min_q30_percent: float = Field(default=80.0, ge=0, le=100)


class NgsQcResult(BaseModel):
    """One synthetic downstream QC summary row."""

    model_config = ConfigDict(frozen=True)

    sample_id: str = Field(min_length=1)
    qc_batch_id: str = Field(min_length=1)
    analysis_id: str = Field(min_length=1)
    read_count: int | None = Field(default=None, ge=0)
    q30_percent: float | None = Field(default=None, ge=0, le=100)

    @field_validator("sample_id", "qc_batch_id", "analysis_id")
    @classmethod
    def required_identifier(cls, value: str, info: ValidationInfo) -> str:
        return require_nonblank_identifier(value, info.field_name)


class UpstreamLineageRecord(BaseModel):
    """Synthetic lab lineage known before downstream QC review."""

    model_config = ConfigDict(frozen=True)

    sample_id: str = Field(min_length=1)
    lab_batch_id: str = Field(min_length=1)
    quant_batch_id: str | None = None
    normalization_batch_id: str | None = None
    requant_batch_id: str | None = None
    upstream_workflow_valid: bool = True
    has_ancestry: bool = True

    @field_validator("sample_id", "lab_batch_id")
    @classmethod
    def required_identifier(cls, value: str, info: ValidationInfo) -> str:
        return require_nonblank_identifier(value, info.field_name)

    @field_validator("quant_batch_id", "normalization_batch_id", "requant_batch_id", mode="before")
    @classmethod
    def optional_identifier(cls, value: str | None) -> str | None:
        return optional_nonblank_identifier(value)

    @property
    def has_required_ancestry(self) -> bool:
        return bool(
            self.has_ancestry
            and self.quant_batch_id
            and self.normalization_batch_id
            and self.requant_batch_id
        )


class QcEvaluation(BaseModel):
    """Threshold evaluation for one downstream QC row."""

    model_config = ConfigDict(frozen=True)

    result: NgsQcResult
    thresholds: QcThresholds
    status: QcStatus
    exception_codes: tuple[ExceptionCode, ...] = ()

    @property
    def manual_review_required(self) -> bool:
        return bool(self.exception_codes)

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class QcProvenanceRecord(BaseModel):
    """QC row plus deterministic lab lineage assessment."""

    model_config = ConfigDict(frozen=True)

    sample_id: str = Field(min_length=1)
    qc_result: NgsQcResult | None
    lineage: UpstreamLineageRecord | None
    qc_status: QcStatus
    provenance_status: QcProvenanceStatus
    exception_codes: tuple[ExceptionCode, ...] = ()
    manual_review_required: bool
    safe_interpretation: str = Field(min_length=1)

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class QcProvenanceReport(BaseModel):
    """Deterministic downstream QC provenance report."""

    model_config = ConfigDict(frozen=True)

    thresholds: QcThresholds
    records: tuple[QcProvenanceRecord, ...]

    @property
    def summary(self) -> dict[str, Any]:
        status_counts = Counter(record.provenance_status.value for record in self.records)
        qc_counts = Counter(record.qc_status.value for record in self.records)
        code_counts = Counter(
            code.value
            for record in self.records
            for code in record.exception_codes
        )
        return {
            "record_count": len(self.records),
            "manual_review_count": sum(1 for record in self.records if record.manual_review_required),
            "qc_status_counts": dict(sorted(qc_counts.items())),
            "provenance_status_counts": dict(sorted(status_counts.items())),
            "exception_code_counts": dict(sorted(code_counts.items())),
        }

    def to_json_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload["summary"] = self.summary
        return payload
