from __future__ import annotations

import base64
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from intel_engine.main import create_app
from intel_engine.models import FetchJobRecord, FetchRunRecord, RawDocumentRecord, RawScreeningResultRecord, StrategyVersionRecord


def _app(tmp_path):
    app = create_app(
        db_path=tmp_path / "legacy.sqlite3",
        production_database_url=f"sqlite+pysqlite:///{tmp_path / 'production.sqlite3'}",
    )
    app.state.source_connectivity_validator = lambda payload: {
        "ok": True,
        "message": "连通性测试通过。",
        "documentCount": 1,
    }
    return app


def _auth_header() -> dict[str, str]:
    token = base64.b64encode(b"admin:admin").decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _source_payload():
    return {
        "id": "openai_news",
        "channel": "ai",
        "sourceType": "html",
        "tier": "T1",
        "name": "OpenAI News",
        "url": "https://openai.com/news/",
        "language": "en",
        "region": "global",
        "marketplace": None,
        "authorityWeight": 95,
        "noiseLevel": 0.05,
        "fetchAdapter": "http_article",
        "parserType": "website",
        "defaultCategories": ["ai_models"],
        "fetchIntervalMinutes": 60,
        "enabled": True,
        "visibility": "public",
        "notes": None,
    }


def test_internal_sources_can_create_list_and_patch(tmp_path):
    app = _app(tmp_path)
    client = TestClient(app)

    created = client.post("/api/v1/internal/sources", json=_source_payload(), headers=_auth_header())
    listed = client.get("/api/v1/internal/sources?channel=ai", headers=_auth_header())
    patched = client.patch(
        "/api/v1/internal/sources/openai_news",
        json={"enabled": False},
        headers=_auth_header(),
    )

    assert created.status_code == 200
    assert created.json()["source"]["id"] == "openai_news"
    assert listed.json()["sources"][0]["tier"] == "T1"
    assert patched.json()["source"]["enabled"] is False


def test_internal_sources_reject_blank_required_fields(tmp_path):
    app = _app(tmp_path)
    client = TestClient(app)
    payload = {**_source_payload(), "id": " ", "name": "", "url": " "}

    created = client.post("/api/v1/internal/sources", json=payload, headers=_auth_header())

    assert created.status_code == 422
    assert "信源 ID" in created.json()["detail"]["message"]


def test_internal_sources_reject_duplicate_id_or_url(tmp_path):
    app = _app(tmp_path)
    client = TestClient(app)
    payload = _source_payload()

    assert client.post("/api/v1/internal/sources", json=payload, headers=_auth_header()).status_code == 200
    same_id = client.post("/api/v1/internal/sources", json={**payload, "name": "Other"}, headers=_auth_header())
    same_url = client.post(
        "/api/v1/internal/sources",
        json={**payload, "id": "openai_news_copy", "url": "https://openai.com/news"},
        headers=_auth_header(),
    )

    assert same_id.status_code == 409
    assert same_id.json()["detail"]["code"] == "source_exists"
    assert same_url.status_code == 409
    assert same_url.json()["detail"]["code"] == "source_url_exists"


def test_internal_sources_require_connectivity_before_save(tmp_path):
    app = _app(tmp_path)
    app.state.source_connectivity_validator = lambda payload: {
        "ok": False,
        "message": "连通性测试失败：HTTP 404",
        "documentCount": 0,
    }
    client = TestClient(app)

    created = client.post("/api/v1/internal/sources", json=_source_payload(), headers=_auth_header())

    assert created.status_code == 422
    assert created.json()["detail"]["code"] == "source_connectivity_failed"
    assert "HTTP 404" in created.json()["detail"]["message"]


def test_internal_source_states_and_jobs_are_listed(tmp_path):
    app = _app(tmp_path)
    client = TestClient(app)
    client.post("/api/v1/internal/sources", json=_source_payload(), headers=_auth_header())
    SessionLocal = app.state.production_sessionmaker
    now = datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc)
    with SessionLocal() as session:
        session.add(FetchJobRecord(source_id="openai_news", status="pending", priority=10, run_after=now))
        session.commit()

    states = client.get("/api/v1/internal/source-states?channel=ai", headers=_auth_header())
    jobs = client.get("/api/v1/internal/jobs?status=pending", headers=_auth_header())

    assert states.status_code == 200
    assert states.json()["sourceStates"][0]["sourceId"] == "openai_news"
    assert states.json()["sourceStates"][0]["healthScore"] == 100
    assert jobs.json()["jobs"][0]["sourceId"] == "openai_news"


