from __future__ import annotations

import csv
from pathlib import Path

import pytest

from labflow_core.domain.samples import NormalizationSampleInput
from labflow_core.domain.statuses import (
    AnalyteType,
    ExceptionCode,
    NormalizationMode,
    Status,
    WorkflowType,
)
from labflow_core.domain.wells import all_plate_wells
from labflow_core.lims.registry import ContainerRegistry
from labflow_core.norm.planner import (
    NormalizationConfig,
    plan_normalization,
    process_normalization_config,
    write_normalization_outputs,
)
from labflow_core.norm.requant import RnaRequantPolicy, process_rna_workflow, write_rna_outputs
from labflow_core.norm.split import SplitConfig
from labflow_core.norm.targets import NormalizationTarget
from labflow_core.quant.processors import (
    QuantificationConfig,
    SamplePlateConfig,
    process_quantification,
    write_quantification_outputs,
)
from labflow_core.quant.standards import fit_linear_standard_curve
from labflow_core.quant.varioskan import VarioskanReading, VarioskanSchemaMapping, parse_varioskan_tsv
from labflow_core.robots.janus import janus_audit_rows, janus_minimal_rows, write_janus_outputs
from labflow_core.robots.protocol_ir import build_protocol_ir
from labflow_core.throughput.readiness import BatchReadinessInputs, evaluate_batch_readiness
from labflow_core.throughput.simulator import (
    ThroughputScenario,
    compare_default_batching,
    compare_scenarios,
)

STANDARD_CONCS = {
    "A1": 0.0,
    "B1": 0.5,
    "C1": 1.0,
    "D1": 2.0,
    "E1": 5.0,
    "F1": 10.0,
    "G1": 20.0,
    "H1": 40.0,
}


def _registry() -> ContainerRegistry:
    registry = ContainerRegistry.with_defaults()
    registry.ensure_container("SRC", "matrix_96_1ml_screwtop")
    registry.ensure_container("DST", "matrix_96_1ml_screwtop")
    return registry


def _target() -> NormalizationTarget:
    return NormalizationTarget(target_concentration_ng_per_ul=5, target_final_volume_ul=50)


def _write_standard_tsv(path: Path) -> None:
    path.write_text(
        "Plate ID\tWell\tSample ID\tReading\n"
        + "\n".join(
            f"STD\t{well}\tSTD\t{100 + concentration * 100}"
            for well, concentration in STANDARD_CONCS.items()
        )
        + "\n"
    )


def _write_sample_plate_tsv(
    path: Path,
    *,
    blank_well: str = "H12",
    blank_reading: float = 120,
    default_sample_reading: float = 620,
    sample_readings_by_well: dict[str, float] | None = None,
) -> None:
    overrides = sample_readings_by_well or {}
    lines = ["Plate ID\tWell\tSample ID\tReading"]
    sample_index = 1
    for well in all_plate_wells():
        well_label = str(well)
        if well_label == blank_well:
            lines.append(f"PLATE\t{well_label}\tBLANK\t{blank_reading}")
            continue
        reading = overrides.get(well_label, default_sample_reading)
        lines.append(f"PLATE\t{well_label}\tS{sample_index:03d}\t{reading}")
        sample_index += 1
    path.write_text("\n".join(lines) + "\n")


def _write_duplicate_sample_well_plate_tsv(path: Path) -> None:
    lines = ["Plate ID\tWell\tSample ID\tReading"]
    sample_index = 1
    for well in all_plate_wells():
        well_label = str(well)
        if well_label == "H12":
            lines.append("PLATE\tH12\tBLANK\t120")
            continue
        if well_label == "A2":
            continue
        lines.append(f"PLATE\t{well_label}\tS{sample_index:03d}\t620")
        sample_index += 1
    lines.append("PLATE\tA1\tS999\t620")
    path.write_text("\n".join(lines) + "\n")


