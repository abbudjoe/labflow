from __future__ import annotations

import json

import pytest

from labflow_core.domain.audit import AuditAction, AuditEvent
from labflow_core.domain.containers import (
    Container,
    ContainerType,
    matrix_96_1ml_rubber_septum_type,
    matrix_96_1ml_screwtop_type,
)
from labflow_core.domain.exceptions import ExceptionRecord
from labflow_core.domain.samples import NormalizationSampleInput
from labflow_core.domain.statuses import (
    AnalyteType,
    AncestryEventType,
    ExceptionCode,
    ExceptionSeverity,
    NormalizationMode,
    WorkflowType,
)
from labflow_core.domain.units import (
    DEFAULT_MAX_DESTINATION_VOLUME_UL,
    MINIMUM_TRANSFER_VOLUME_UL,
    ROBOT_ASPIRATION_SAFETY_MARGIN_UL,
    SOURCE_RESIDUAL_DEAD_VOLUME_UL,
    required_source_volume_ul,
)
from labflow_core.domain.wells import default_standard_wells, parse_well
from labflow_core.lims.ancestry import AncestryRecord, AncestryTracker
from labflow_core.lims.manifests import (
    validate_duplicate_manifest_rows,
    validate_mode_location_contract,
)
from labflow_core.lims.registry import ContainerRegistry


def test_valid_wells_parse_normalize_and_sort() -> None:
    assert str(parse_well("a1")) == "A1"
    assert str(parse_well("H12")) == "H12"
    assert sorted([parse_well("B1"), parse_well("A12"), parse_well("A1")]) == [
        parse_well("A1"),
        parse_well("A12"),
        parse_well("B1"),
    ]


@pytest.mark.parametrize("well", ["I1", "A13", "Z99", "1A", "AA1", ""])
def test_invalid_wells_raise(well: str) -> None:
    with pytest.raises(ValueError):
        parse_well(well)


def test_default_standard_well_order_is_a1_through_h1() -> None:
    assert [str(well) for well in default_standard_wells()] == [
        "A1",
        "B1",
        "C1",
        "D1",
        "E1",
        "F1",
        "G1",
        "H1",
    ]


def test_matrix_container_types_and_max_volume() -> None:
    screwtop = matrix_96_1ml_screwtop_type()
    septum = matrix_96_1ml_rubber_septum_type()
    assert screwtop.max_working_volume_ul == DEFAULT_MAX_DESTINATION_VOLUME_UL == 999.0
    assert screwtop.closure_type == "screw_top"
    assert septum.closure_type == "septum_or_rubber_top"
    assert screwtop.rows == 8
    assert screwtop.columns == 12
    with pytest.raises(ValueError):
        ContainerType(
            container_type_id="bad",
            name="Bad rack",
            format="96_well",
            rows=8,
            columns=12,
            nominal_capacity_ul=100.0,
            max_working_volume_ul=101.0,
            closure_type="synthetic",
        )


def test_required_source_volume_formula_uses_transfer_dead_volume_and_margin() -> None:
    assert MINIMUM_TRANSFER_VOLUME_UL == 1.0
    assert SOURCE_RESIDUAL_DEAD_VOLUME_UL == 2.0
    assert ROBOT_ASPIRATION_SAFETY_MARGIN_UL == 1.0
    assert required_source_volume_ul(12.5) == pytest.approx(15.5)


def test_container_registry_resolves_default_types_and_barcodes() -> None:
    registry = ContainerRegistry.with_defaults()
    source = registry.ensure_container("SRC001", "matrix_96_1ml_screwtop")
    destination = registry.ensure_container("DST001", "matrix_96_1ml_septum")
    assert source.barcode == "SRC001"
    assert registry.resolve_container_type_for_container("SRC001").closure_type == "screw_top"
    assert (
        registry.resolve_container_type_for_container(destination.barcode).closure_type
        == "septum_or_rubber_top"
    )
    with pytest.raises(KeyError):
        registry.resolve_type("missing")


def test_container_identifiers_reject_whitespace() -> None:
    with pytest.raises(ValueError):
        Container(
            container_id="   ",
            barcode="BC001",
            container_type_id="matrix_96_1ml_screwtop",
        )
    with pytest.raises(ValueError):
        Container(
            container_id="C001",
            barcode="   ",
            container_type_id="matrix_96_1ml_screwtop",
        )


def test_exception_record_serializes_batch_sample_locations_and_action() -> None:
    record = ExceptionRecord(
        exception_code=ExceptionCode.MISSING_CONCENTRATION,
        severity=ExceptionSeverity.BLOCKING,
        batch_id="BATCH-1",
        sample_id="S1",
        source_container_id="SRC",
        source_well="A1",
        destination_container_id="DST",
        destination_well="B1",
        message="Concentration is missing.",
        suggested_action="Repeat quantification or exclude the sample.",
        blocks_robot_transfer=True,
    )
    row = record.to_report_row()
    assert row["exception_code"] == "MISSING_CONCENTRATION"
    assert row["severity"] == "BLOCKING"
    assert row["batch_id"] == "BATCH-1"
    assert row["sample_id"] == "S1"
    assert row["source_well"] == "A1"
    assert row["destination_well"] == "B1"
    assert row["suggested_action"] == "Repeat quantification or exclude the sample."
    assert record.recommended_action == record.suggested_action
    assert row["blocks_robot_transfer"] is True