def test_internal_source_diagnostics_exposes_fetch_and_screening_reasons(tmp_path):
    app = _app(tmp_path)
    client = TestClient(app)
    client.post("/api/v1/internal/sources", json=_source_payload(), headers=_auth_header())
    SessionLocal = app.state.production_sessionmaker
    now = datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc)
    with SessionLocal() as session:
        session.add(
            StrategyVersionRecord(
                id="ai-default-v1",
                channel="ai",
                name="Default",
                status="active",
                prefilter_prompt_version="prefilter-v1",
                score_prompt_version="score-v1",
                rank_formula_version="rank-v1",
                thresholds_json={"selected": 80},
                model_config_json={"provider": "deepseek"},
                activated_at=now,
            )
        )
        run = FetchRunRecord(
            source_id="openai_news",
            status="succeeded",
            started_at=now,
            finished_at=now,
            http_status=200,
            content_type="application/rss+xml",
            bytes_received=128,
            item_count=1,
            metadata_json={
                "candidate_items": 3,
                "accepted_items": 1,
                "skipped_missing_date": 2,
                "skipped_old_items": 0,
                "skipped_invalid_original_url": 0,
            },
        )
        session.add(run)
        session.flush()
        raw = RawDocumentRecord(
            fetch_run_id=run.id,
            source_id="openai_news",
            url="https://openai.com/news/no-date",
            canonical_url="https://openai.com/news/no-date",
            content_type="text/html",
            body_text="No date.",
            body_html="<article>No date.</article>",
            response_headers_json={},
            content_hash="diagnostic-raw",
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
                screen_bucket="invalid",
                relevance_score=0,
                confidence_score=0,
                category="ai_models",
                title_cn="缺少时间",
                summary_cn="缺少明确发布时间。",
                tags_json=["缺少时间", "抓取诊断"],
                reason_code="missing_publish_time",
                reason_cn="缺少明确发布时间。",
                raw_json={"provider": "deepseek", "model": "deepseek-v4-flash"},
            )
        )
        session.commit()

    response = client.get("/api/v1/internal/source-diagnostics?channel=ai", headers=_auth_header())

    assert response.status_code == 200
    diagnostic = response.json()["sourceDiagnostics"][0]
    assert diagnostic["sourceId"] == "openai_news"
    assert diagnostic["diagnosticStatus"] == "missing_publish_time"
    assert diagnostic["lastRun"]["candidateItems"] == 3
    assert diagnostic["screening"]["latestReasonCode"] == "missing_publish_time"


def test_internal_strategy_feedback_and_evaluation_run_endpoints(tmp_path):
    app = _app(tmp_path)
    client = TestClient(app)
    strategy_payload = {
        "id": "ai-default-v1",
        "channel": "ai",
        "name": "Default",
        "status": "draft",
        "prefilterPromptVersion": "prefilter-v1",
        "scorePromptVersion": "score-v1",
        "rankFormulaVersion": "rank-v1",
        "thresholds": {"selected": 72},
        "modelConfig": {"provider": "fake"},
    }

    created_strategy = client.post("/api/v1/internal/strategy-versions", json=strategy_payload, headers=_auth_header())
    listed_strategy = client.get("/api/v1/internal/strategy-versions?channel=ai", headers=_auth_header())
    feedback = client.post(
        "/api/v1/internal/feedback-events",
        json={"channel": "ai", "feedbackType": "false_positive", "reason": "噪声", "actor": "operator"},
        headers=_auth_header(),
    )
    evaluation = client.post(
        "/api/v1/internal/evaluation-runs",
        json={
            "channel": "ai",
            "strategyVersion": "ai-default-v1",
            "name": "smoke backtest",
            "request": {"sampleSize": 20},
        },
        headers=_auth_header(),
    )

    assert created_strategy.status_code == 200
    assert listed_strategy.json()["strategyVersions"][0]["id"] == "ai-default-v1"
    assert feedback.json()["feedbackEvent"]["feedbackType"] == "false_positive"
    assert evaluation.json()["evaluationRun"]["status"] == "pending"