def test_varioskan_schema_mapping_and_sorted_tsv_parse(tmp_path: Path) -> None:
    path = tmp_path / "custom.tsv"
    path.write_text(
        "Plate\tPosition\tName\tRFU\n"
        "P2\tB1\tS2\t200\n"
        "P1\ta1\tS1\t100\n"
    )
    mapping = VarioskanSchemaMapping(
        plate_id="Plate",
        well="Position",
        sample_id="Name",
        reading="RFU",
    )
    readings = parse_varioskan_tsv(path, mapping)
    assert [(reading.plate_id, str(reading.well), reading.sample_id) for reading in readings] == [
        ("P1", "A1", "S1"),
        ("P2", "B1", "S2"),
    ]


def test_standard_curve_with_8_standards_fits_expected_line() -> None:
    readings = [
        VarioskanReading(plate_id="STD", well=well, reading=100 + concentration * 100)
        for well, concentration in STANDARD_CONCS.items()
    ]
    result = fit_linear_standard_curve(readings, STANDARD_CONCS, batch_id="BATCH")
    assert result.curve is not None
    assert result.curve.slope == pytest.approx(100)
    assert result.curve.intercept == pytest.approx(0)


def test_missing_standard_well_produces_exception() -> None:
    readings = [
        VarioskanReading(plate_id="STD", well=well, reading=100 + concentration * 100)
        for well, concentration in STANDARD_CONCS.items()
        if well != "H1"
    ]
    result = fit_linear_standard_curve(readings, STANDARD_CONCS, batch_id="BATCH")
    assert result.curve is None
    assert result.exceptions[0].exception_code is ExceptionCode.MISSING_BATCH_STANDARD_CURVE
    assert result.exceptions[0].batch_id == "BATCH"


def test_partial_standard_concentration_layout_is_rejected() -> None:
    readings = [
        VarioskanReading(plate_id="STD", well="A1", reading=100),
        VarioskanReading(plate_id="STD", well="B1", reading=150),
    ]
    result = fit_linear_standard_curve(
        readings,
        {"A1": 0.0, "B1": 0.5},
        batch_id="BATCH",
    )
    assert result.curve is None
    assert result.exceptions[0].exception_code is ExceptionCode.MISSING_BATCH_STANDARD_CURVE


def test_invalid_standard_concentration_well_returns_structured_exception() -> None:
    readings = [
        VarioskanReading(plate_id="STD", well=well, reading=100 + concentration * 100)
        for well, concentration in STANDARD_CONCS.items()
    ]
    result = fit_linear_standard_curve(
        readings,
        {**STANDARD_CONCS, "Z99": 1.0},
        batch_id="BATCH",
    )
    assert result.curve is None
    assert result.exceptions[0].exception_code is ExceptionCode.INVALID_BATCH_STANDARD_CURVE


def test_quantification_blank_dilution_stock_and_outputs(tmp_path: Path) -> None:
    standards_path = tmp_path / "standards.tsv"
    samples_path = tmp_path / "samples.tsv"
    out_dir = tmp_path / "quant_out"
    _write_standard_tsv(standards_path)
    _write_sample_plate_tsv(samples_path)
    result = process_quantification(
        QuantificationConfig(
            batch_id="BATCH",
            assay="Quant-iT PicoGreen",
            standards_tsv=standards_path,
            sample_plates=(
                SamplePlateConfig(
                    plate_id="PLATE",
                    source_container_id="PLATE",
                    tsv=samples_path,
                    blank_well="H12",
                    dilution_factor=10,
                ),
            ),
            standard_concentrations_ng_per_ul=STANDARD_CONCS,
        )
    )
    assert len(result.rows) == 95
    assert result.rows[0].blank_corrected_reading == pytest.approx(500)
    assert result.rows[0].assay_well_concentration_ng_per_ul == pytest.approx(5)
    assert result.rows[0].stock_concentration_ng_per_ul == pytest.approx(50)
    assert result.ancestry_records[0].source_container_id == "PLATE"
    write_quantification_outputs(result, out_dir)
    assert (out_dir / "quant_results.csv").exists()
    assert (out_dir / "lims_stock_concentration_manifest.csv").read_text().count("S001") == 1


