from __future__ import annotations

from fastapi.testclient import TestClient

from intel_engine.main import create_app
from tests.admin_helpers import auth_header


def test_pipeline_run_endpoint_records_manual_run(tmp_path):
    app = create_app(
        db_path=tmp_path / "legacy.sqlite3",
        production_database_url=f"sqlite+pysqlite:///{tmp_path / 'production.sqlite3'}",
    )
    client = TestClient(app)

    created = client.post(
        "/api/v1/internal/pipeline-runs",
        json={"workerId": "manual-worker", "limit": 5},
        headers=auth_header(),
    )
    listed = client.get("/api/v1/internal/pipeline-runs", headers=auth_header())

    assert created.status_code == 200
    run = created.json()["pipelineRun"]
    assert run["status"] == "succeeded"
    assert run["workerId"] == "manual-worker"
    assert run["limit"] == 5
    assert listed.json()["pipelineRuns"][0]["id"] == run["id"]
