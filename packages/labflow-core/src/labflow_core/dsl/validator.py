"""Deterministic domain validation for LabFlow workflow DSL files."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from labflow_core.domain.units import (
    DEFAULT_MAX_DESTINATION_VOLUME_UL,
    MINIMUM_TRANSFER_VOLUME_UL,
    ROBOT_ASPIRATION_SAFETY_MARGIN_UL,
    SOURCE_RESIDUAL_DEAD_VOLUME_UL,
)
from labflow_core.domain.wells import default_standard_wells, parse_well
from labflow_core.dsl.diagnostics import (
    DiagnosticCode,
    DiagnosticSource,
    WorkflowDiagnostic,
)
from labflow_core.dsl.models import LabFlowWorkflow, SampleConfig, WorkflowKind
from labflow_core.dsl.parser import parse_workflow_file, parse_workflow_text


@dataclass(frozen=True)
class WorkflowValidationResult:
    workflow: LabFlowWorkflow | None
    diagnostics: tuple[WorkflowDiagnostic, ...]

    @property
    def valid(self) -> bool:
        return self.workflow is not None and not self.diagnostics


def validate_workflow_file(path: Path) -> WorkflowValidationResult:
    parsed = parse_workflow_file(path)
    if parsed.workflow is None:
        return WorkflowValidationResult(workflow=None, diagnostics=parsed.diagnostics)
    return validate_workflow(parsed.workflow)


def validate_workflow_text(text: str) -> WorkflowValidationResult:
    parsed = parse_workflow_text(text)
    if parsed.workflow is None:
        return WorkflowValidationResult(workflow=None, diagnostics=parsed.diagnostics)
    return validate_workflow(parsed.workflow)


def validate_workflow(workflow: LabFlowWorkflow) -> WorkflowValidationResult:
    diagnostics: list[WorkflowDiagnostic] = []
    _validate_batch(workflow, diagnostics)
    _validate_standards(workflow, diagnostics)
    _validate_normalization(workflow, diagnostics)
    _validate_requant(workflow, diagnostics)
    _validate_samples(workflow, diagnostics)
    _validate_janus_block(workflow, diagnostics)
    return WorkflowValidationResult(workflow=workflow, diagnostics=tuple(diagnostics))


def _validate_batch(
    workflow: LabFlowWorkflow,
    diagnostics: list[WorkflowDiagnostic],
) -> None:
    batch = workflow.batch
    if batch.plate_format != 96:
        diagnostics.append(
            _domain_error(
                code=DiagnosticCode.INVALID_SAMPLE_PLATE_LAYOUT,
                message="LabFlow v0.1 supports only 96-well plates.",
                path="batch.plate_format",
                action="Set plate_format to 96.",
            )
        )
    if batch.samples_per_plate != 95:
        diagnostics.append(
            _domain_error(
                code=DiagnosticCode.INVALID_SAMPLE_PLATE_LAYOUT,
                message="Sample plates must contain exactly 95 samples plus one blank.",
                path="batch.samples_per_plate",
                action="Set samples_per_plate to 95 and reserve one well for the blank.",
            )
        )
    if batch.blank_well is None:
        diagnostics.append(
            _domain_error(
                code=DiagnosticCode.MISSING_PLATE_BLANK,
                message=f"Batch {batch.batch_id} is missing required sample-plate blank well.",
                path="batch.blank_well",
                action="Add blank_well, for example H12.",
            )
        )
        return
    _append_invalid_well_if_needed(batch.blank_well, "batch.blank_well", diagnostics)


def _validate_standards(
    workflow: LabFlowWorkflow,
    diagnostics: list[WorkflowDiagnostic],
) -> None:
    standards = workflow.standards
    if standards is None or not standards.wells:
        diagnostics.append(
            _domain_error(
                code=DiagnosticCode.MISSING_BATCH_STANDARD_CURVE,
                message="Workflow is missing the required batch standards plate.",
                path="standards",
                action="Define standards.wells for the eight A1-H1 batch standards.",
            )
        )
        return
    if standards.curve_model != "linear":
        diagnostics.append(
            _domain_error(
                code=DiagnosticCode.INVALID_BATCH_STANDARD_CURVE,
                message="Only linear standard curves are supported in v0.1.",
                path="standards.curve_model",
                action="Set standards.curve_model to linear.",
            )
        )

    expected = {str(well) for well in default_standard_wells()}
    configured_by_canonical: dict[str, list[str]] = {}
    present_standard_wells: set[str] = set()
    for raw_well, standard_id in standards.wells.items():
        canonical = _canonical_well(raw_well)
        if canonical is None:
            diagnostics.append(
                _domain_error(
                    code=DiagnosticCode.INVALID_WELL,
                    message=f"Standard well {raw_well} is not a valid A1-H12 coordinate.",
                    path=f"standards.wells.{raw_well}",
                    action="Use valid 96-well coordinates A1-H12.",
                )
            )
            continue
        configured_by_canonical.setdefault(canonical, []).append(raw_well)
        if standard_id.strip():
            present_standard_wells.add(canonical)
        else:
            diagnostics.append(
                _domain_error(
                    code=DiagnosticCode.MISSING_BATCH_STANDARD_CURVE,
                    message=f"Standard well {canonical} is missing a standard identifier.",
                    path=f"standards.wells.{raw_well}",
                    action="Provide a nonblank synthetic standard ID for each A1-H1 standard.",
                )
            )

    for canonical, raw_wells in sorted(
        configured_by_canonical.items(),
        key=lambda item: parse_well(item[0]).sort_key,
    ):
        if len(raw_wells) <= 1:
            continue
        diagnostics.append(
            _domain_error(
                code=DiagnosticCode.INVALID_BATCH_STANDARD_CURVE,
                message=(
                    f"Standard well {canonical} is configured more than once "
                    f"as {', '.join(raw_wells)}."
                ),
                path="standards.wells",
                action="Define each A1-H1 standard well exactly once.",
            )
        )
    missing = sorted(
        expected - present_standard_wells,
        key=lambda well: parse_well(well).sort_key,
    )
    if missing:
        diagnostics.append(
            _domain_error(
                code=DiagnosticCode.MISSING_BATCH_STANDARD_CURVE,
                message=f"Missing required standard wells: {', '.join(missing)}.",
                path="standards.wells",
                action="Define exactly the eight standards in wells A1-H1.",
            )
        )
    extra = sorted(
        set(configured_by_canonical) - expected,
        key=lambda well: parse_well(well).sort_key,
    )
    if extra:
        diagnostics.append(
            _domain_error(
                code=DiagnosticCode.INVALID_BATCH_STANDARD_CURVE,
                message=f"Standards include wells outside A1-H1: {', '.join(extra)}.",
                path="standards.wells",
                action="Use exactly the eight standards in wells A1-H1.",
            )
        )


def _validate_normalization(
    workflow: LabFlowWorkflow,
    diagnostics: list[WorkflowDiagnostic],
) -> None:
    if workflow.workflow.type is WorkflowKind.DNA_QUANT:
        return
    normalization = workflow.normalization
    if normalization is None:
        diagnostics.append(
            _domain_error(
                code=DiagnosticCode.REQUIRED_ARTIFACT_MISSING,
                message="Normalization workflow is missing normalization settings.",
                path="normalization",
                action="Add target concentration or mass with a final volume.",
            )
        )
        return
    unsupported = normalization.unsupported_molar_fields
    if unsupported:
        diagnostics.append(
            _domain_error(
                code=DiagnosticCode.MOLAR_TARGET_NOT_SUPPORTED,
                message=f"Molar target fields are not supported: {', '.join(unsupported)}.",
                path="normalization",
                action="Use only ng_per_ul, ul, and ng target fields.",
            )
        )
    if normalization.target_final_volume_ul is None:
        diagnostics.append(
            _domain_error(
                code=DiagnosticCode.REQUIRED_ARTIFACT_MISSING,
                message="Normalization target_final_volume_ul is required.",
                path="normalization.target_final_volume_ul",
                action="Provide a final volume in ul.",
            )
        )
    elif normalization.target_final_volume_ul > DEFAULT_MAX_DESTINATION_VOLUME_UL:
        diagnostics.append(
            _domain_error(
                code=DiagnosticCode.INVALID_SAMPLE_PLATE_LAYOUT,
                message="Target final volume exceeds the 999 ul Matrix tube working volume.",
                path="normalization.target_final_volume_ul",
                action="Use a target final volume at or below 999 ul.",
            )
        )
    has_concentration = normalization.target_concentration_ng_per_ul is not None
    has_mass = normalization.target_mass_ng is not None
    if has_concentration == has_mass:
        diagnostics.append(
            _domain_error(
                code=DiagnosticCode.REQUIRED_ARTIFACT_MISSING,
                message="Provide exactly one target mode: concentration plus volume or mass plus volume.",
                path="normalization",
                action="Set one of target_concentration_ng_per_ul or target_mass_ng.",
            )
        )
    if normalization.minimum_transfer_volume_ul != MINIMUM_TRANSFER_VOLUME_UL:
        diagnostics.append(
            _domain_error(
                code=DiagnosticCode.REQUIRED_ARTIFACT_MISSING,
                message="minimum_transfer_volume_ul must remain 1 ul for v0.1.",
                path="normalization.minimum_transfer_volume_ul",
                action="Set minimum_transfer_volume_ul to 1.",
            )
        )
    if normalization.source_residual_dead_volume_ul != SOURCE_RESIDUAL_DEAD_VOLUME_UL:
        diagnostics.append(
            _domain_error(
                code=DiagnosticCode.REQUIRED_ARTIFACT_MISSING,
                message="source_residual_dead_volume_ul must remain 2 ul for v0.1.",
                path="normalization.source_residual_dead_volume_ul",
                action="Set source_residual_dead_volume_ul to 2.",
            )
        )
    if normalization.robot_aspiration_safety_margin_ul != ROBOT_ASPIRATION_SAFETY_MARGIN_UL:
        diagnostics.append(
            _domain_error(
                code=DiagnosticCode.REQUIRED_ARTIFACT_MISSING,
                message="robot_aspiration_safety_margin_ul must remain 1 ul for v0.1.",
                path="normalization.robot_aspiration_safety_margin_ul",
                action="Set robot_aspiration_safety_margin_ul to 1.",
            )
        )


def _validate_requant(
    workflow: LabFlowWorkflow,
    diagnostics: list[WorkflowDiagnostic],
) -> None:
    if workflow.workflow.type is not WorkflowKind.RNA_NORM_REQUANT:
        return
    if workflow.requant is None:
        diagnostics.append(
            _domain_error(
                code=DiagnosticCode.REQUIRED_ARTIFACT_MISSING,
                message="RNA normalization + re-quant workflow requires requant settings.",
                path="requant",
                action="Add requant assay and result_handling configuration.",
            )
        )
        return
    if workflow.requant.assay != "RiboGreen":
        diagnostics.append(
            _domain_error(
                code=DiagnosticCode.REQUIRED_ARTIFACT_MISSING,
                message="RNA re-quant assay must be RiboGreen in v0.1.",
                path="requant.assay",
                action="Set requant.assay to RiboGreen.",
            )
        )
    if workflow.requant.result_handling != "use_as_downstream_concentration":
        diagnostics.append(
            _domain_error(
                code=DiagnosticCode.REQUIRED_ARTIFACT_MISSING,
                message="RNA re-quant results must become downstream concentration.",
                path="requant.result_handling",
                action="Set result_handling to use_as_downstream_concentration.",
            )
        )


def _validate_samples(
    workflow: LabFlowWorkflow,
    diagnostics: list[WorkflowDiagnostic],
) -> None:
    for index, sample in enumerate(workflow.samples):
        sample_path = f"samples.{index}"
        _append_invalid_well_if_needed(sample.source_well, f"{sample_path}.source_well", diagnostics)
        if sample.destination_well is not None:
            _append_invalid_well_if_needed(
                sample.destination_well,
                f"{sample_path}.destination_well",
                diagnostics,
            )
        if (
            workflow.workflow.type is not WorkflowKind.DNA_QUANT
            and sample.stock_concentration_ng_per_ul is None
        ):
            diagnostics.append(
                _domain_error(
                    code=DiagnosticCode.MISSING_CONCENTRATION,
                    message=f"Sample {sample.sample_id} is missing stock concentration.",
                    path=f"{sample_path}.stock_concentration_ng_per_ul",
                    action="Provide stock_concentration_ng_per_ul from deterministic quantification.",
                )
            )
        if workflow.workflow.type is not WorkflowKind.DNA_QUANT:
            if (
                (sample.destination_container_id is None or sample.destination_well is None)
                and not _is_in_place_eligible(workflow, sample)
            ):
                diagnostics.append(
                    _domain_error(
                        code=DiagnosticCode.MISSING_DESTINATION_LOCATION,
                        message=f"Sample {sample.sample_id} is missing destination location.",
                        path=sample_path,
                        action="Assign destination_container_id and destination_well.",
                    )
                )
    _append_duplicate_sample_locations(workflow.samples, diagnostics)


def _is_in_place_eligible(workflow: LabFlowWorkflow, sample: SampleConfig) -> bool:
    normalization = workflow.normalization
    if normalization is None:
        return False
    if sample.destination_container_id is not None or sample.destination_well is not None:
        return False
    if (
        sample.stock_concentration_ng_per_ul is None
        or sample.available_volume_ul is None
        or normalization.target_final_volume_ul is None
    ):
        return False
    if normalization.target_concentration_ng_per_ul is not None:
        target_concentration = normalization.target_concentration_ng_per_ul
    elif normalization.target_mass_ng is not None:
        target_concentration = normalization.target_mass_ng / normalization.target_final_volume_ul
    else:
        return False
    standard_transfer = (
        target_concentration
        * normalization.target_final_volume_ul
        / sample.stock_concentration_ng_per_ul
    )
    return sample.available_volume_ul <= standard_transfer


def _append_duplicate_sample_locations(
    samples: tuple[SampleConfig, ...],
    diagnostics: list[WorkflowDiagnostic],
) -> None:
    source_counts = Counter(
        (sample.source_container_id, source_well)
        for sample in samples
        if (source_well := _canonical_well(sample.source_well)) is not None
    )
    destination_counts = Counter(
        (sample.destination_container_id, destination_well)
        for sample in samples
        if sample.destination_container_id
        and sample.destination_well
        and (destination_well := _canonical_well(sample.destination_well)) is not None
    )
    for index, sample in enumerate(samples):
        source_well = _canonical_well(sample.source_well)
        if source_well is not None and source_counts[(sample.source_container_id, source_well)] > 1:
            diagnostics.append(
                _domain_error(
                    code=DiagnosticCode.DUPLICATE_SOURCE_LOCATION,
                    message=(
                        f"Duplicate source location "
                        f"{sample.source_container_id}:{source_well}."
                    ),
                    path=f"samples.{index}.source_well",
                    action="Assign each source well to at most one sample.",
                )
            )
        if sample.destination_container_id and sample.destination_well:
            destination_well = _canonical_well(sample.destination_well)
            if (
                destination_well is not None
                and destination_counts[(sample.destination_container_id, destination_well)] > 1
            ):
                diagnostics.append(
                    _domain_error(
                        code=DiagnosticCode.DUPLICATE_DESTINATION_LOCATION,
                        message=(
                            "Duplicate destination location "
                            f"{sample.destination_container_id}:{destination_well}."
                        ),
                        path=f"samples.{index}.destination_well",
                        action="Assign each destination well to at most one transfer.",
                    )
                )


def _validate_janus_block(
    workflow: LabFlowWorkflow,
    diagnostics: list[WorkflowDiagnostic],
) -> None:
    if not workflow.outputs.janus or not diagnostics:
        return
    diagnostics.append(
        _domain_error(
            code=DiagnosticCode.JANUS_BLOCKED_FOR_INVALID_BATCH,
            message="JANUS output is blocked because the workflow has validation errors.",
            path="outputs.janus",
            action="Resolve blocking diagnostics before requesting JANUS generation.",
        )
    )


def _append_invalid_well_if_needed(
    well: str,
    path: str,
    diagnostics: list[WorkflowDiagnostic],
) -> None:
    if _is_invalid_well(well):
        diagnostics.append(
            _domain_error(
                code=DiagnosticCode.INVALID_WELL,
                message=f"Well {well} is not a valid A1-H12 coordinate.",
                path=path,
                action="Use valid 96-well coordinates A1-H12.",
            )
        )


def _is_invalid_well(well: str) -> bool:
    return _canonical_well(well) is None


def _canonical_well(well: str) -> str | None:
    try:
        return str(parse_well(well))
    except ValueError:
        return None


def _domain_error(
    *,
    code: DiagnosticCode,
    message: str,
    path: str,
    action: str,
) -> WorkflowDiagnostic:
    return WorkflowDiagnostic.error(
        code=code,
        message=message,
        path=path,
        source=DiagnosticSource.DOMAIN_VALIDATOR,
        suggested_action=action,
    )