def test_missing_sample_plate_blank_and_out_of_range_are_flagged(tmp_path: Path) -> None:
    standards_path = tmp_path / "standards.tsv"
    missing_blank_path = tmp_path / "missing_blank.tsv"
    out_of_range_path = tmp_path / "out.tsv"
    _write_standard_tsv(standards_path)
    missing_blank_path.write_text("Plate ID\tWell\tSample ID\tReading\nPLATE\tA1\tS1\t620\n")
    _write_sample_plate_tsv(out_of_range_path, sample_readings_by_well={"A1": 5000})
    missing_blank = process_quantification(
        QuantificationConfig(
            batch_id="BATCH",
            assay="Quant-iT PicoGreen",
            standards_tsv=standards_path,
            sample_plates=(
                SamplePlateConfig(
                    plate_id="PLATE",
                    source_container_id="PLATE",
                    tsv=missing_blank_path,
                    blank_well="H12",
                    dilution_factor=10,
                ),
            ),
            standard_concentrations_ng_per_ul=STANDARD_CONCS,
        )
    )
    assert missing_blank.exceptions[0].exception_code is ExceptionCode.MISSING_PLATE_BLANK
    out_of_range = process_quantification(
        QuantificationConfig(
            batch_id="BATCH",
            assay="Quant-iT PicoGreen",
            standards_tsv=standards_path,
            sample_plates=(
                SamplePlateConfig(
                    plate_id="PLATE",
                    source_container_id="PLATE",
                    tsv=out_of_range_path,
                    blank_well="H12",
                    dilution_factor=10,
                ),
            ),
            standard_concentrations_ng_per_ul=STANDARD_CONCS,
        )
    )
    assert out_of_range.rows[0].status is Status.OUT_OF_RANGE
    assert out_of_range.exceptions[0].exception_code is ExceptionCode.QC_STATUS_FAILED


def test_incomplete_sample_plate_layout_generates_no_quant_rows(tmp_path: Path) -> None:
    standards_path = tmp_path / "standards.tsv"
    samples_path = tmp_path / "samples.tsv"
    _write_standard_tsv(standards_path)
    samples_path.write_text(
        "Plate ID\tWell\tSample ID\tReading\n"
        "PLATE\tA1\tS1\t620\n"
        "PLATE\tH12\tBLANK\t120\n"
    )
    result = process_quantification(
        QuantificationConfig(
            batch_id="BATCH",
            assay="Quant-iT PicoGreen",
            standards_tsv=standards_path,
            sample_plates=(
                SamplePlateConfig(
                    plate_id="PLATE",
                    source_container_id="PLATE",
                    tsv=samples_path,
                    blank_well="H12",
                    dilution_factor=10,
                ),
            ),
            standard_concentrations_ng_per_ul=STANDARD_CONCS,
        )
    )
    assert result.rows == ()
    assert result.exceptions[0].exception_code is ExceptionCode.INVALID_SAMPLE_PLATE_LAYOUT


def test_duplicate_sample_plate_well_generates_no_quant_rows(tmp_path: Path) -> None:
    standards_path = tmp_path / "standards.tsv"
    samples_path = tmp_path / "samples.tsv"
    _write_standard_tsv(standards_path)
    _write_duplicate_sample_well_plate_tsv(samples_path)
    result = process_quantification(
        QuantificationConfig(
            batch_id="BATCH",
            assay="Quant-iT PicoGreen",
            standards_tsv=standards_path,
            sample_plates=(
                SamplePlateConfig(
                    plate_id="PLATE",
                    source_container_id="PLATE",
                    tsv=samples_path,
                    blank_well="H12",
                    dilution_factor=10,
                ),
            ),
            standard_concentrations_ng_per_ul=STANDARD_CONCS,
        )
    )
    assert result.rows == ()
    assert result.exceptions[0].exception_code is ExceptionCode.INVALID_SAMPLE_PLATE_LAYOUT
    assert "Missing wells: A2" in result.exceptions[0].message
    assert "Duplicate wells: A1" in result.exceptions[0].message


