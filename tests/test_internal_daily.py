from __future__ import annotations

from fastapi.testclient import TestClient

from tests.admin_helpers import app_with_admin_data, auth_header


def test_daily_digest_can_generate_publish_and_unpublish(tmp_path):
    client = TestClient(app_with_admin_data(tmp_path))

    generated = client.post(
        "/api/v1/internal/daily-digests/generate",
        json={"channel": "ai", "date": "2026-05-11", "strategyVersion": "ai-default-v1"},
        headers=auth_header(),
    )
    digest_id = generated.json()["dailyDigest"]["id"]
    unpublished = client.post(
        f"/api/v1/internal/daily-digests/{digest_id}/unpublish",
        json={"actor": "operator"},
        headers=auth_header(),
    )
    public_hidden = client.get("/api/v1/public/daily?channel=ai&date=2026-05-11")
    published = client.post(
        f"/api/v1/internal/daily-digests/{digest_id}/publish",
        json={"actor": "operator"},
        headers=auth_header(),
    )
    public_visible = client.get("/api/v1/public/daily?channel=ai&date=2026-05-11")
    listed = client.get("/api/v1/internal/daily-digests?channel=ai&date=2026-05-11", headers=auth_header())

    assert generated.status_code == 200
    assert unpublished.json()["dailyDigest"]["published"] is False
    assert public_hidden.json()["daily"] is None
    assert published.json()["dailyDigest"]["published"] is True
    assert published.json()["dailyDigest"]["publishedBy"] == "operator"
    assert public_visible.json()["daily"]["title"] == "AI 日报"
    assert listed.json()["dailyDigests"][0]["id"] == digest_id
