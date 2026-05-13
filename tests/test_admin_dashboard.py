from __future__ import annotations

from fastapi.testclient import TestClient

from tests.admin_helpers import app_with_admin_data, auth_header


def test_dashboard_requires_auth_and_returns_core_metrics(tmp_path):
    client = TestClient(app_with_admin_data(tmp_path))

    unauthenticated = client.get("/api/v1/internal/dashboard")
    response = client.get("/api/v1/internal/dashboard", headers=auth_header())

    assert unauthenticated.status_code == 401
    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics"]["sourceCount"] == 1
    assert payload["metrics"]["healthWarningCount"] == 1
    assert payload["metrics"]["failedJobCount"] == 1
    assert payload["metrics"]["pendingReviewEventCount"] == 1
    assert payload["metrics"]["publishedDailyCount"] == 1
    assert payload["recentFailedJobs"][0]["sourceId"] == "openai_news"