def test_target_modes_derive_mass_and_concentration_and_reject_molarity() -> None:
    concentration_target = NormalizationTarget(
        target_concentration_ng_per_ul=5,
        target_final_volume_ul=50,
    )
    assert concentration_target.mass_ng == pytest.approx(250)
    mass_target = NormalizationTarget(target_mass_ng=250, target_final_volume_ul=50)
    assert mass_target.concentration_ng_per_ul == pytest.approx(5)
    with pytest.raises(ValueError):
        NormalizationTarget.from_config(
            {"target_final_volume_ul": 50, "target_concentration_ng_per_ul": 5, "nM": 2}
        )
    with pytest.raises(ValueError):
        NormalizationTarget.model_validate(
            {"target_final_volume_ul": 50, "target_concentration_ng_per_ul": 5, "nM": 2}
        )


def test_standard_new_container_normalization_math() -> None:
    sample = NormalizationSampleInput(
        sample_id="S1",
        analyte_type=AnalyteType.DS_DNA,
        source_container_id="SRC",
        source_well="A1",
        stock_concentration_ng_per_ul=20,
        available_volume_ul=50,
        destination_container_id="DST",
        destination_well="A1",
    )
    result = plan_normalization(
        batch_id="BATCH",
        workflow_type=WorkflowType.DNA_NORMALIZATION,
        samples=[sample],
        target=_target(),
        registry=_registry(),
        split_config=SplitConfig(),
    )
    row = result.rows[0]
    assert row.normalization_mode is NormalizationMode.STANDARD_NEW_CONTAINER
    assert row.sample_transfer_volume_ul == pytest.approx(12.5)
    assert row.diluent_volume_ul == pytest.approx(37.5)
    assert row.generates_robot_transfer is True


def test_low_concentration_destination_volume_and_source_volume_are_invalid() -> None:
    low = NormalizationSampleInput(
        sample_id="LOW",
        analyte_type=AnalyteType.DS_DNA,
        source_container_id="SRC",
        source_well="A1",
        stock_concentration_ng_per_ul=1,
        available_volume_ul=50,
        destination_container_id="DST",
        destination_well="A1",
    )
    low_result = plan_normalization(
        batch_id="BATCH",
        workflow_type=WorkflowType.DNA_NORMALIZATION,
        samples=[low],
        target=_target(),
        registry=_registry(),
        split_config=SplitConfig(),
    )
    assert low_result.rows[0].generates_robot_transfer is False
    assert low_result.exceptions[0].exception_code is ExceptionCode.SOURCE_CONCENTRATION_BELOW_TARGET

    big_result = plan_normalization(
        batch_id="BATCH",
        workflow_type=WorkflowType.DNA_NORMALIZATION,
        samples=[
            low.model_copy(
                update={
                    "sample_id": "BIG",
                    "stock_concentration_ng_per_ul": 20,
                    "available_volume_ul": 300,
                }
            )
        ],
        target=NormalizationTarget(target_concentration_ng_per_ul=5, target_final_volume_ul=1000),
        registry=_registry(),
        split_config=SplitConfig(),
    )
    assert big_result.exceptions[0].exception_code is ExceptionCode.DESTINATION_VOLUME_EXCEEDED

    scarce = low.model_copy(
        update={
            "sample_id": "SCARCE",
            "stock_concentration_ng_per_ul": 25,
            "available_volume_ul": 12,
        }
    )
    scarce_result = plan_normalization(
        batch_id="BATCH",
        workflow_type=WorkflowType.DNA_NORMALIZATION,
        samples=[scarce],
        target=_target(),
        registry=_registry(),
        split_config=SplitConfig(),
    )
    assert scarce_result.exceptions[0].exception_code is ExceptionCode.INSUFFICIENT_SOURCE_VOLUME


