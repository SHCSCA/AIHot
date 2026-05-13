from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from intel_engine.daily import generate_daily_digest
from intel_engine.db import create_engine_from_settings, init_schema, sessionmaker_for_engine
from intel_engine.main import create_app
from intel_engine.models import DailyDigestRecord, EventClusterRecord, StrategyVersionRecord
from intel_engine.settings import Settings


def _session_factory(tmp_path):
    settings = Settings(database_url=f"sqlite+pysqlite:///{tmp_path / 'production.sqlite3'}")
    engine = create_engine_from_settings(settings)
    init_schema(engine)
    return sessionmaker_for_engine(engine)


def _seed_strategy_and_event(session):
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    session.add(
        StrategyVersionRecord(
            id="ai-default-v1",
            channel="ai",
            name="Default",
            status="active",
            prefilter_prompt_version="prefilter-v1",
            score_prompt_version="score-v1",
            rank_formula_version="rank-v1",
            thresholds_json={"selected": 72},
            model_config_json={"provider": "fake"},
            activated_at=now,
        )
    )
    session.add(
        EventClusterRecord(
            channel="ai",
            canonical_title="OpenAI 发布 GPT-5",
            main_item_id=None,
            category="ai_models",
            first_seen_at=now,
            last_seen_at=now,
            member_count=2,
            source_count=2,
            cluster_score=91,
            embedding=[0.1, 0.2],
        )
    )
    session.commit()


def test_generate_daily_digest_is_idempotent(tmp_path):
    SessionLocal = _session_factory(tmp_path)
    digest_date = date(2026, 5, 12)
    with SessionLocal() as session:
        _seed_strategy_and_event(session)
        first = generate_daily_digest(session, channel="ai", digest_date=digest_date, strategy_version="ai-default-v1")
        second = generate_daily_digest(session, channel="ai", digest_date=digest_date, strategy_version="ai-default-v1")
        digests = session.scalars(select(DailyDigestRecord)).all()

    assert first.created is True
    assert second.created is False
    assert len(digests) == 1
    highlight = digests[0].sections_json["highlights"][0]
    assert highlight["title"] == "OpenAI 发布 GPT-5"
    assert highlight["summary"] == "待 AI 处理后生成中文摘要。"
    assert highlight["entryReason"] == "待 AI 处理后生成推荐理由。"
    assert highlight["lastSeenAt"] == "2026-05-12T08:00:00+00:00"


def test_feed_endpoints_return_public_rss_without_internal_fields(tmp_path):
    db_url = f"sqlite+pysqlite:///{tmp_path / 'production.sqlite3'}"
    app = create_app(db_path=tmp_path / "legacy.sqlite3", production_database_url=db_url)
    SessionLocal = app.state.production_sessionmaker
    digest_date = date(2026, 5, 12)
    with SessionLocal() as session:
        _seed_strategy_and_event(session)
        generate_daily_digest(session, channel="ai", digest_date=digest_date, strategy_version="ai-default-v1")
        session.commit()
    client = TestClient(app)

    events_feed = client.get("/feed/ai/events.xml")
    daily_feed = client.get("/feed/ai/daily.xml")

    assert events_feed.status_code == 200
    assert daily_feed.status_code == 200
    assert "OpenAI 发布 GPT-5" in events_feed.text
    assert "AI 日报" in daily_feed.text
    assert "strategy" not in events_feed.text
    assert "embedding" not in events_feed.text