def test_ancestry_parent_child_record_by_sample_id() -> None:
    tracker = AncestryTracker()
    record = tracker.record_split(
        parent_sample_id="S1",
        child_sample_id="S1-SPLIT1",
        source_container_id="SRC",
        source_well=parse_well("A1"),
        destination_container_id="DST",
        destination_well=parse_well("B1"),
        batch_id="BATCH-1",
        workflow_type=WorkflowType.DNA_NORMALIZATION,
        expected_child_concentration_ng_per_ul=10.1234567,
    )
    row = record.to_row()
    assert record.parent_sample_id == "S1"
    assert record.child_sample_id == "S1-SPLIT1"
    assert row["source_well"] == "A1"
    assert row["destination_well"] == "B1"
    assert json.loads(record.metadata_json) == {
        "expected_child_concentration_ng_per_ul": 10.123457,
        "requires_requant": True,
    }
    assert tracker.records == (record,)


def test_ancestry_required_identifiers_reject_whitespace() -> None:
    with pytest.raises(ValueError):
        AncestryRecord(
            child_sample_id="   ",
            event_type=AncestryEventType.NORMALIZED_STANDARD,
            batch_id="BATCH-1",
            workflow_type=WorkflowType.DNA_NORMALIZATION,
        )
    with pytest.raises(ValueError):
        AncestryRecord(
            child_sample_id="S1",
            event_type=AncestryEventType.NORMALIZED_STANDARD,
            batch_id="   ",
            workflow_type=WorkflowType.DNA_NORMALIZATION,
        )


def test_duplicate_manifest_validation_flags_all_duplicate_policies() -> None:
    rows = [
        NormalizationSampleInput(
            sample_id="S1",
            analyte_type=AnalyteType.DS_DNA,
            source_container_id="SRC",
            source_well="A1",
            stock_concentration_ng_per_ul=10,
            available_volume_ul=20,
            destination_container_id="DST",
            destination_well="B1",
        ),
        NormalizationSampleInput(
            sample_id="S1",
            analyte_type=AnalyteType.DS_DNA,
            source_container_id="SRC",
            source_well="A1",
            stock_concentration_ng_per_ul=10,
            available_volume_ul=20,
            destination_container_id="DST",
            destination_well="B1",
        ),
    ]
    exceptions = validate_duplicate_manifest_rows(rows, batch_id="BATCH-1")
    codes = {exception.exception_code for exception in exceptions}
    assert ExceptionCode.DUPLICATE_SAMPLE_ID in codes
    assert ExceptionCode.DUPLICATE_SOURCE_LOCATION in codes
    assert ExceptionCode.DUPLICATE_DESTINATION_LOCATION in codes
    assert {exception.batch_id for exception in exceptions} == {"BATCH-1"}
    assert all(exception.blocks_robot_transfer for exception in exceptions)


def test_whitespace_location_identifiers_are_missing_not_valid_locations() -> None:
    with pytest.raises(ValueError):
        NormalizationSampleInput(
            sample_id="S1",
            analyte_type=AnalyteType.DS_DNA,
            source_container_id="   ",
            source_well="A1",
            stock_concentration_ng_per_ul=10,
            available_volume_ul=20,
            destination_container_id="DST",
            destination_well="B1",
        )

    row = NormalizationSampleInput(
        sample_id="S1",
        analyte_type=AnalyteType.DS_DNA,
        source_container_id="SRC",
        source_well="A1",
        stock_concentration_ng_per_ul=10,
        available_volume_ul=20,
        destination_container_id="   ",
        destination_well="B1",
    )
    assert row.destination_container_id is None
    exception = validate_mode_location_contract(row, NormalizationMode.STANDARD_NEW_CONTAINER)
    assert exception is not None
    assert exception.exception_code is ExceptionCode.MISSING_DESTINATION_LOCATION


def test_audit_event_is_structured_and_deterministic() -> None:
    event = AuditEvent(
        event_id="AUDIT-1",
        action=AuditAction.DRY_RUN,
        actor="developer",
        entity_type="batch",
        entity_id="BATCH-1",
        batch_id="BATCH-1",
        dry_run=True,
        metadata={"tool": "validate_batch"},
    )
    row = event.to_row()
    assert row["event_id"] == "AUDIT-1"
    assert row["action"] == "DRY_RUN"
    assert row["dry_run"] is True
    assert row["approved"] is False
    assert row["created_at"] == "2026-01-01T00:00:00+00:00"
    assert row["metadata_json"] == '{"tool": "validate_batch"}'