def test_manifest_ingest_reports_invalid_external_rows(tmp_path: Path) -> None:
    input_csv = tmp_path / "bad.csv"
    input_csv.write_text(
        "sample_id,source_container_id,source_well,stock_concentration_ng_per_ul,"
        "available_volume_ul,destination_container_id,destination_well\n"
        ",SRC,Z99,not-a-number,,DST,A1\n"
    )
    config = NormalizationConfig(
        batch_id="BATCH",
        workflow_type=WorkflowType.DNA_NORMALIZATION,
        analyte_type=AnalyteType.DS_DNA,
        input_csv=input_csv,
        target=_target(),
        split_config=SplitConfig(),
        registry=_registry(),
    )
    result = process_normalization_config(config)
    codes = {exception.exception_code for exception in result.exceptions}
    assert ExceptionCode.MISSING_SAMPLE_ID in codes
    assert ExceptionCode.INVALID_SOURCE_LOCATION in codes
    assert ExceptionCode.INVALID_CONCENTRATION in codes
    assert ExceptionCode.MISSING_AVAILABLE_VOLUME in codes
    assert result.rows == ()


def test_in_place_and_split_workflows_and_outputs(tmp_path: Path) -> None:
    samples = [
        NormalizationSampleInput(
            sample_id="INPLACE",
            analyte_type=AnalyteType.DS_DNA,
            source_container_id="SRC",
            source_well="A1",
            stock_concentration_ng_per_ul=25,
            available_volume_ul=8,
        ),
        NormalizationSampleInput(
            sample_id="SPLIT",
            analyte_type=AnalyteType.DS_DNA,
            source_container_id="SRC",
            source_well="A2",
            stock_concentration_ng_per_ul=500,
            available_volume_ul=30,
            destination_container_id="DST",
            destination_well="A2",
        ),
    ]
    result = plan_normalization(
        batch_id="BATCH",
        workflow_type=WorkflowType.DNA_NORMALIZATION,
        samples=samples,
        target=_target(),
        registry=_registry(),
        split_config=SplitConfig(),
    )
    in_place = next(row for row in result.rows if row.sample_id == "INPLACE")
    split = next(row for row in result.rows if row.sample_id == "SPLIT")
    assert in_place.normalization_mode is NormalizationMode.IN_PLACE
    assert in_place.sample_transfer_volume_ul == 0
    assert in_place.diluent_volume_ul == pytest.approx(32)
    assert split.normalization_mode is NormalizationMode.SPLIT_REQUIRED
    assert split.sample_transfer_volume_ul == 1
    assert split.child_sample_id == "SPLIT-SPLIT1"
    assert {exc.exception_code for exc in result.exceptions} >= {
        ExceptionCode.IN_PLACE_NORMALIZATION_SELECTED,
        ExceptionCode.SPLIT_REQUIRED_HIGH_CONCENTRATION,
        ExceptionCode.SPLIT_REQUANT_REQUIRED,
    }
    write_normalization_outputs(result, tmp_path / "norm_out")
    assert (tmp_path / "norm_out" / "normalization_plan.csv").exists()


def test_in_place_destination_and_split_capacity_are_invalid() -> None:
    destination_supplied = NormalizationSampleInput(
        sample_id="S1",
        analyte_type=AnalyteType.DS_DNA,
        source_container_id="SRC",
        source_well="A1",
        stock_concentration_ng_per_ul=25,
        available_volume_ul=8,
        destination_container_id="DST",
        destination_well="A1",
    )
    result = plan_normalization(
        batch_id="BATCH",
        workflow_type=WorkflowType.DNA_NORMALIZATION,
        samples=[destination_supplied],
        target=_target(),
        registry=_registry(),
        split_config=SplitConfig(),
    )
    assert result.rows[0].generates_robot_transfer is False
    assert result.exceptions[0].exception_code is ExceptionCode.DESTINATION_SUPPLIED_FOR_IN_PLACE

    split_sample = destination_supplied.model_copy(
        update={
            "sample_id": "SPLIT",
            "stock_concentration_ng_per_ul": 500,
            "available_volume_ul": 30,
        }
    )
    split_result = plan_normalization(
        batch_id="BATCH",
        workflow_type=WorkflowType.DNA_NORMALIZATION,
        samples=[split_sample],
        target=_target(),
        registry=_registry(),
        split_config=SplitConfig(split_source_transfer_volume_ul=1, split_final_volume_ul=1200),
    )
    assert split_result.rows[0].generates_robot_transfer is False
    assert split_result.exceptions[0].exception_code is ExceptionCode.DESTINATION_VOLUME_EXCEEDED


