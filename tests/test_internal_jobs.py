from __future__ import annotations

from fastapi.testclient import TestClient

from tests.admin_helpers import app_with_admin_data, auth_header


def test_failed_job_can_be_retried(tmp_path):
    client = TestClient(app_with_admin_data(tmp_path))

    response = client.post("/api/v1/internal/jobs/1/retry", headers=auth_header())

    assert response.status_code == 200
    job = response.json()["job"]
    assert job["status"] == "pending"
    assert job["lastError"] is None
    assert job["attemptCount"] == 0
