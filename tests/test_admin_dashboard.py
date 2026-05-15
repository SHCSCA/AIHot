from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from intel_engine.models import FetchJobRecord, SourceRecord, SourceStateRecord
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


def test_dashboard_returns_channel_metrics_and_filters_detail_lists(tmp_path):
    app = app_with_admin_data(tmp_path)
    SessionLocal = app.state.production_sessionmaker
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    with SessionLocal() as session:
        session.add(
            SourceRecord(
                id="amazon_ads_updates",
                channel="amazon",
                source_type="html",
                tier="T1",
                name="Amazon Ads Updates",
                url="https://advertising.amazon.com/solutions/products",
                language="en",
                region="global",
                marketplace=None,
                authority_weight=92,
                noise_level=0.08,
                fetch_adapter="http_article",
                parser_type="html_list",
                default_categories=["ads_ppc"],
                fetch_interval_minutes=60,
                enabled=True,
                visibility="public",
                source_group="official",
                collection_status="collectable",
                free_access=True,
            )
        )
        session.add(SourceStateRecord(source_id="amazon_ads_updates", health_score=95))
        session.add(
            FetchJobRecord(
                source_id="amazon_ads_updates",
                status="failed",
                priority=10,
                run_after=now,
                last_error="Amazon 403",
            )
        )
        session.commit()

    response = TestClient(app).get("/api/v1/internal/dashboard?channel=amazon", headers=auth_header())
    payload = response.json()

    assert response.status_code == 200
    assert payload["metrics"]["sourceCount"] == 2
    assert {channel["channel"]: channel["metrics"]["sourceCount"] for channel in payload["channelMetrics"]} == {
        "ai": 1,
        "amazon": 1,
    }
    assert [job["sourceId"] for job in payload["recentFailedJobs"]] == ["amazon_ads_updates"]