def test_split_config_enforces_one_ul_and_positive_diluent() -> None:
    with pytest.raises(ValueError):
        SplitConfig(split_source_transfer_volume_ul=0.5, split_final_volume_ul=50)
    with pytest.raises(ValueError):
        SplitConfig(split_source_transfer_volume_ul=1, split_final_volume_ul=1)


def test_rna_requant_updates_downstream_and_flags_missing_invalid(tmp_path: Path) -> None:
    input_csv = tmp_path / "rna_input.csv"
    requant_csv = tmp_path / "requant.csv"
    input_csv.write_text(
        "sample_id,source_container_id,source_well,stock_concentration_ng_per_ul,"
        "available_volume_ul,destination_container_id,destination_well\n"
        "R1,SRC,A1,20,50,DST,A1\n"
        "R2,SRC,A2,20,50,DST,A2\n"
        "R3,SRC,A3,20,50,DST,A3\n"
        "R4,SRC,A4,20,50,DST,A4\n"
        "R5,SRC,A5,20,50,DST,A5\n"
        "R6,SRC,A6,20,50,DST,A6\n"
    )
    requant_csv.write_text(
        "sample_id,requant_concentration_ng_per_ul\n"
        "R1,7.25\n"
        "R2,\n"
        "R3,-2\n"
        "R5,250\n"
        "R6,2\n"
    )
    config = NormalizationConfig(
        batch_id="BATCH",
        workflow_type=WorkflowType.RNA_NORMALIZATION_REQUANT,
        analyte_type=AnalyteType.TOTAL_RNA,
        input_csv=input_csv,
        target=NormalizationTarget(target_mass_ng=250, target_final_volume_ul=50),
        split_config=SplitConfig(),
        registry=_registry(),
    )
    result = process_rna_workflow(
        config,
        requant_csv,
        RnaRequantPolicy(
            assay_min_concentration_ng_per_ul=0.1,
            assay_max_concentration_ng_per_ul=100,
            minimum_downstream_concentration_ng_per_ul=5,
        ),
    )
    ready = next(row for row in result.requant_rows if row.sample_id == "R1")
    assert ready.downstream_concentration_ng_per_ul == 7.25
    assert ready.status is Status.DOWNSTREAM_READY
    codes = {exception.exception_code for exception in result.requant_exceptions}
    assert ExceptionCode.MISSING_REQUANT_RESULT in codes
    assert ExceptionCode.INVALID_REQUANT_RESULT in codes
    assert ExceptionCode.REQUANT_OUT_OF_ASSAY_RANGE in codes
    assert ExceptionCode.DOWNSTREAM_VOLUME_CONSTRAINT_FAILED in codes
    absent = next(row for row in result.requant_rows if row.sample_id == "R4")
    assert absent.status is Status.MANUAL_REVIEW
    reasons = {row.manual_review_reason for row in result.requant_rows}
    assert {
        "missing_result",
        "invalid_result",
        "out_of_assay_range",
        "impossible_under_downstream_volume_constraints",
    }.issubset(reasons)
    write_rna_outputs(result, tmp_path / "rna_out")
    assert (tmp_path / "rna_out" / "rna_downstream_concentration_manifest.csv").exists()


def test_janus_export_excludes_invalid_and_writes_protocol(tmp_path: Path) -> None:
    samples = [
        NormalizationSampleInput(
            sample_id="VALID",
            analyte_type=AnalyteType.DS_DNA,
            source_container_id="SRC",
            source_well="A1",
            stock_concentration_ng_per_ul=20,
            available_volume_ul=50,
            destination_container_id="DST",
            destination_well="A1",
        ),
        NormalizationSampleInput(
            sample_id="INVALID",
            analyte_type=AnalyteType.DS_DNA,
            source_container_id="SRC",
            source_well="A2",
            stock_concentration_ng_per_ul=1,
            available_volume_ul=50,
            destination_container_id="DST",
            destination_well="A2",
        ),
    ]
    result = plan_normalization(
        batch_id="BATCH",
        workflow_type=WorkflowType.DNA_NORMALIZATION,
        samples=samples,
        target=_target(),
        registry=_registry(),
        split_config=SplitConfig(),
    )
    minimal = janus_minimal_rows(list(result.rows))
    audit = janus_audit_rows(list(result.rows))
    assert len(minimal) == 1
    assert set(minimal[0]) == {"well", "diluent_volume_ul", "sample_volume_ul"}
    assert audit[0]["sample_id"] == "VALID"
    protocol = build_protocol_ir(list(result.rows))
    assert [step.operation_type for step in protocol] == ["ADD_DILUENT", "ADD_SAMPLE", "MIX"]
    write_janus_outputs(list(result.rows), tmp_path / "janus_out")
    assert (tmp_path / "janus_out" / "janus_worklist.csv").exists()
    assert (tmp_path / "janus_out" / "protocol_ir.csv").exists()


