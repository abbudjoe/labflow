"""Normalization planning for deterministic DNA and RNA workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from labflow_core.domain.containers import ContainerType
from labflow_core.domain.exceptions import ExceptionRecord
from labflow_core.domain.samples import NormalizationSampleInput
from labflow_core.domain.statuses import (
    AnalyteType,
    AncestryEventType,
    ExceptionCode,
    ExceptionSeverity,
    NormalizationMode,
    Status,
    WorkflowType,
)
from labflow_core.domain.units import MINIMUM_TRANSFER_VOLUME_UL, required_source_volume_ul
from labflow_core.domain.wells import WellCoordinate
from labflow_core.lims.ancestry import ANCESTRY_COLUMNS, AncestryRecord, AncestryTracker
from labflow_core.lims.manifests import (
    read_csv_rows,
    validate_duplicate_manifest_rows,
    validate_mode_location_contract,
    write_csv_rows,
    write_exception_report,
)
from labflow_core.lims.registry import ContainerRegistry
from labflow_core.norm.split import SplitConfig
from labflow_core.norm.targets import NormalizationTarget

NORMALIZATION_PLAN_COLUMNS = [
    "batch_id",
    "sample_id",
    "source_container_id",
    "source_well",
    "destination_container_id",
    "destination_well",
    "source_concentration_ng_per_ul",
    "target_concentration_ng_per_ul",
    "target_final_volume_ul",
    "target_mass_ng",
    "sample_transfer_volume_ul",
    "diluent_volume_ul",
    "normalization_mode",
    "status",
]

AUDIT_MANIFEST_COLUMNS = [
    "batch_id",
    "sample_id",
    "event_type",
    "manual_override",
    "auditable",
    "message",
]


class NormalizationConfig(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    batch_id: str = Field(min_length=1)
    workflow_type: WorkflowType
    analyte_type: AnalyteType
    input_csv: Path
    target: NormalizationTarget
    split_config: SplitConfig = Field(default_factory=SplitConfig)
    registry: ContainerRegistry


@dataclass(frozen=True)
class NormalizationPlanRow:
    batch_id: str
    sample_id: str
    source_container_id: str
    source_well: WellCoordinate
    destination_container_id: str | None
    destination_well: WellCoordinate | None
    source_concentration_ng_per_ul: float
    target_concentration_ng_per_ul: float
    target_final_volume_ul: float
    target_mass_ng: float
    sample_transfer_volume_ul: float
    diluent_volume_ul: float
    normalization_mode: NormalizationMode
    status: Status
    generates_robot_transfer: bool
    child_sample_id: str | None = None

    def to_csv_row(self) -> dict[str, str]:
        return {
            "batch_id": self.batch_id,
            "sample_id": self.sample_id,
            "source_container_id": self.source_container_id,
            "source_well": str(self.source_well),
            "destination_container_id": self.destination_container_id or "",
            "destination_well": str(self.destination_well) if self.destination_well else "",
            "source_concentration_ng_per_ul": _fmt4(self.source_concentration_ng_per_ul),
            "target_concentration_ng_per_ul": _fmt4(self.target_concentration_ng_per_ul),
            "target_final_volume_ul": _fmt2(self.target_final_volume_ul),
            "target_mass_ng": _fmt4(self.target_mass_ng),
            "sample_transfer_volume_ul": _fmt2(self.sample_transfer_volume_ul),
            "diluent_volume_ul": _fmt2(self.diluent_volume_ul),
            "normalization_mode": self.normalization_mode.value,
            "status": self.status.value,
        }


@dataclass(frozen=True)
class NormalizationPlanResult:
    rows: tuple[NormalizationPlanRow, ...]
    exceptions: tuple[ExceptionRecord, ...]
    ancestry_records: tuple[AncestryRecord, ...]


@dataclass(frozen=True)
class NormalizationInputLoadResult:
    samples: tuple[NormalizationSampleInput, ...]
    exceptions: tuple[ExceptionRecord, ...]


def read_normalization_samples(
    input_csv: Path,
    *,
    analyte_type: AnalyteType,
) -> list[NormalizationSampleInput]:
    return list(read_normalization_sample_inputs(input_csv, analyte_type=analyte_type).samples)


def read_normalization_sample_inputs(
    input_csv: Path,
    *,
    analyte_type: AnalyteType,
) -> NormalizationInputLoadResult:
    samples: list[NormalizationSampleInput] = []
    exceptions: list[ExceptionRecord] = []
    for row_number, row in enumerate(read_csv_rows(input_csv), start=2):
        row_exceptions: list[ExceptionRecord] = []
        sample_id = (row.get("sample_id") or "").strip()
        source_container_id = (row.get("source_container_id") or "").strip()
        source_well_raw = (row.get("source_well") or "").strip()
        destination_container_id = (row.get("destination_container_id") or "").strip() or None
        destination_well_raw = (row.get("destination_well") or "").strip()
        source_well = _parse_well_for_row(
            source_well_raw,
            code=ExceptionCode.INVALID_SOURCE_LOCATION,
            row_number=row_number,
            sample_id=sample_id or None,
            source_container_id=source_container_id or None,
            exceptions=row_exceptions,
        )
        destination_well = None
        if destination_well_raw:
            destination_well = _parse_well_for_row(
                destination_well_raw,
                code=ExceptionCode.INVALID_DESTINATION_LOCATION,
                row_number=row_number,
                sample_id=sample_id or None,
                source_container_id=source_container_id or None,
                exceptions=row_exceptions,
            )
        concentration = _parse_required_float_for_row(
            row.get("stock_concentration_ng_per_ul"),
            missing_code=ExceptionCode.MISSING_CONCENTRATION,
            invalid_code=ExceptionCode.INVALID_CONCENTRATION,
            field_name="stock_concentration_ng_per_ul",
            row_number=row_number,
            sample_id=sample_id or None,
            source_container_id=source_container_id or None,
            exceptions=row_exceptions,
        )
        available_volume = _parse_required_float_for_row(
            row.get("available_volume_ul"),
            missing_code=ExceptionCode.MISSING_AVAILABLE_VOLUME,
            invalid_code=ExceptionCode.INVALID_AVAILABLE_VOLUME,
            field_name="available_volume_ul",
            row_number=row_number,
            sample_id=sample_id or None,
            source_container_id=source_container_id or None,
            exceptions=row_exceptions,
        )
        if not sample_id:
            row_exceptions.append(
                _ingest_exception(
                    code=ExceptionCode.MISSING_SAMPLE_ID,
                    row_number=row_number,
                    message="sample_id is required.",
                    action="Provide a LIMS sample ID before planning.",
                    sample_id=None,
                    source_container_id=source_container_id or None,
                    blocks_robot_transfer=True,
                )
            )
        if not source_container_id:
            row_exceptions.append(
                _ingest_exception(
                    code=ExceptionCode.MISSING_SOURCE_LOCATION,
                    row_number=row_number,
                    message="source_container_id is required.",
                    action="Provide a LIMS-resolved source container.",
                    sample_id=sample_id or None,
                    source_container_id=None,
                    blocks_robot_transfer=True,
                )
            )
        if not source_well_raw:
            row_exceptions.append(
                _ingest_exception(
                    code=ExceptionCode.MISSING_SOURCE_LOCATION,
                    row_number=row_number,
                    message="source_well is required.",
                    action="Provide a valid 96-well source location.",
                    sample_id=sample_id or None,
                    source_container_id=source_container_id or None,
                    blocks_robot_transfer=True,
                )
            )
        if concentration is not None and concentration <= 0:
            row_exceptions.append(
                _ingest_exception(
                    code=ExceptionCode.INVALID_CONCENTRATION,
                    row_number=row_number,
                    message="stock_concentration_ng_per_ul must be positive.",
                    action="Repeat quantification or exclude the sample.",
                    sample_id=sample_id or None,
                    source_container_id=source_container_id or None,
                    blocks_robot_transfer=True,
                )
            )
        if available_volume is not None and available_volume <= 0:
            row_exceptions.append(
                _ingest_exception(
                    code=ExceptionCode.INVALID_AVAILABLE_VOLUME,
                    row_number=row_number,
                    message="available_volume_ul must be positive.",
                    action="Correct the source volume or exclude the sample.",
                    sample_id=sample_id or None,
                    source_container_id=source_container_id or None,
                    blocks_robot_transfer=True,
                )
            )

        if row_exceptions:
            exceptions.extend(row_exceptions)
            continue
        assert source_well is not None
        assert concentration is not None
        assert available_volume is not None
        samples.append(
            NormalizationSampleInput(
                sample_id=sample_id,
                analyte_type=analyte_type,
                source_container_id=source_container_id,
                source_well=source_well,
                stock_concentration_ng_per_ul=concentration,
                available_volume_ul=available_volume,
                destination_container_id=destination_container_id,
                destination_well=destination_well,
            )
        )
    return NormalizationInputLoadResult(samples=tuple(samples), exceptions=tuple(exceptions))


def plan_normalization(
    *,
    batch_id: str,
    workflow_type: WorkflowType,
    samples: list[NormalizationSampleInput],
    target: NormalizationTarget,
    registry: ContainerRegistry,
    split_config: SplitConfig,
) -> NormalizationPlanResult:
    exceptions: list[ExceptionRecord] = validate_duplicate_manifest_rows(samples, batch_id=batch_id)
    duplicate_blocked_sample_ids = {exc.sample_id for exc in exceptions if exc.sample_id}
    tracker = AncestryTracker()
    rows: list[NormalizationPlanRow] = []

    for sample in samples:
        if sample.sample_id in duplicate_blocked_sample_ids:
            rows.append(_invalid_row(batch_id, sample, target))
            continue

        source_type = _resolve_container_type_for_sample(
            registry,
            sample,
            batch_id=batch_id,
            container_id=sample.source_container_id,
            source=True,
            exceptions=exceptions,
        )
        if source_type is None:
            rows.append(_invalid_row(batch_id, sample, target))
            continue

        sample_exceptions: list[ExceptionRecord] = []
        source_concentration = sample.stock_concentration_ng_per_ul
        if source_concentration <= 0:
            sample_exceptions.append(
                _sample_exception(
                    batch_id,
                    sample,
                    ExceptionCode.INVALID_CONCENTRATION,
                    "Source concentration must be positive.",
                    "Repeat quantification or exclude the sample.",
                )
            )
            exceptions.extend(sample_exceptions)
            rows.append(_invalid_row(batch_id, sample, target))
            continue

        target_concentration = target.concentration_ng_per_ul
        standard_transfer = (
            target_concentration * target.target_final_volume_ul / source_concentration
        )
        diluent_volume = target.target_final_volume_ul - standard_transfer

        if source_concentration < target_concentration:
            sample_exceptions.append(
                _sample_exception(
                    batch_id,
                    sample,
                    ExceptionCode.SOURCE_CONCENTRATION_BELOW_TARGET,
                    "Source concentration is below the target concentration.",
                    "Choose a lower target or exclude the sample.",
                )
            )
        if diluent_volume < 0:
            sample_exceptions.append(
                _sample_exception(
                    batch_id,
                    sample,
                    ExceptionCode.DILUENT_VOLUME_NEGATIVE,
                    "Calculated diluent volume is negative.",
                    "Review target and source concentration.",
                )
            )

        if sample_exceptions:
            exceptions.extend(sample_exceptions)
            rows.append(_invalid_row(batch_id, sample, target))
            continue

        if standard_transfer < MINIMUM_TRANSFER_VOLUME_UL:
            if not sample.destination_container_id or sample.destination_well is None:
                exc = validate_mode_location_contract(
                    sample,
                    NormalizationMode.STANDARD_NEW_CONTAINER,
                )
                if exc:
                    exceptions.append(_with_batch(exc, batch_id))
                    rows.append(_invalid_row(batch_id, sample, target))
                    continue
            split_destination_type = None
            if sample.destination_container_id:
                split_destination_type = _resolve_container_type_for_sample(
                    registry,
                    sample,
                    batch_id=batch_id,
                    container_id=sample.destination_container_id,
                    source=False,
                    exceptions=exceptions,
                )
            if split_destination_type is None:
                rows.append(_invalid_row(batch_id, sample, target))
                continue
            if split_config.split_final_volume_ul > split_destination_type.max_working_volume_ul:
                exceptions.append(
                    _sample_exception(
                        batch_id,
                        sample,
                        ExceptionCode.DESTINATION_VOLUME_EXCEEDED,
                        "Split final volume exceeds destination container working volume.",
                        "Lower split final volume or choose a supported destination container.",
                    )
                )
                rows.append(_invalid_row(batch_id, sample, target))
                continue
            child_sample_id = f"{sample.sample_id}-SPLIT1"
            expected_child_concentration = split_config.expected_child_concentration_ng_per_ul(
                source_concentration
            )
            exceptions.extend(
                [
                    ExceptionRecord(
                        exception_code=ExceptionCode.SPLIT_REQUIRED_HIGH_CONCENTRATION,
                        severity=ExceptionSeverity.WARNING,
                        batch_id=batch_id,
                        sample_id=sample.sample_id,
                        source_container_id=sample.source_container_id,
                        source_well=sample.source_well,
                        destination_container_id=sample.destination_container_id,
                        destination_well=sample.destination_well,
                        message=(
                            "Calculated direct transfer is below 1 uL; "
                            "split workflow required."
                        ),
                        suggested_action="Create split child, re-quant child, then follow up.",
                        blocks_robot_transfer=False,
                    ),
                    ExceptionRecord(
                        exception_code=ExceptionCode.SPLIT_REQUANT_REQUIRED,
                        severity=ExceptionSeverity.WARNING,
                        batch_id=batch_id,
                        sample_id=child_sample_id,
                        source_container_id=sample.source_container_id,
                        source_well=sample.source_well,
                        destination_container_id=sample.destination_container_id,
                        destination_well=sample.destination_well,
                        message="Split child requires re-quant before downstream normalization.",
                        suggested_action="Run RiboGreen/PicoGreen re-quant on the split child.",
                        blocks_robot_transfer=False,
                    ),
                ]
            )
            assert sample.destination_container_id is not None
            assert sample.destination_well is not None
            tracker.record_split(
                parent_sample_id=sample.sample_id,
                child_sample_id=child_sample_id,
                source_container_id=sample.source_container_id,
                source_well=sample.source_well,
                destination_container_id=sample.destination_container_id,
                destination_well=sample.destination_well,
                batch_id=batch_id,
                workflow_type=workflow_type,
                expected_child_concentration_ng_per_ul=expected_child_concentration,
            )
            rows.append(
                NormalizationPlanRow(
                    batch_id=batch_id,
                    sample_id=sample.sample_id,
                    source_container_id=sample.source_container_id,
                    source_well=sample.source_well,
                    destination_container_id=sample.destination_container_id,
                    destination_well=sample.destination_well,
                    source_concentration_ng_per_ul=source_concentration,
                    target_concentration_ng_per_ul=target_concentration,
                    target_final_volume_ul=split_config.split_final_volume_ul,
                    target_mass_ng=target.mass_ng,
                    sample_transfer_volume_ul=split_config.split_source_transfer_volume_ul,
                    diluent_volume_ul=split_config.split_diluent_volume_ul,
                    normalization_mode=NormalizationMode.SPLIT_REQUIRED,
                    status=Status.SPLIT_CREATED,
                    generates_robot_transfer=True,
                    child_sample_id=child_sample_id,
                )
            )
            continue

        if sample.available_volume_ul <= standard_transfer:
            mode_exc = validate_mode_location_contract(sample, NormalizationMode.IN_PLACE)
            if mode_exc:
                exceptions.append(_with_batch(mode_exc, batch_id))
                rows.append(_invalid_row(batch_id, sample, target))
                continue
            derived_final_volume = source_concentration * sample.available_volume_ul / target_concentration
            in_place_diluent = derived_final_volume - sample.available_volume_ul
            if source_concentration <= target_concentration or in_place_diluent < 0:
                exceptions.append(
                    _sample_exception(
                        batch_id,
                        sample,
                        ExceptionCode.IN_PLACE_NORMALIZATION_INVALID,
                        "In-place normalization cannot dilute to the requested target.",
                        "Review target or exclude sample.",
                    )
                )
                rows.append(_invalid_row(batch_id, sample, target))
                continue
            if derived_final_volume > source_type.max_working_volume_ul:
                exceptions.append(
                    _sample_exception(
                        batch_id,
                        sample,
                        ExceptionCode.DESTINATION_VOLUME_EXCEEDED,
                        "Derived in-place final volume exceeds source container working volume.",
                        "Use a larger supported container or exclude sample.",
                    )
                )
                rows.append(_invalid_row(batch_id, sample, target))
                continue
            exceptions.append(
                ExceptionRecord(
                    exception_code=ExceptionCode.IN_PLACE_NORMALIZATION_SELECTED,
                    severity=ExceptionSeverity.INFO,
                    batch_id=batch_id,
                    sample_id=sample.sample_id,
                    source_container_id=sample.source_container_id,
                    source_well=sample.source_well,
                    message="In-place normalization selected because available volume is limited.",
                    suggested_action="Add diluent to source well only; skip sample transfer and mixing.",
                    blocks_robot_transfer=False,
                )
            )
            tracker.add(
                AncestryRecord(
                    child_sample_id=sample.sample_id,
                    event_type=AncestryEventType.NORMALIZED_IN_PLACE,
                    source_container_id=sample.source_container_id,
                    source_well=sample.source_well,
                    batch_id=batch_id,
                    workflow_type=workflow_type,
                )
            )
            rows.append(
                NormalizationPlanRow(
                    batch_id=batch_id,
                    sample_id=sample.sample_id,
                    source_container_id=sample.source_container_id,
                    source_well=sample.source_well,
                    destination_container_id=None,
                    destination_well=None,
                    source_concentration_ng_per_ul=source_concentration,
                    target_concentration_ng_per_ul=target_concentration,
                    target_final_volume_ul=derived_final_volume,
                    target_mass_ng=source_concentration * sample.available_volume_ul,
                    sample_transfer_volume_ul=0.0,
                    diluent_volume_ul=in_place_diluent,
                    normalization_mode=NormalizationMode.IN_PLACE,
                    status=Status.IN_PLACE_NORMALIZATION_SELECTED,
                    generates_robot_transfer=True,
                )
            )
            continue

        mode_exc = validate_mode_location_contract(sample, NormalizationMode.STANDARD_NEW_CONTAINER)
        if mode_exc:
            exceptions.append(_with_batch(mode_exc, batch_id))
            rows.append(_invalid_row(batch_id, sample, target))
            continue

        assert sample.destination_container_id is not None
        destination_type = _resolve_container_type_for_sample(
            registry,
            sample,
            batch_id=batch_id,
            container_id=sample.destination_container_id,
            source=False,
            exceptions=exceptions,
        )
        if destination_type is None:
            rows.append(_invalid_row(batch_id, sample, target))
            continue
        if target.target_final_volume_ul > destination_type.max_working_volume_ul:
            exceptions.append(
                _sample_exception(
                    batch_id,
                    sample,
                    ExceptionCode.DESTINATION_VOLUME_EXCEEDED,
                    "Target final volume exceeds destination container working volume.",
                    "Lower final volume or choose a supported destination container.",
                )
            )
            rows.append(_invalid_row(batch_id, sample, target))
            continue
        required_source = required_source_volume_ul(standard_transfer)
        if sample.available_volume_ul < required_source:
            exceptions.append(
                _sample_exception(
                    batch_id,
                    sample,
                    ExceptionCode.INSUFFICIENT_SOURCE_VOLUME,
                    (
                        "Available source volume is below sample transfer plus "
                        "2 uL dead volume plus 1 uL aspiration margin."
                    ),
                    "Use in-place normalization when eligible, re-quant, or exclude sample.",
                )
            )
            rows.append(_invalid_row(batch_id, sample, target))
            continue

        tracker.add(
            AncestryRecord(
                child_sample_id=sample.sample_id,
                event_type=AncestryEventType.NORMALIZED_STANDARD,
                source_container_id=sample.source_container_id,
                source_well=sample.source_well,
                destination_container_id=sample.destination_container_id,
                destination_well=sample.destination_well,
                batch_id=batch_id,
                workflow_type=workflow_type,
            )
        )
        rows.append(
            NormalizationPlanRow(
                batch_id=batch_id,
                sample_id=sample.sample_id,
                source_container_id=sample.source_container_id,
                source_well=sample.source_well,
                destination_container_id=sample.destination_container_id,
                destination_well=sample.destination_well,
                source_concentration_ng_per_ul=source_concentration,
                target_concentration_ng_per_ul=target_concentration,
                target_final_volume_ul=target.target_final_volume_ul,
                target_mass_ng=target.mass_ng,
                sample_transfer_volume_ul=standard_transfer,
                diluent_volume_ul=diluent_volume,
                normalization_mode=NormalizationMode.STANDARD_NEW_CONTAINER,
                status=Status.STANDARD_NORMALIZATION,
                generates_robot_transfer=True,
            )
        )

    return NormalizationPlanResult(
        rows=tuple(rows),
        exceptions=tuple(exceptions),
        ancestry_records=tracker.records,
    )


def process_normalization_config(config: NormalizationConfig) -> NormalizationPlanResult:
    loaded = read_normalization_sample_inputs(config.input_csv, analyte_type=config.analyte_type)
    planned = plan_normalization(
        batch_id=config.batch_id,
        workflow_type=config.workflow_type,
        samples=list(loaded.samples),
        target=config.target,
        registry=config.registry,
        split_config=config.split_config,
    )
    return NormalizationPlanResult(
        rows=planned.rows,
        exceptions=loaded.exceptions + planned.exceptions,
        ancestry_records=planned.ancestry_records,
    )


def write_normalization_outputs(
    result: NormalizationPlanResult,
    out_dir: Path,
    *,
    prefix: str = "",
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_name = f"{prefix}normalization_plan.csv" if prefix else "normalization_plan.csv"
    exception_name = f"{prefix}exception_report.csv" if prefix else "exception_report.csv"
    write_csv_rows(
        out_dir / plan_name,
        NORMALIZATION_PLAN_COLUMNS,
        [row.to_csv_row() for row in result.rows],
    )
    write_exception_report(out_dir / exception_name, result.exceptions)
    write_csv_rows(
        out_dir / "sample_ancestry.csv",
        ANCESTRY_COLUMNS,
        [record.to_row() for record in result.ancestry_records],
    )
    write_csv_rows(
        out_dir / "audit_manifest.csv",
        AUDIT_MANIFEST_COLUMNS,
        [
            {
                "batch_id": row.batch_id,
                "sample_id": row.sample_id,
                "event_type": row.status.value,
                "manual_override": "False",
                "auditable": "True",
                "message": "Synthetic deterministic planning event.",
            }
            for row in result.rows
        ],
    )


def _invalid_row(
    batch_id: str,
    sample: NormalizationSampleInput,
    target: NormalizationTarget,
) -> NormalizationPlanRow:
    return NormalizationPlanRow(
        batch_id=batch_id,
        sample_id=sample.sample_id,
        source_container_id=sample.source_container_id,
        source_well=sample.source_well,
        destination_container_id=sample.destination_container_id,
        destination_well=sample.destination_well,
        source_concentration_ng_per_ul=sample.stock_concentration_ng_per_ul,
        target_concentration_ng_per_ul=target.concentration_ng_per_ul,
        target_final_volume_ul=target.target_final_volume_ul,
        target_mass_ng=target.mass_ng,
        sample_transfer_volume_ul=0.0,
        diluent_volume_ul=0.0,
        normalization_mode=NormalizationMode.STANDARD_NEW_CONTAINER,
        status=Status.INVALID,
        generates_robot_transfer=False,
    )


def _resolve_container_type_for_sample(
    registry: ContainerRegistry,
    sample: NormalizationSampleInput,
    *,
    batch_id: str,
    container_id: str,
    source: bool,
    exceptions: list[ExceptionRecord],
) -> ContainerType | None:
    try:
        return registry.resolve_container_type_for_container(container_id)
    except KeyError:
        exceptions.append(
            ExceptionRecord(
                exception_code=(
                    ExceptionCode.INVALID_SOURCE_LOCATION
                    if source
                    else ExceptionCode.INVALID_DESTINATION_LOCATION
                ),
                severity=ExceptionSeverity.BLOCKING,
                batch_id=batch_id,
                sample_id=sample.sample_id,
                source_container_id=sample.source_container_id,
                source_well=sample.source_well,
                destination_container_id=None if source else container_id,
                destination_well=None if source else sample.destination_well,
                message=f"Unknown {'source' if source else 'destination'} container {container_id}.",
                suggested_action="Resolve the container barcode/type through the LIMS registry.",
                blocks_robot_transfer=True,
            )
        )
        return None


def _sample_exception(
    batch_id: str,
    sample: NormalizationSampleInput,
    code: ExceptionCode,
    message: str,
    action: str,
) -> ExceptionRecord:
    return ExceptionRecord(
        exception_code=code,
        severity=ExceptionSeverity.BLOCKING,
        batch_id=batch_id,
        sample_id=sample.sample_id,
        source_container_id=sample.source_container_id,
        source_well=sample.source_well,
        destination_container_id=sample.destination_container_id,
        destination_well=sample.destination_well,
        message=message,
        suggested_action=action,
        blocks_robot_transfer=True,
    )


def _with_batch(exception: ExceptionRecord, batch_id: str) -> ExceptionRecord:
    return exception.model_copy(update={"batch_id": batch_id})


def _parse_well_for_row(
    value: str,
    *,
    code: ExceptionCode,
    row_number: int,
    sample_id: str | None,
    source_container_id: str | None,
    exceptions: list[ExceptionRecord],
) -> WellCoordinate | None:
    if not value:
        return None
    try:
        return WellCoordinate.model_validate(value)
    except ValueError:
        exceptions.append(
            _ingest_exception(
                code=code,
                row_number=row_number,
                message=f"Invalid 96-well coordinate {value!r}.",
                action="Provide a source/destination well in A1-H12 format.",
                sample_id=sample_id,
                source_container_id=source_container_id,
                blocks_robot_transfer=True,
            )
        )
        return None


def _parse_required_float_for_row(
    value: str | None,
    *,
    missing_code: ExceptionCode,
    invalid_code: ExceptionCode,
    field_name: str,
    row_number: int,
    sample_id: str | None,
    source_container_id: str | None,
    exceptions: list[ExceptionRecord],
) -> float | None:
    if value is None or value == "":
        exceptions.append(
            _ingest_exception(
                code=missing_code,
                row_number=row_number,
                message=f"{field_name} is required.",
                action=f"Provide {field_name} before planning.",
                sample_id=sample_id,
                source_container_id=source_container_id,
                blocks_robot_transfer=True,
            )
        )
        return None
    try:
        return float(value)
    except ValueError:
        exceptions.append(
            _ingest_exception(
                code=invalid_code,
                row_number=row_number,
                message=f"{field_name} must be numeric.",
                action=f"Correct {field_name} before planning.",
                sample_id=sample_id,
                source_container_id=source_container_id,
                blocks_robot_transfer=True,
            )
        )
        return None


def _ingest_exception(
    *,
    code: ExceptionCode,
    row_number: int,
    message: str,
    action: str,
    sample_id: str | None,
    source_container_id: str | None,
    blocks_robot_transfer: bool,
) -> ExceptionRecord:
    return ExceptionRecord(
        exception_code=code,
        severity=ExceptionSeverity.BLOCKING,
        sample_id=sample_id,
        source_container_id=source_container_id,
        message=f"Input row {row_number}: {message}",
        suggested_action=action,
        blocks_robot_transfer=blocks_robot_transfer,
    )


def _fmt2(value: float) -> str:
    return f"{value:.2f}"


def _fmt4(value: float) -> str:
    return f"{value:.4f}"
