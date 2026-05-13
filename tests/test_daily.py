from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from intel_engine.daily import generate_daily_digest
from intel_engine.db import create_engine_from_settings, init_schema, sessionmaker_for_engine
from intel_engine.main import create_app
from intel_engine.models import (
    ClusterMemberRecord,
    DailyDigestRecord,
    EventClusterRecord,
    FetchRunRecord,
    ModelScoreRecord,
    NormalizedItemRecord,
    RankedItemRecord,
    RawDocumentRecord,
    RawScreeningResultRecord,
    SourceRecord,
    StrategyVersionRecord,
)
from intel_engine.settings import Settings


def _session_factory(tmp_path):
    settings = Settings(database_url=f"sqlite+pysqlite:///{tmp_path / 'production.sqlite3'}")
    engine = create_engine_from_settings(settings)
    init_schema(engine)
    return sessionmaker_for_engine(engine)


def _seed_strategy_and_event(session):
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    session.add(
        SourceRecord(
            id="openai_news",
            channel="ai",
            source_type="rss",
            tier="T1",
            name="OpenAI News",
            url="https://openai.com/news/",
            language="en",
            region="global",
            marketplace=None,
            authority_weight=95,
            noise_level=0.05,
            fetch_adapter="rss",
            parser_type="rss",
            default_categories=["ai_models"],
            fetch_interval_minutes=60,
            enabled=True,
            visibility="public",
            notes=None,
        )
    )
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
    session.flush()
    run = FetchRunRecord(
        source_id="openai_news",
        status="succeeded",
        started_at=now,
        finished_at=now,
        http_status=200,
        content_type="text/html",
        bytes_received=128,
        item_count=1,
        metadata_json={},
    )
    session.add(run)
    session.flush()
    raw = RawDocumentRecord(
        fetch_run_id=run.id,
        source_id="openai_news",
        url="https://openai.com/news/gpt-5",
        canonical_url="https://openai.com/news/gpt-5",
        content_type="text/html",
        body_text="OpenAI model update.",
        body_html="<article>OpenAI model update.</article>",
        response_headers_json={},
        content_hash="daily-raw-hash",
        fetched_at=now,
    )
    session.add(raw)
    session.flush()
    item = NormalizedItemRecord(
        channel="ai",
        source_id="openai_news",
        raw_document_id=raw.id,
        title_original="OpenAI launches GPT-5",
        title_cn="OpenAI 发布 GPT-5",
        url="https://openai.com/news/gpt-5",
        canonical_url="https://openai.com/news/gpt-5",
        summary_original="OpenAI model update.",
        summary_cn="OpenAI 发布新模型。",
        published_at=now,
        fetched_at=now,
        language="en",
        content_hash="daily-item-hash",
    )
    session.add(item)
    session.flush()
    session.add(
        RawScreeningResultRecord(
            raw_document_id=raw.id,
            strategy_version="ai-default-v1",
            provider="deepseek",
            model="deepseek-v4-flash",
            screen_status="accepted",
            screen_bucket="core",
            relevance_score=92,
            confidence_score=88,
            category="ai_models",
            title_cn="OpenAI 发布 GPT-5",
            summary_cn="OpenAI 发布新模型。",
            tags_json=["模型发布", "官方动态"],
            reason_code="accepted",
            reason_cn="官方模型发布。",
            raw_json={"provider": "deepseek", "model": "deepseek-v4-flash"},
        )
    )
    session.add(
        ModelScoreRecord(
            item_id=item.id,
            strategy_version="ai-default-v1",
            model="deepseek-v4-pro",
            category="ai_models",
            relevance_score=91,
            impact_score=90,
            novelty_score=86,
            actionability_score=72,
            credibility_score=95,
            seller_action_level="review",
            reason="DeepSeek 认为这是高权威模型发布，值得关注。",
            raw_json={
                "provider": "deepseek",
                "model": "deepseek-v4-pro",
                "confidenceScore": 88,
                "tags": ["模型发布", "官方动态"],
                "eventType": "model_release",
                "keyFacts": ["OpenAI 发布 GPT-5"],
                "riskFlags": [],
            },
        )
    )
    session.add(
        RankedItemRecord(
            item_id=item.id,
            strategy_version="ai-default-v1",
            source_weight=95,
            category_weight=80,
            freshness_weight=100,
            duplicate_penalty=0,
            channel_impact_weight=90,
            final_score=91,
            selected=True,
            threshold_used=77,
            selection_reason="达到精选阈值",
        )
    )
    session.flush()
    session.add(
        EventClusterRecord(
            channel="ai",
            canonical_title="OpenAI 发布 GPT-5",
            main_item_id=item.id,
            category="ai_models",
            first_seen_at=now,
            last_seen_at=now,
            member_count=2,
            source_count=2,
            cluster_score=91,
            embedding=[0.1, 0.2],
            review_status="approved",
            review_note="AI 自动审核通过。",
            reviewed_by="ai-reviewer",
            reviewed_at=now,
        )
    )
    session.flush()
    cluster = session.scalar(select(EventClusterRecord))
    assert cluster is not None
    session.add(
        ClusterMemberRecord(
            cluster_id=cluster.id,
            item_id=item.id,
            source_id="openai_news",
            relation_score=100,
            is_main=True,
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
    assert highlight["summary"] == "OpenAI 发布新模型。"
    assert highlight["entryReason"] == "DeepSeek 认为这是高权威模型发布，值得关注。"
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