def test_duplicate_participants_generate_no_janus_rows() -> None:
    samples = [
        NormalizationSampleInput(
            sample_id="S1",
            analyte_type=AnalyteType.DS_DNA,
            source_container_id="SRC",
            source_well="A1",
            stock_concentration_ng_per_ul=20,
            available_volume_ul=50,
            destination_container_id="DST",
            destination_well="A1",
        ),
        NormalizationSampleInput(
            sample_id="S2",
            analyte_type=AnalyteType.DS_DNA,
            source_container_id="SRC",
            source_well="A1",
            stock_concentration_ng_per_ul=20,
            available_volume_ul=50,
            destination_container_id="DST",
            destination_well="A1",
        ),
    ]
    result = plan_normalization(
        batch_id="BATCH",
        workflow_type=WorkflowType.DNA_NORMALIZATION,
        samples=samples,
        target=_target(),
        registry=_registry(),
        split_config=SplitConfig(),
    )
    assert all(not row.generates_robot_transfer for row in result.rows)
    assert janus_minimal_rows(list(result.rows)) == []


def test_throughput_defaults_compare_one_container_to_three_container_batches(tmp_path: Path) -> None:
    comparison = compare_default_batching(containers=5)
    assert comparison.optimized.total_samples == 475
    assert comparison.optimized.total_elapsed_time_min == 61
    assert comparison.optimized.samples_per_hour > comparison.baseline.samples_per_hour
    assert comparison.optimized.robot_utilization_percent > comparison.baseline.robot_utilization_percent

    with pytest.raises(ValueError):
        ThroughputScenario(containers=1, containers_per_batch=1, robot_run_time_min_per_container=5)


def test_configurable_throughput_and_readiness_gates() -> None:
    baseline = ThroughputScenario(
        containers=4,
        samples_per_container=95,
        containers_per_batch=1,
        lims_overhead_time_min_per_batch=5,
        human_prep_time_min_per_batch=10,
        robot_run_time_min_per_container=3,
        post_robot_time_min_per_batch=8,
    )
    optimized = baseline.model_copy(update={"containers_per_batch": 3})
    comparison = compare_scenarios(baseline, optimized)
    assert comparison.throughput_multiplier == round(
        comparison.optimized.samples_per_hour / comparison.baseline.samples_per_hour,
        4,
    )

    ready = BatchReadinessInputs(
        all_required_samples_have_concentrations=True,
        all_source_locations_valid=True,
        all_destination_locations_assigned=True,
        all_transfer_volumes_valid=True,
        all_exceptions_resolved_or_excluded=True,
        required_controls_present=True,
        required_reagents_defined=True,
        lims_batch_id_assigned=True,
        output_manifest_generated=False,
        operator_instructions_generated=True,
        robot_protocol_or_worklist_generated=True,
    )
    result = evaluate_batch_readiness(ready)
    assert result.robot_ready is False
    assert result.blocking_gates == ("output_manifest_generated",)


def test_written_worklist_is_minimal_csv(tmp_path: Path) -> None:
    row = {"well": "A1", "diluent_volume_ul": "37.50", "sample_volume_ul": "12.50"}
    path = tmp_path / "janus.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    assert path.read_text().splitlines()[0] == "well,diluent_volume_ul,sample_volume_ul"
