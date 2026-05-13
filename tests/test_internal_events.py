from __future__ import annotations

from fastapi.testclient import TestClient

from tests.admin_helpers import app_with_admin_data, auth_header


def test_internal_events_can_filter_show_detail_and_review(tmp_path):
    client = TestClient(app_with_admin_data(tmp_path))

    listed = client.get("/api/v1/internal/events?channel=ai&reviewStatus=pending&q=GPT", headers=auth_header())
    detail = client.get("/api/v1/internal/events/1", headers=auth_header())
    reviewed = client.patch(
        "/api/v1/internal/events/1/review",
        json={"reviewStatus": "approved", "reviewNote": "可发布", "actor": "operator"},
        headers=auth_header(),
    )
    approved = client.get("/api/v1/internal/events?reviewStatus=approved", headers=auth_header())
    public = client.get("/api/v1/public/events?channel=ai")

    assert listed.status_code == 200
    assert listed.json()["events"][0]["reviewStatus"] == "pending"
    assert listed.json()["events"][0]["entryReason"] == "DeepSeek 认为这是高权威模型发布，值得关注。"
    assert listed.json()["events"][0]["mainItem"]["summary"] == "OpenAI 发布新模型。"
    assert detail.json()["event"]["title"] == "OpenAI 发布 GPT-5"
    assert detail.json()["members"][0]["sourceName"] == "OpenAI News"
    assert reviewed.json()["event"]["reviewStatus"] == "approved"
    assert reviewed.json()["event"]["reviewNote"] == "可发布"
    assert approved.json()["count"] == 1
    assert "reviewNote" not in public.json()["events"][0]
    assert "reviewStatus" not in public.json()["events"][0]
