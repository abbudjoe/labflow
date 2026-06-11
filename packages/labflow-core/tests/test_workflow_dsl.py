from __future__ import annotations

from pathlib import Path

import pytest

from labflow_core.dsl import (
    DiagnosticCode,
    parse_workflow_text,
    validate_workflow_file,
    validate_workflow_text,
)
from labflow_core.dsl.schema import workflow_json_schema

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = REPO_ROOT / "examples" / "workflows"

VALID_EXAMPLES = [
    "valid_dna_quant.workflow.yaml",
    "valid_dna_normalization.workflow.yaml",
    "valid_rna_norm_requant.workflow.yaml",
    "fixed_rna_norm_requant.workflow.yaml",
]

INVALID_EXAMPLES: dict[str, set[str]] = {
    "invalid_missing_blank.workflow.yaml": {
        DiagnosticCode.MISSING_PLATE_BLANK.value,
        DiagnosticCode.JANUS_BLOCKED_FOR_INVALID_BATCH.value,
    },
    "invalid_molar_target.workflow.yaml": {
        DiagnosticCode.MOLAR_TARGET_NOT_SUPPORTED.value,
        DiagnosticCode.JANUS_BLOCKED_FOR_INVALID_BATCH.value,
    },
    "invalid_duplicate_well.workflow.yaml": {
        DiagnosticCode.DUPLICATE_SOURCE_LOCATION.value,
        DiagnosticCode.DUPLICATE_DESTINATION_LOCATION.value,
        DiagnosticCode.JANUS_BLOCKED_FOR_INVALID_BATCH.value,
    },
    "invalid_rna_norm_requant.workflow.yaml": {
        DiagnosticCode.MISSING_PLATE_BLANK.value,
        DiagnosticCode.MISSING_BATCH_STANDARD_CURVE.value,
        DiagnosticCode.INVALID_WELL.value,
        DiagnosticCode.MISSING_CONCENTRATION.value,
        DiagnosticCode.JANUS_BLOCKED_FOR_INVALID_BATCH.value,
    },
}


@pytest.mark.parametrize("filename", VALID_EXAMPLES)
def test_valid_workflow_examples_pass(filename: str) -> None:
    result = validate_workflow_file(EXAMPLES / filename)
    assert result.valid, [diagnostic.model_dump() for diagnostic in result.diagnostics]
    assert result.workflow is not None


@pytest.mark.parametrize(("filename", "expected_codes"), INVALID_EXAMPLES.items())
def test_invalid_workflow_examples_emit_expected_diagnostics(
    filename: str,
    expected_codes: set[str],
) -> None:
    result = validate_workflow_file(EXAMPLES / filename)
    codes = {diagnostic.code for diagnostic in result.diagnostics}
    assert expected_codes <= codes
    assert result.valid is False


def test_dsl_validation_can_be_called_from_python_text() -> None:
    result = parse_workflow_text((EXAMPLES / "valid_dna_quant.workflow.yaml").read_text())
    assert result.ok
    assert result.workflow is not None
    assert result.workflow.workflow.type.value == "dna_quant"


def test_workflow_schema_exports_json_schema() -> None:
    schema = workflow_json_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "workflow" in schema["properties"]
    assert "batch" in schema["properties"]


def test_all_stage4_example_files_exist() -> None:
    expected = set(VALID_EXAMPLES) | set(INVALID_EXAMPLES)
    actual = {path.name for path in EXAMPLES.glob("*.workflow.yaml")}
    assert expected <= actual


def test_duplicate_well_detection_normalizes_case() -> None:
    text = (EXAMPLES / "invalid_duplicate_well.workflow.yaml").read_text()
    mixed_case = text.replace(
        "source_well: A1\n    stock_concentration_ng_per_ul: 20\n"
        "    available_volume_ul: 50\n    destination_container_id: DNA_DST_001\n"
        "    destination_well: A1\n\noutputs:",
        "source_well: a1\n    stock_concentration_ng_per_ul: 20\n"
        "    available_volume_ul: 50\n    destination_container_id: DNA_DST_001\n"
        "    destination_well: a1\n\noutputs:",
        1,
    )
    result = validate_workflow_text(mixed_case)
    codes = {diagnostic.code for diagnostic in result.diagnostics}
    assert DiagnosticCode.DUPLICATE_SOURCE_LOCATION.value in codes
    assert DiagnosticCode.DUPLICATE_DESTINATION_LOCATION.value in codes


def test_blank_standard_identifier_is_missing_standard() -> None:
    text = (EXAMPLES / "valid_dna_quant.workflow.yaml").read_text()
    blank_standard = text.replace("A1: STD_1", "A1: '   '")
    result = validate_workflow_text(blank_standard)
    codes = {diagnostic.code for diagnostic in result.diagnostics}
    assert DiagnosticCode.MISSING_BATCH_STANDARD_CURVE.value in codes


@pytest.mark.parametrize("samples_per_plate", [94, 96])
def test_samples_per_plate_must_be_exactly_95(samples_per_plate: int) -> None:
    text = (EXAMPLES / "valid_dna_quant.workflow.yaml").read_text()
    text = text.replace("samples_per_plate: 95", f"samples_per_plate: {samples_per_plate}")
    result = validate_workflow_text(text)
    codes = {diagnostic.code for diagnostic in result.diagnostics}
    assert DiagnosticCode.INVALID_SAMPLE_PLATE_LAYOUT.value in codes


def test_destinationless_in_place_eligible_sample_is_valid() -> None:
    text = (EXAMPLES / "valid_rna_norm_requant.workflow.yaml").read_text()
    text = text.replace("sample_id: RNA_N_001", "sample_id: RNA_INPLACE_001")
    text = text.replace("stock_concentration_ng_per_ul: 25", "stock_concentration_ng_per_ul: 25")
    text = text.replace("available_volume_ul: 50", "available_volume_ul: 8")
    text = text.replace("    destination_container_id: RNA_DST_001\n", "")
    text = text.replace("    destination_well: A1\n", "")

    result = validate_workflow_text(text)

    codes = {diagnostic.code for diagnostic in result.diagnostics}
    assert DiagnosticCode.MISSING_DESTINATION_LOCATION.value not in codes
    assert result.valid
