from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import yaml

from labflow_core.domain.wells import all_plate_wells
from labflow_core.tools import (
    call_tool,
    compare_throughput,
    explain_exception_code,
    generate_janus_csv,
    generate_normalization_plan,
    list_tools,
    parse_varioskan_tsv,
    process_quantification,
    process_rna_requant,
    validate_batch,
    validate_workflow,
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


def _write_normalization_csv(path: Path, *, missing_concentration: bool = False) -> None:
    row = {
        "sample_id": "S1",
        "source_container_id": "SRC",
        "source_well": "A1",
        "stock_concentration_ng_per_ul": "" if missing_concentration else "20",
        "available_volume_ul": "50",
        "destination_container_id": "DST",
        "destination_well": "A1",
    }
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)


def _write_normalization_config(path: Path, input_csv: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "batch_id": "BATCH_TOOL",
                "workflow_type": "DNA_NORMALIZATION",
                "analyte_type": "dsDNA",
                "input_csv": input_csv.name,
                "target": {
                    "target_concentration_ng_per_ul": 5,
                    "target_final_volume_ul": 50,
                },
                "containers": [
                    {
                        "container_id": "SRC",
                        "container_type_id": "matrix_96_1ml_screwtop",
                    },
                    {
                        "container_id": "DST",
                        "container_type_id": "matrix_96_1ml_screwtop",
                    },
                ],
            },
            sort_keys=True,
        )
    )


def _write_standard_tsv(path: Path) -> None:
    path.write_text(
        "Plate ID\tWell\tSample ID\tReading\n"
        + "\n".join(
            f"STD\t{well}\tSTD\t{100 + concentration * 100}"
            for well, concentration in STANDARD_CONCS.items()
        )
        + "\n"
    )


def _write_sample_plate_tsv(path: Path) -> None:
    lines = ["Plate ID\tWell\tSample ID\tReading"]
    sample_index = 1
    for well in all_plate_wells():
        well_label = str(well)
        if well_label == "H12":
            lines.append("PLATE\tH12\tBLANK\t120")
            continue
        lines.append(f"PLATE\t{well_label}\tS{sample_index:03d}\t620")
        sample_index += 1
    path.write_text("\n".join(lines) + "\n")


def _write_quantification_config(path: Path, standards_tsv: Path, samples_tsv: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "batch_id": "BATCH_QUANT_TOOL",
                "workflow_type": "DNA_QUANT",
                "assay": "Quant-iT PicoGreen",
                "standards_tsv": standards_tsv.name,
                "sample_plates": [
                    {
                        "plate_id": "PLATE",
                        "source_container_id": "PLATE",
                        "tsv": samples_tsv.name,
                        "blank_well": "H12",
                        "dilution_factor": 10,
                    }
                ],
                "standard_concentrations_ng_per_ul": STANDARD_CONCS,
            },
            sort_keys=True,
        )
    )


def _write_rna_requant_config(path: Path, input_csv: Path, requant_csv: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "batch_id": "BATCH_RNA_TOOL",
                "workflow_type": "RNA_NORMALIZATION_REQUANT",
                "analyte_type": "total_RNA",
                "input_csv": input_csv.name,
                "target": {
                    "target_mass_ng": 250,
                    "target_final_volume_ul": 50,
                },
                "containers": [
                    {
                        "container_id": "SRC",
                        "container_type_id": "matrix_96_1ml_screwtop",
                    },
                    {
                        "container_id": "DST",
                        "container_type_id": "matrix_96_1ml_screwtop",
                    },
                ],
                "requant_csv": requant_csv.name,
            },
            sort_keys=True,
        )
    )


def test_tool_registry_lists_required_tools() -> None:
    names = {tool["name"] for tool in list_tools()}
    assert {
        "validate_workflow",
        "validate_batch",
        "parse_varioskan_tsv",
        "process_quantification",
        "generate_normalization_plan",
        "process_rna_requant",
        "generate_janus_csv",
        "compare_throughput",
        "explain_exception_code",
        "ingest_ngs_qc_results",
        "validate_qc_provenance",
        "explain_qc_failure",
        "generate_lab_to_analysis_lineage",
    } <= names


def test_missing_concentration_returns_structured_error(tmp_path: Path) -> None:
    input_csv = tmp_path / "samples.csv"
    config_path = tmp_path / "normalization.yaml"
    _write_normalization_csv(input_csv, missing_concentration=True)
    _write_normalization_config(config_path, input_csv)

    result = generate_normalization_plan(str(config_path))

    assert result["ok"] is False
    assert result["status"] == "invalid"
    assert {error["code"] for error in result["errors"]} == {"MISSING_CONCENTRATION"}
    json.dumps(result)


def test_invalid_batch_blocks_janus(tmp_path: Path) -> None:
    input_csv = tmp_path / "samples.csv"
    config_path = tmp_path / "normalization.yaml"
    _write_normalization_csv(input_csv, missing_concentration=True)
    _write_normalization_config(config_path, input_csv)

    result = generate_janus_csv(str(config_path), dry_run=True)

    assert result["ok"] is False
    assert result["status"] == "blocked"
    codes = {error["code"] for error in result["errors"]}
    assert "MISSING_CONCENTRATION" in codes
    assert "JANUS_BLOCKED_FOR_INVALID_BATCH" in codes
    assert result["audit_event_id"].startswith("audit_")
    json.dumps(result)


