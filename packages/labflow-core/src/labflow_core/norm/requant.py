"""RNA re-quantification workflow helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from labflow_core.domain.exceptions import ExceptionRecord
from labflow_core.domain.statuses import AncestryEventType, ExceptionCode, ExceptionSeverity, Status
from labflow_core.lims.ancestry import ANCESTRY_COLUMNS, AncestryRecord, AncestryTracker
from labflow_core.lims.manifests import read_csv_rows, write_csv_rows, write_exception_report
from labflow_core.norm.planner import (
    NormalizationConfig,
    NormalizationPlanResult,
    process_normalization_config,
    write_normalization_outputs,
)

RNA_REQUANT_COLUMNS = [
    "sample_id",
    "requant_concentration_ng_per_ul",
    "manual_review_reason",
    "status",
    "downstream_concentration_ng_per_ul",
]

RNA_DOWNSTREAM_COLUMNS = [
    "sample_id",
    "downstream_concentration_ng_per_ul",
    "downstream_ready",
]


class RnaRequantPolicy(BaseModel):
    """Configurable synthetic review policy for RNA re-quant results."""

    model_config = ConfigDict(frozen=True)

    assay_min_concentration_ng_per_ul: float | None = Field(default=None, ge=0)
    assay_max_concentration_ng_per_ul: float | None = Field(default=None, gt=0)
    minimum_downstream_concentration_ng_per_ul: float | None = Field(default=None, ge=0)


@dataclass(frozen=True)
class RequantResultRow:
    sample_id: str
    requant_concentration_ng_per_ul: float | None
    status: Status
    downstream_concentration_ng_per_ul: float | None
    manual_review_reason: str | None = None

    def to_requant_row(self) -> dict[str, str]:
        return {
            "sample_id": self.sample_id,
            "requant_concentration_ng_per_ul": (
                _fmt4(self.requant_concentration_ng_per_ul)
                if self.requant_concentration_ng_per_ul is not None
                else ""
            ),
            "manual_review_reason": self.manual_review_reason or "",
            "status": self.status.value,
            "downstream_concentration_ng_per_ul": (
                _fmt4(self.downstream_concentration_ng_per_ul)
                if self.downstream_concentration_ng_per_ul is not None
                else ""
            ),
        }

    def to_downstream_row(self) -> dict[str, str]:
        downstream = self.downstream_concentration_ng_per_ul
        return {
            "sample_id": self.sample_id,
            "downstream_concentration_ng_per_ul": (
                _fmt4(downstream) if downstream is not None else ""
            ),
            "downstream_ready": str(downstream is not None),
        }


@dataclass(frozen=True)
class RnaWorkflowResult:
    normalization: NormalizationPlanResult
    requant_rows: tuple[RequantResultRow, ...]
    requant_exceptions: tuple[ExceptionRecord, ...]
    ancestry_records: tuple[AncestryRecord, ...]


def process_rna_workflow(
    config: NormalizationConfig,
    requant_csv: Path,
    policy: RnaRequantPolicy | None = None,
) -> RnaWorkflowResult:
    review_policy = policy or RnaRequantPolicy()
    normalization = process_normalization_config(config)
    requant_rows: list[RequantResultRow] = []
    requant_exceptions: list[ExceptionRecord] = []
    tracker = AncestryTracker()
    expected_sample_ids = {
        row.child_sample_id or row.sample_id
        for row in normalization.rows
        if row.generates_robot_transfer
    }
    seen_sample_ids: set[str] = set()

    for row in read_csv_rows(requant_csv):
        sample_id = row["sample_id"]
        if sample_id not in expected_sample_ids:
            requant_exceptions.append(
                ExceptionRecord(
                    exception_code=ExceptionCode.INVALID_REQUANT_RESULT,
                    severity=ExceptionSeverity.WARNING,
                    batch_id=config.batch_id,
                    sample_id=sample_id,
                    message="RNA re-quant result does not match an expected normalized sample.",
                    suggested_action="Verify sample ID ancestry before using the result.",
                    blocks_robot_transfer=True,
                )
            )
            requant_rows.append(
                RequantResultRow(
                    sample_id=sample_id,
                    requant_concentration_ng_per_ul=None,
                    status=Status.MANUAL_REVIEW,
                    downstream_concentration_ng_per_ul=None,
                )
            )
            continue

        seen_sample_ids.add(sample_id)
        raw_value = row.get("requant_concentration_ng_per_ul", "")
        parsed = _parse_positive_optional_float(raw_value)
        if raw_value == "":
            requant_exceptions.append(
                ExceptionRecord(
                    exception_code=ExceptionCode.MISSING_REQUANT_RESULT,
                    severity=ExceptionSeverity.WARNING,
                    batch_id=config.batch_id,
                    sample_id=sample_id,
                    message="RNA re-quant result is missing.",
                    suggested_action="Repeat RiboGreen re-quant or send sample to manual review.",
                    blocks_robot_transfer=True,
                )
            )
            requant_rows.append(_manual_review_row(sample_id, "missing_result"))
            continue
        if parsed is None:
            requant_exceptions.append(
                ExceptionRecord(
                    exception_code=ExceptionCode.INVALID_REQUANT_RESULT,
                    severity=ExceptionSeverity.WARNING,
                    batch_id=config.batch_id,
                    sample_id=sample_id,
                    message="RNA re-quant result is invalid or non-positive.",
                    suggested_action="Repeat RiboGreen re-quant or send sample to manual review.",
                    blocks_robot_transfer=True,
                )
            )
            requant_rows.append(_manual_review_row(sample_id, "invalid_result"))
            continue
        if _is_out_of_assay_range(parsed, review_policy):
            requant_exceptions.append(
                ExceptionRecord(
                    exception_code=ExceptionCode.REQUANT_OUT_OF_ASSAY_RANGE,
                    severity=ExceptionSeverity.WARNING,
                    batch_id=config.batch_id,
                    sample_id=sample_id,
                    message="RNA re-quant result is outside the configured assay range.",
                    suggested_action="Repeat RiboGreen re-quant or send sample to manual review.",
                    blocks_robot_transfer=True,
                )
            )
            requant_rows.append(
                _manual_review_row(sample_id, "out_of_assay_range", concentration=parsed)
            )
            continue
        downstream_minimum = review_policy.minimum_downstream_concentration_ng_per_ul
        if downstream_minimum is not None and parsed < downstream_minimum:
            requant_exceptions.append(
                ExceptionRecord(
                    exception_code=ExceptionCode.DOWNSTREAM_VOLUME_CONSTRAINT_FAILED,
                    severity=ExceptionSeverity.WARNING,
                    batch_id=config.batch_id,
                    sample_id=sample_id,
                    message=(
                        "RNA re-quant result cannot satisfy configured downstream "
                        "concentration/volume constraints."
                    ),
                    suggested_action=(
                        "Revise downstream volume constraints or send sample to manual review."
                    ),
                    blocks_robot_transfer=True,
                )
            )
            requant_rows.append(
                _manual_review_row(
                    sample_id,
                    "impossible_under_downstream_volume_constraints",
                    concentration=parsed,
                )
            )
            continue

        tracker.add(
            AncestryRecord(
                child_sample_id=sample_id,
                event_type=AncestryEventType.REQUANTIFIED,
                batch_id=config.batch_id,
                workflow_type=config.workflow_type,
            )
        )
        requant_rows.append(
            RequantResultRow(
                sample_id=sample_id,
                requant_concentration_ng_per_ul=parsed,
                status=Status.DOWNSTREAM_READY,
                downstream_concentration_ng_per_ul=parsed,
            )
        )

    for missing_sample_id in sorted(expected_sample_ids - seen_sample_ids):
        requant_exceptions.append(
            ExceptionRecord(
                exception_code=ExceptionCode.MISSING_REQUANT_RESULT,
                severity=ExceptionSeverity.WARNING,
                batch_id=config.batch_id,
                sample_id=missing_sample_id,
                message="Expected RNA re-quant result is absent from the re-quant file.",
                suggested_action="Repeat RiboGreen re-quant or send sample to manual review.",
                blocks_robot_transfer=True,
            )
        )
        requant_rows.append(_manual_review_row(missing_sample_id, "missing_result"))

    return RnaWorkflowResult(
        normalization=normalization,
        requant_rows=tuple(sorted(requant_rows, key=lambda result_row: result_row.sample_id)),
        requant_exceptions=tuple(requant_exceptions),
        ancestry_records=normalization.ancestry_records + tracker.records,
    )


def write_rna_outputs(result: RnaWorkflowResult, out_dir: Path) -> None:
    write_normalization_outputs(result.normalization, out_dir, prefix="rna_")
    write_csv_rows(
        out_dir / "rna_requant_results.csv",
        RNA_REQUANT_COLUMNS,
        [row.to_requant_row() for row in result.requant_rows],
    )
    write_csv_rows(
        out_dir / "rna_downstream_concentration_manifest.csv",
        RNA_DOWNSTREAM_COLUMNS,
        [row.to_downstream_row() for row in result.requant_rows],
    )
    write_exception_report(
        out_dir / "rna_exception_report.csv",
        result.normalization.exceptions + result.requant_exceptions,
    )
    write_csv_rows(
        out_dir / "sample_ancestry.csv",
        ANCESTRY_COLUMNS,
        [record.to_row() for record in result.ancestry_records],
    )


def _manual_review_row(
    sample_id: str,
    reason: str,
    *,
    concentration: float | None = None,
) -> RequantResultRow:
    return RequantResultRow(
        sample_id=sample_id,
        requant_concentration_ng_per_ul=concentration,
        status=Status.MANUAL_REVIEW,
        downstream_concentration_ng_per_ul=None,
        manual_review_reason=reason,
    )


def _parse_positive_optional_float(value: str) -> float | None:
    try:
        parsed = float(value)
    except ValueError:
        return None
    if parsed <= 0:
        return None
    return parsed


def _is_out_of_assay_range(value: float, policy: RnaRequantPolicy) -> bool:
    minimum = policy.assay_min_concentration_ng_per_ul
    maximum = policy.assay_max_concentration_ng_per_ul
    if minimum is not None and value < minimum:
        return True
    if maximum is not None and value > maximum:
        return True
    return False


def _fmt4(value: float) -> str:
    return f"{value:.4f}"
