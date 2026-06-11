from __future__ import annotations

import csv
from pathlib import Path

import yaml

from labflow_agent import AgentToolRuntime, ToolCallMode, ToolCallPlan


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


def _rewrite_concentration(path: Path, concentration: str) -> None:
    row = {
        "sample_id": "S1",
        "source_container_id": "SRC",
        "source_well": "A1",
        "stock_concentration_ng_per_ul": concentration,
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
                "batch_id": "BATCH_AGENT_GUARDRAIL",
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


def _janus_plan(
    config_path: Path,
    *,
    mode: ToolCallMode,
    dry_run: bool,
    approval_token: str | None = None,
    dry_run_audit_event_id: str | None = None,
) -> ToolCallPlan:
    arguments = {
        "plan_id": str(config_path),
        "dry_run": dry_run,
        "approval_token": approval_token,
        "output_dir": None,
    }
    if dry_run_audit_event_id is not None:
        arguments["dry_run_audit_event_id"] = dry_run_audit_event_id
    return ToolCallPlan(
        tool_name="generate_janus_csv",
        arguments=arguments,
        mode=mode,
        reason="Exercise Stage 10 JANUS guardrails.",
    )


def test_commit_without_dry_run_fails_and_is_audited(tmp_path: Path) -> None:
    input_csv = tmp_path / "samples.csv"
    config_path = tmp_path / "normalization.yaml"
    _write_normalization_csv(input_csv)
    _write_normalization_config(config_path, input_csv)
    runtime = AgentToolRuntime()

    executed = runtime.execute_tool_call(
        _janus_plan(config_path, mode=ToolCallMode.COMMIT, dry_run=False, approval_token="token")
    )

    assert executed.result["status"] == "blocked"
    assert {error["code"] for error in executed.result["errors"]} == {"COMMIT_REQUIRES_DRY_RUN"}
    assert executed.audit_event_id is not None
    assert runtime.audit_store.require(executed.audit_event_id).result_status == "blocked"


def test_commit_without_approval_fails_and_is_audited(tmp_path: Path) -> None:
    input_csv = tmp_path / "samples.csv"
    config_path = tmp_path / "normalization.yaml"
    _write_normalization_csv(input_csv)
    _write_normalization_config(config_path, input_csv)
    runtime = AgentToolRuntime()
    dry_run = runtime.execute_tool_call(
        _janus_plan(config_path, mode=ToolCallMode.DRY_RUN, dry_run=True)
    )

    executed = runtime.execute_tool_call(
        _janus_plan(
            config_path,
            mode=ToolCallMode.COMMIT,
            dry_run=False,
            dry_run_audit_event_id=str(dry_run.audit_event_id),
        )
    )

    assert executed.result["status"] == "blocked"
    assert {error["code"] for error in executed.result["errors"]} == {"COMMIT_REQUIRES_APPROVAL"}
    assert executed.result["audit_event"]["dry_run_audit_event_id"] == dry_run.audit_event_id
    assert len(runtime.audit_events) == 2


def test_commit_requires_matching_dry_run_inputs(tmp_path: Path) -> None:
    input_csv = tmp_path / "samples.csv"
    first_config_path = tmp_path / "normalization.yaml"
    second_config_path = tmp_path / "other_normalization.yaml"
    _write_normalization_csv(input_csv)
    _write_normalization_config(first_config_path, input_csv)
    _write_normalization_config(second_config_path, input_csv)
    runtime = AgentToolRuntime()
    dry_run = runtime.execute_tool_call(
        _janus_plan(first_config_path, mode=ToolCallMode.DRY_RUN, dry_run=True)
    )
    approval_token = runtime.approve_commit(
        action="generate_janus_csv",
        dry_run_audit_event_id=str(dry_run.audit_event_id),
        actor_id="operator",
    )

    executed = runtime.execute_tool_call(
        _janus_plan(
            second_config_path,
            mode=ToolCallMode.COMMIT,
            dry_run=False,
            approval_token=approval_token,
            dry_run_audit_event_id=str(dry_run.audit_event_id),
        )
    )

    assert executed.result["status"] == "blocked"
    assert {error["code"] for error in executed.result["errors"]} == {"DRY_RUN_INPUT_MISMATCH"}


def test_janus_generation_blocked_for_invalid_batch_and_audited(tmp_path: Path) -> None:
    input_csv = tmp_path / "samples.csv"
    config_path = tmp_path / "normalization.yaml"
    _write_normalization_csv(input_csv, missing_concentration=True)
    _write_normalization_config(config_path, input_csv)
    runtime = AgentToolRuntime()

    executed = runtime.execute_tool_call(
        _janus_plan(config_path, mode=ToolCallMode.DRY_RUN, dry_run=True)
    )

    assert executed.result["status"] == "blocked"
    codes = {error["code"] for error in executed.result["errors"]}
    assert "MISSING_CONCENTRATION" in codes
    assert "JANUS_BLOCKED_FOR_INVALID_BATCH" in codes
    assert executed.result["audit_event_id"] == executed.audit_event_id
    assert executed.result["core_audit_event_id"].startswith("audit_")
    assert set(runtime.audit_store.require(str(executed.audit_event_id)).exception_codes) == codes


def test_dry_run_creates_audit_event(tmp_path: Path) -> None:
    input_csv = tmp_path / "samples.csv"
    config_path = tmp_path / "normalization.yaml"
    _write_normalization_csv(input_csv)
    _write_normalization_config(config_path, input_csv)
    runtime = AgentToolRuntime()

    executed = runtime.execute_tool_call(
        _janus_plan(config_path, mode=ToolCallMode.DRY_RUN, dry_run=True)
    )

    assert executed.result["status"] == "ok"
    assert executed.audit_event_id is not None
    audit_event = runtime.audit_store.require(executed.audit_event_id)
    assert audit_event.tool_name == "generate_janus_csv"
    assert audit_event.mode is ToolCallMode.DRY_RUN
    assert audit_event.artifact_ids


def test_commit_creates_audit_event_and_artifact_records(tmp_path: Path) -> None:
    input_csv = tmp_path / "samples.csv"
    config_path = tmp_path / "normalization.yaml"
    _write_normalization_csv(input_csv)
    _write_normalization_config(config_path, input_csv)
    runtime = AgentToolRuntime()
    dry_run = runtime.execute_tool_call(
        _janus_plan(config_path, mode=ToolCallMode.DRY_RUN, dry_run=True)
    )
    approval_token = runtime.approve_commit(
        action="generate_janus_csv",
        dry_run_audit_event_id=str(dry_run.audit_event_id),
        actor_id="operator",
    )

    committed = runtime.execute_tool_call(
        _janus_plan(
            config_path,
            mode=ToolCallMode.COMMIT,
            dry_run=False,
            approval_token=approval_token,
            dry_run_audit_event_id=str(dry_run.audit_event_id),
        )
    )

    assert committed.result["status"] == "ok"
    assert committed.result["audit_event_id"] == committed.audit_event_id
    assert committed.result["audit_event"]["mode"] == "commit"
    assert committed.result["audit_event"]["approval_token_id"].startswith("approval_")
    assert committed.result["audit_event"]["dry_run_audit_event_id"] == dry_run.audit_event_id
    assert committed.result["artifact_records"]
    assert {record.artifact_type for record in runtime.artifact_records} == {
        "janus_worklist_preview",
        "janus_audit_preview",
    }
    assert {
        record.commit_audit_event_id for record in runtime.artifact_records
    } == {committed.audit_event_id}


def test_commit_records_audited_dry_run_artifacts_if_source_file_changes(tmp_path: Path) -> None:
    input_csv = tmp_path / "samples.csv"
    config_path = tmp_path / "normalization.yaml"
    _write_normalization_csv(input_csv)
    _write_normalization_config(config_path, input_csv)
    runtime = AgentToolRuntime()
    dry_run = runtime.execute_tool_call(
        _janus_plan(config_path, mode=ToolCallMode.DRY_RUN, dry_run=True)
    )
    _rewrite_concentration(input_csv, "10")
    approval_token = runtime.approve_commit(
        action="generate_janus_csv",
        dry_run_audit_event_id=str(dry_run.audit_event_id),
        actor_id="operator",
    )

    committed = runtime.execute_tool_call(
        _janus_plan(
            config_path,
            mode=ToolCallMode.COMMIT,
            dry_run=False,
            approval_token=approval_token,
            dry_run_audit_event_id=str(dry_run.audit_event_id),
        )
    )

    worklist_records = [
        record
        for record in runtime.artifact_records
        if record.artifact_type == "janus_worklist_preview"
    ]
    assert committed.result["status"] == "ok"
    assert worklist_records[0].data == [
        {"well": "A1", "diluent_volume_ul": "37.50", "sample_volume_ul": "12.50"}
    ]
