from __future__ import annotations

from fastapi.testclient import TestClient

from tests.admin_helpers import app_with_admin_data, auth_header


def test_feedback_and_evaluation_runs_are_listed_with_details(tmp_path):
    client = TestClient(app_with_admin_data(tmp_path))
    feedback = client.post(
        "/api/v1/internal/feedback-events",
        json={"channel": "ai", "clusterId": 1, "feedbackType": "false_positive", "reason": "重复", "actor": "operator"},
        headers=auth_header(),
    )
    created = client.post(
        "/api/v1/internal/evaluation-runs",
        json={
            "channel": "ai",
            "strategyVersion": "ai-default-v1",
            "name": "AI 评估",
            "request": {"windowHours": 24},
        },
        headers=auth_header(),
    )
    run_id = created.json()["evaluationRun"]["id"]
    completed = client.post(f"/api/v1/internal/evaluation-runs/{run_id}/run", headers=auth_header())
    listed_feedback = client.get(
        "/api/v1/internal/feedback-events?channel=ai&feedbackType=false_positive&clusterId=1",
        headers=auth_header(),
    )
    listed_runs = client.get("/api/v1/internal/evaluation-runs?channel=ai", headers=auth_header())
    detail = client.get(f"/api/v1/internal/evaluation-runs/{run_id}", headers=auth_header())

    assert feedback.status_code == 200
    assert listed_feedback.json()["feedbackEvents"][0]["reason"] == "重复"
    assert completed.json()["evaluationRun"]["metrics"]["labels"]["selectedEventCount"] == "精选事件数"
    assert listed_runs.json()["evaluationRuns"][0]["id"] == run_id
    assert detail.json()["evaluationRun"]["metrics"]["values"]["feedbackCount"] == 1
