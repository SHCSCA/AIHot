from __future__ import annotations

from fastapi.testclient import TestClient

from tests.admin_helpers import app_with_admin_data, auth_header


def test_internal_events_can_filter_show_detail_and_review(tmp_path):
    client = TestClient(app_with_admin_data(tmp_path))

    listed = client.get(
        "/api/v1/internal/events?channel=ai&reviewStatus=pending&q=GPT",
        headers=auth_header(),
    )
    detail = client.get("/api/v1/internal/events/1", headers=auth_header())
    reviewed = client.patch(
        "/api/v1/internal/events/1/review",
        json={"reviewStatus": "approved", "reviewNote": "可发布", "actor": "operator"},
        headers=auth_header(),
    )
    approved = client.get(
        "/api/v1/internal/events?reviewStatus=approved", headers=auth_header()
    )
    public = client.get("/api/v1/public/events?channel=ai&date=2026-05-11")

    assert listed.status_code == 200
    assert listed.json()["events"][0]["reviewStatus"] == "pending"
    assert (
        listed.json()["events"][0]["entryReason"]
        == "DeepSeek 认为这是高权威模型发布，值得关注。"
    )
    assert listed.json()["events"][0]["mainItem"]["summary"] == "OpenAI 发布新模型。"
    assert detail.json()["event"]["title"] == "OpenAI 发布 GPT-5"
    assert detail.json()["members"][0]["sourceName"] == "OpenAI News"
    assert reviewed.json()["event"]["reviewStatus"] == "approved"
    assert reviewed.json()["event"]["reviewNote"] == "可发布"
    assert approved.json()["count"] == 1
    public_event = public.json()["events"][0]
    assert public_event["entryReason"] == "DeepSeek 认为这是高权威模型发布，值得关注。"
    assert public_event["sourceGroup"] == "official"
    assert public_event["sourceType"] == "html"
    assert public_event["sourceTier"] == "T1"
    assert public_event["mainItem"]["sourceGroup"] == "official"
    assert public_event["verificationStatus"] == "single_source"
    assert public_event["independentSourceCount"] == 1
    assert public_event["evidenceScore"] == 44
    assert public_event["supportedClaims"] == []
    assert (
        public_event["evidenceSummary"] == "当前只有一个独立发布方，尚未完成交叉验证。"
    )
    assert "reviewNote" not in public_event
    assert "reviewStatus" not in public_event
