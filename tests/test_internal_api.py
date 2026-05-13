from __future__ import annotations

import base64
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from intel_engine.main import create_app
from intel_engine.models import FetchJobRecord


def _app(tmp_path):
    return create_app(
        db_path=tmp_path / "legacy.sqlite3",
        production_database_url=f"sqlite+pysqlite:///{tmp_path / 'production.sqlite3'}",
    )


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
