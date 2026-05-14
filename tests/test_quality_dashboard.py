from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from intel_engine.models import FetchRunRecord, RawDocumentRecord, RawScreeningResultRecord
from tests.admin_helpers import app_with_admin_data, auth_header


def test_quality_dashboard_requires_auth_and_returns_channel_funnel(tmp_path):
    app = app_with_admin_data(tmp_path)
    client = TestClient(app)

    unauthenticated = client.get("/api/v1/internal/quality-dashboard?window=720")
    response = client.get("/api/v1/internal/quality-dashboard?window=720", headers=auth_header())

    assert unauthenticated.status_code == 401
    assert response.status_code == 200
    channel = response.json()["channels"][0]
    assert channel["channel"] == "ai"
    assert channel["metrics"]["rawDocuments"] == 1
    assert channel["metrics"]["acceptedScreenings"] == 1
    assert channel["metrics"]["normalizedItems"] == 1
    assert channel["metrics"]["selectedItems"] == 1
    assert channel["categoryBreakdown"][0]["category"] == "ai_models"
    assert channel["sourceContributions"][0]["sourceId"] == "openai_news"


def test_quality_dashboard_surfaces_rejection_reasons(tmp_path):
    app = app_with_admin_data(tmp_path)
    SessionLocal = app.state.production_sessionmaker
    now = datetime(2026, 5, 11, 11, 0, tzinfo=timezone.utc)
    with SessionLocal() as session:
        run = FetchRunRecord(
            source_id="openai_news",
            status="succeeded",
            started_at=now,
            finished_at=now,
            http_status=200,
            content_type="application/rss+xml",
            bytes_received=128,
            item_count=1,
            metadata_json={},
        )
        session.add(run)
        session.flush()
        raw = RawDocumentRecord(
            fetch_run_id=run.id,
            source_id="openai_news",
            url="https://openai.com/news/old-tutorial",
            canonical_url="https://openai.com/news/old-tutorial",
            content_type="application/rss+xml",
            body_text="Old tutorial.",
            body_html="<p>Old tutorial.</p>",
            response_headers_json={},
            content_hash="raw-rejected",
            fetched_at=now,
        )
        session.add(raw)
        session.flush()
        session.add(
            RawScreeningResultRecord(
                raw_document_id=raw.id,
                strategy_version="ai-default-v1",
                provider="deepseek",
                model="deepseek-v4-flash",
                screen_status="rejected",
                screen_bucket="irrelevant",
                relevance_score=35,
                confidence_score=91,
                category="ai_models",
                title_cn="旧教程",
                summary_cn="旧教程无新增事件。",
                tags_json=["教程"],
                reason_code="evergreen_tutorial",
                reason_cn="常青教程或旧知识。",
                raw_json={"provider": "deepseek"},
            )
        )
        session.commit()

    response = TestClient(app).get("/api/v1/internal/quality-dashboard?window=720", headers=auth_header())

    assert response.status_code == 200
    channel = response.json()["channels"][0]
    assert channel["metrics"]["rejectedScreenings"] == 1
    assert channel["rejectionReasons"][0]["reasonCode"] == "evergreen_tutorial"
    assert channel["rejectionReasons"][0]["count"] == 1