def test_valid_batch_dry_run_returns_janus_artifact_preview(tmp_path: Path) -> None:
    input_csv = tmp_path / "samples.csv"
    config_path = tmp_path / "normalization.yaml"
    _write_normalization_csv(input_csv)
    _write_normalization_config(config_path, input_csv)

    result = generate_janus_csv(str(config_path), dry_run=True)

    assert result["ok"] is True
    assert result["status"] == "ok"
    artifact_types = {artifact["artifact_type"] for artifact in result["artifacts"]}
    assert {"janus_worklist_preview", "janus_audit_preview"} <= artifact_types
    worklist = next(
        artifact for artifact in result["artifacts"] if artifact["artifact_type"] == "janus_worklist_preview"
    )
    assert worklist["data"] == [
        {"well": "A1", "diluent_volume_ul": "37.50", "sample_volume_ul": "12.50"}
    ]
    json.dumps(result)


def test_commit_mode_janus_is_blocked_until_guardrail_store_exists(tmp_path: Path) -> None:
    input_csv = tmp_path / "samples.csv"
    config_path = tmp_path / "normalization.yaml"
    output_dir = tmp_path / "janus_out"
    _write_normalization_csv(input_csv)
    _write_normalization_config(config_path, input_csv)

    no_token_result = generate_janus_csv(str(config_path), dry_run=False)
    token_result = generate_janus_csv(
        str(config_path),
        dry_run=False,
        approval_token="not-a-real-approval",
        output_dir=str(output_dir),
    )

    for result in (no_token_result, token_result):
        assert result["ok"] is False
        assert result["status"] == "blocked"
        assert {error["code"] for error in result["errors"]} == {"COMMIT_MODE_NOT_AVAILABLE"}
        assert result["artifacts"] == []
        assert result["audit_event"]["mode"] == "commit"
        json.dumps(result)
    assert not output_dir.exists()


def test_identical_tool_calls_create_distinct_audit_events() -> None:
    first = explain_exception_code("MISSING_CONCENTRATION")
    second = explain_exception_code("MISSING_CONCENTRATION")

    assert first["audit_event_id"] != second["audit_event_id"]
    assert first["audit_event"]["timestamp"] != second["audit_event"]["timestamp"]
    assert first["audit_event"]["input_hash"] == second["audit_event"]["input_hash"]
    json.dumps(first)
    json.dumps(second)


def test_subprocess_tool_calls_create_distinct_audit_events() -> None:
    script = (
        "import json; "
        "from labflow_core.tools import explain_exception_code; "
        "print(json.dumps(explain_exception_code('MISSING_CONCENTRATION')))"
    )

    first = json.loads(subprocess.check_output([sys.executable, "-c", script], text=True))
    second = json.loads(subprocess.check_output([sys.executable, "-c", script], text=True))

    assert first["audit_event_id"] != second["audit_event_id"]
    assert first["audit_event"]["timestamp"] != second["audit_event"]["timestamp"]
    assert first["audit_event"]["input_hash"] == second["audit_event"]["input_hash"]


def test_process_quantification_wrapper_returns_json_serializable_artifacts(
    tmp_path: Path,
) -> None:
    standards_tsv = tmp_path / "standards.tsv"
    samples_tsv = tmp_path / "samples.tsv"
    config_path = tmp_path / "quantification.yaml"
    _write_standard_tsv(standards_tsv)
    _write_sample_plate_tsv(samples_tsv)
    _write_quantification_config(config_path, standards_tsv, samples_tsv)

    result = process_quantification(str(config_path))

    assert result["ok"] is True
    assert result["status"] == "valid"
    artifact_types = {artifact["artifact_type"] for artifact in result["artifacts"]}
    assert {"quantification_rows", "standard_curve"} <= artifact_types
    quant_rows = next(
        artifact for artifact in result["artifacts"] if artifact["artifact_type"] == "quantification_rows"
    )
    assert len(quant_rows["data"]) == 95
    json.dumps(result)


def test_process_rna_requant_wrapper_returns_downstream_manifest(tmp_path: Path) -> None:
    input_csv = tmp_path / "rna_input.csv"
    requant_csv = tmp_path / "requant.csv"
    config_path = tmp_path / "rna_requant.yaml"
    _write_normalization_csv(input_csv)
    requant_csv.write_text("sample_id,requant_concentration_ng_per_ul\nS1,7.25\n")
    _write_rna_requant_config(config_path, input_csv, requant_csv)

    result = process_rna_requant(str(config_path))

    assert result["ok"] is True
    assert result["status"] == "valid"
    downstream = next(
        artifact
        for artifact in result["artifacts"]
        if artifact["artifact_type"] == "rna_downstream_manifest"
    )
    assert downstream["data"] == [
        {
            "sample_id": "S1",
            "downstream_concentration_ng_per_ul": "7.2500",
            "downstream_ready": "True",
        }
    ]
    json.dumps(result)


def test_read_only_tools_return_json_serializable_results(tmp_path: Path) -> None:
    workflow_yaml = (Path("examples/workflows/valid_dna_quant.workflow.yaml")).read_text()
    throughput_config = tmp_path / "throughput.yaml"
    throughput_config.write_text("containers: 3\n")
    varioskan_tsv = tmp_path / "reader.tsv"
    varioskan_tsv.write_text("Plate ID\tWell\tSample ID\tReading\nP1\tA1\tS1\t100\n")

    results = [
        validate_workflow(workflow_yaml),
        validate_batch(batch_id="DNA_QUANT_BATCH_001", workflow_yaml=workflow_yaml),
        parse_varioskan_tsv(str(varioskan_tsv)),
        compare_throughput(str(throughput_config)),
        explain_exception_code("MISSING_CONCENTRATION"),
        call_tool("validate_workflow", workflow_yaml=workflow_yaml),
    ]

    assert all(result["audit_event_id"].startswith("audit_") for result in results)
    for result in results:
        json.dumps(result)
