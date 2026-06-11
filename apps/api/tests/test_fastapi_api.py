from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import yaml
from fastapi.testclient import TestClient

from labflow_api.main import create_app
from labflow_api.settings import ApiSettings


def _client(tmp_path: Path) -> TestClient:
    app = create_app(ApiSettings(artifact_store_dir=tmp_path / "artifacts"))
    return TestClient(app)


def _data(response_json: dict[str, Any]) -> dict[str, Any]:
    assert response_json["ok"] is True
    assert response_json["trace_id"].startswith("trace_")
    data = response_json["data"]
    assert isinstance(data, dict)
    return data


def _write_normalization_csv(path: Path) -> None:
    row = {
        "sample_id": "S1",
        "source_container_id": "SRC",
        "source_well": "A1",
        "stock_concentration_ng_per_ul": "20",
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
                "batch_id": "BATCH_API",
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


def test_health_and_openapi_docs_are_available(tmp_path: Path) -> None:
    client = _client(tmp_path)

    health = _data(client.get("/health").json())
    openapi = client.get("/openapi.json")

    assert health["status"] == "ok"
    assert openapi.status_code == 200
    assert "/health" in openapi.json()["paths"]


def test_workflow_validation_endpoint_returns_diagnostics(tmp_path: Path) -> None:
    client = _client(tmp_path)
    workflow_yaml = Path("examples/workflows/invalid_missing_blank.workflow.yaml").read_text()

    data = _data(client.post("/workflows/validate", json={"workflow_yaml": workflow_yaml}).json())

    assert data["ok"] is False
    assert "MISSING_PLATE_BLANK" in {diagnostic["code"] for diagnostic in data["diagnostics"]}


def test_rag_and_agent_endpoints_return_traceable_grounded_payloads(tmp_path: Path) -> None:
    client = _client(tmp_path)

    rag_data = _data(client.post("/rag/query", json={"question": "Why are blanks required?"}).json())
    agent_data = _data(
        client.post(
            "/agent/explain-diagnostic",
            json={
                "diagnostic_code": "MISSING_CONCENTRATION",
                "question": "Explain MISSING_CONCENTRATION.",
            },
        ).json()
    )

    assert "answer" in rag_data
    assert rag_data["unsupported"] is False
    assert agent_data["task"] == "explain_diagnostic"
    assert agent_data["tool_calls"][0]["tool_name"] == "explain_exception_code"


def test_rag_debug_endpoint_returns_retrieval_diagnostics(tmp_path: Path) -> None:
    client = _client(tmp_path)

    data = _data(
        client.post(
            "/rag/debug",
            json={"question": "Can a missing concentration be filled in later?"},
        ).json()
    )

    assert data["question"] == "Can a missing concentration be filled in later?"
    assert data["top_results"]
    assert data["expanded_query_terms"]
    assert data["source_family_requirements"]
    assert "missing_required_source_families" in data
    assert "supplemented_sources" in data
    assert "source_family_counts" in data
    assert isinstance(data["stale_sources"], list)
    assert isinstance(data["source_conflicts"], list)


def test_tool_audit_and_artifact_endpoints(tmp_path: Path) -> None:
    client = _client(tmp_path)
    input_csv = tmp_path / "samples.csv"
    config_path = tmp_path / "normalization.yaml"
    _write_normalization_csv(input_csv)
    _write_normalization_config(config_path, input_csv)

    dry_run = _data(
        client.post(
            "/tools/execute",
            json={
                "tool_name": "generate_janus_csv",
                "mode": "dry_run",
                "arguments": {
                    "plan_id": str(config_path),
                    "dry_run": True,
                    "approval_token": None,
                    "output_dir": None,
                },
            },
        ).json()
    )
    audit_event_id = dry_run["audit_event_id"]

    audit_list = _data(client.get("/audit/events").json())
    audit_detail = _data(client.get(f"/audit/events/{audit_event_id}").json())

    assert audit_event_id in {event["audit_event_id"] for event in audit_list["events"]}
    assert audit_detail["audit_event_id"] == audit_event_id

    token = client.app.state.labflow_state.tool_runtime.approve_commit(
        action="generate_janus_csv",
        dry_run_audit_event_id=audit_event_id,
        actor_id="operator",
    )
    commit = _data(
        client.post(
            "/tools/execute",
            json={
                "tool_name": "generate_janus_csv",
                "mode": "commit",
                "arguments": {
                    "plan_id": str(config_path),
                    "dry_run": False,
                    "approval_token": token,
                    "dry_run_audit_event_id": audit_event_id,
                    "output_dir": None,
                },
            },
        ).json()
    )
    artifact_id = commit["result"]["artifact_records"][0]["artifact_record_id"]
    artifact = _data(client.get(f"/artifacts/{artifact_id}").json())

    assert commit["result"]["status"] == "ok"
    assert artifact["artifact_record_id"] == artifact_id
    assert (tmp_path / "artifacts" / f"{artifact_id}.json").exists()


def test_evals_run_and_lookup(tmp_path: Path) -> None:
    client = _client(tmp_path)

    report = _data(client.post("/evals/run", json={"retrieval_only": True, "top_k": 6}).json())
    fetched = _data(client.get(f"/evals/runs/{report['eval_run_id']}").json())

    assert report["eval_run_id"] == fetched["eval_run_id"]
    assert fetched["retrieval_only"] is True


def test_structured_not_found_error_has_trace_id(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/audit/events/missing")

    assert response.status_code == 404
    body = response.json()
    assert body["ok"] is False
    assert body["trace_id"].startswith("trace_")
    assert body["error"]["code"] == "NOT_FOUND"


def test_request_validation_error_has_structured_trace_envelope(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post("/rag/query", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["ok"] is False
    assert body["trace_id"].startswith("trace_")
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["errors"]


def test_unexpected_runtime_error_has_structured_trace_envelope(tmp_path: Path) -> None:
    app = create_app(ApiSettings(artifact_store_dir=tmp_path / "artifacts"))
    app.state.labflow_state = None
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/audit/events")

    assert response.status_code == 500
    body = response.json()
    assert body["ok"] is False
    assert body["trace_id"].startswith("trace_")
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "details" in body["error"]
