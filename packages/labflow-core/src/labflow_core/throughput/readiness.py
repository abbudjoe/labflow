"""Deterministic batch readiness gates."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class BatchReadinessInputs(BaseModel):
    model_config = ConfigDict(frozen=True)

    all_required_samples_have_concentrations: bool
    all_source_locations_valid: bool
    all_destination_locations_assigned: bool
    all_transfer_volumes_valid: bool
    all_exceptions_resolved_or_excluded: bool
    required_controls_present: bool
    required_reagents_defined: bool
    lims_batch_id_assigned: bool
    output_manifest_generated: bool
    operator_instructions_generated: bool
    robot_protocol_or_worklist_generated: bool


class BatchReadinessResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    robot_ready: bool
    blocking_gates: tuple[str, ...]


READINESS_FIELDS = tuple(BatchReadinessInputs.model_fields)


def evaluate_batch_readiness(inputs: BatchReadinessInputs) -> BatchReadinessResult:
    data = inputs.model_dump()
    blocking = tuple(field for field in READINESS_FIELDS if not data[field])
    return BatchReadinessResult(robot_ready=not blocking, blocking_gates=blocking)
