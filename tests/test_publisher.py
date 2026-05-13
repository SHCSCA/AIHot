from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from intel_engine.main import create_app
from intel_engine.models import (
    ClusterMemberRecord,
    DailyDigestRecord,
    EventClusterRecord,
    FetchRunRecord,
    ModelScoreRecord,
    NormalizedItemRecord,
    RawDocumentRecord,
    SourceRecord,
    SourceStateRecord,
    StrategyVersionRecord,
)
from intel_engine.rss import build_events_feed


def _app_with_event(tmp_path):
    app = create_app(
        db_path=tmp_path / "legacy.sqlite3",
        production_database_url=f"sqlite+pysqlite:///{tmp_path / 'production.sqlite3'}",
    )
    SessionLocal = app.state.production_sessionmaker
    now = datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc)
    with SessionLocal() as session:
        source = SourceRecord(
            id="openai_news",
            channel="ai",
            source_type="html",
            tier="T1",
            name="OpenAI News",
            url="https://openai.com/news/",
            language="en",
            region="global",
            marketplace=None,
            authority_weight=95,
            noise_level=0.05,
            fetch_adapter="http_article",
            parser_type="website",
            default_categories=["ai_models"],
            fetch_interval_minutes=60,
            enabled=True,
            visibility="public",
            notes=None,
        )
        session.add_all(
            [
                source,
                SourceStateRecord(source_id="openai_news"),
                StrategyVersionRecord(
                    id="ai-default-v1",
                    channel="ai",
                    name="Default",
                    status="active",
                    prefilter_prompt_version="prefilter-v1",
                    score_prompt_version="score-v1",
                    rank_formula_version="rank-v1",
                    thresholds_json={"ai_models": 75},
                    model_config_json={"provider": "fake"},
                    activated_at=now,
                ),
            ]
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
            content_hash="raw-hash",
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
            content_hash="item-hash",
        )
        session.add(item)
        session.flush()
        session.add(
            ModelScoreRecord(
                item_id=item.id,
                strategy_version="ai-default-v1",
                model="deepseek-v4-flash",
                category="ai_models",
                relevance_score=91,
                impact_score=90,
                novelty_score=86,
                actionability_score=72,
                credibility_score=95,
                seller_action_level="review",
                reason="DeepSeek 认为这是高权威模型发布，值得关注。",
                raw_json={"provider": "deepseek", "model": "deepseek-v4-flash"},
            )
        )
        cluster = EventClusterRecord(
            channel="ai",
            canonical_title="OpenAI 发布 GPT-5",
            main_item_id=item.id,
            category="ai_models",
            first_seen_at=now,
            last_seen_at=now,
            member_count=1,
            source_count=1,
            cluster_score=91.5,
            embedding=[0.1, 0.2],
        )
        session.add(cluster)
        session.flush()
        session.add(
            ClusterMemberRecord(
                cluster_id=cluster.id,
                item_id=item.id,
                source_id="openai_news",
                relation_score=100,
                is_main=True,
            )
        )
        session.add(
            DailyDigestRecord(
                channel="ai",
                digest_date=date(2026, 5, 11),
                strategy_version="ai-default-v1",
                title="AI 日报",
                sections_json={"highlights": [{"eventId": str(cluster.id), "title": cluster.canonical_title}]},
                published=True,
            )
        )
        session.commit()
    return app


def test_public_events_endpoint_returns_event_clusters_without_internal_fields(tmp_path):
    client = TestClient(_app_with_event(tmp_path))

    response = client.get("/api/v1/public/events?channel=ai")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    event = payload["events"][0]
    assert event["title"] == "OpenAI 发布 GPT-5"
    assert event["summary"] == "OpenAI 发布新模型。"
    assert event["entryReason"] == "DeepSeek 认为这是高权威模型发布，值得关注。"
    assert event["mainItem"]["summary"] == "OpenAI 发布新模型。"
    assert event["mainItem"]["sourceId"] == "openai_news"
    assert "embedding" not in event
    assert "strategyVersion" not in event
    assert "thresholdUsed" not in event


def test_public_events_uses_cursor_pagination_without_duplicates(tmp_path):
    app = _app_with_event(tmp_path)
    SessionLocal = app.state.production_sessionmaker
    with SessionLocal() as session:
        base = datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc)
        _add_public_event(session, event_id_suffix="2", observed_at=base + timedelta(hours=1), title="第二条事件")
        _add_public_event(session, event_id_suffix="3", observed_at=base + timedelta(hours=2), title="第三条事件")
        session.commit()
    client = TestClient(app)

    first = client.get("/api/v1/public/events?channel=ai&date=2026-05-11&take=1").json()
    second = client.get(f"/api/v1/public/events?channel=ai&date=2026-05-11&take=1&cursor={first['nextCursor']}").json()

    assert first["hasNext"] is True
    assert first["nextCursor"]
    assert first["events"][0]["title"] == "第三条事件"
    assert second["events"][0]["title"] == "第二条事件"
    assert second["events"][0]["id"] != first["events"][0]["id"]


def test_public_event_detail_returns_members(tmp_path):
    client = TestClient(_app_with_event(tmp_path))

    response = client.get("/api/v1/public/events/1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["event"]["id"] == "1"
    assert payload["members"][0]["title"] == "OpenAI 发布 GPT-5"


def test_public_daily_endpoint_returns_published_digest(tmp_path):
    client = TestClient(_app_with_event(tmp_path))

    response = client.get("/api/v1/public/daily?channel=ai&date=2026-05-11")

    assert response.status_code == 200
    payload = response.json()
    assert payload["daily"]["title"] == "AI 日报"
    assert payload["daily"]["sections"]["highlights"][0]["title"] == "OpenAI 发布 GPT-5"


def test_build_events_feed_uses_public_event_fields_only():
    xml = build_events_feed(
        [
            {
                "id": "1",
                "title": "OpenAI 发布 GPT-5",
                "url": "https://openai.com/news/gpt-5",
                "summary": "OpenAI 发布新模型。",
                "publishedAt": "2026-05-11T10:00:00+00:00",
            }
        ],
        title="AI 情报",
        link="https://example.com/feed.xml",
        description="精选 AI 情报",
    )

    assert "<rss" in xml
    assert "OpenAI 发布 GPT-5" in xml
    assert "strategyVersion" not in xml


def _add_public_event(session, *, event_id_suffix: str, observed_at: datetime, title: str) -> None:
    run = FetchRunRecord(
        source_id="openai_news",
        status="succeeded",
        started_at=observed_at,
        finished_at=observed_at,
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
        url=f"https://openai.com/news/event-{event_id_suffix}",
        canonical_url=f"https://openai.com/news/event-{event_id_suffix}",
        content_type="text/html",
        body_text=f"{title} raw summary.",
        body_html=f"<article>{title}</article>",
        response_headers_json={},
        content_hash=f"raw-hash-{event_id_suffix}",
        fetched_at=observed_at,
    )
    session.add(raw)
    session.flush()
    item = NormalizedItemRecord(
        channel="ai",
        source_id="openai_news",
        raw_document_id=raw.id,
        title_original=title,
        title_cn=title,
        url=f"https://openai.com/news/event-{event_id_suffix}",
        canonical_url=f"https://openai.com/news/event-{event_id_suffix}",
        summary_original=f"{title} raw summary.",
        summary_cn=f"{title} 中文摘要。",
        published_at=observed_at,
        fetched_at=observed_at,
        language="en",
        content_hash=f"item-hash-{event_id_suffix}",
    )
    session.add(item)
    session.flush()
    session.add(
        ModelScoreRecord(
            item_id=item.id,
            strategy_version="ai-default-v1",
            model="deepseek-v4-flash",
            category="ai_models",
            relevance_score=91,
            impact_score=90,
            novelty_score=86,
            actionability_score=72,
            credibility_score=95,
            seller_action_level="review",
            reason=f"{title} 推荐理由。",
            raw_json={"provider": "deepseek", "model": "deepseek-v4-flash"},
        )
    )
    cluster = EventClusterRecord(
        channel="ai",
        canonical_title=title,
        main_item_id=item.id,
        category="ai_models",
        first_seen_at=observed_at,
        last_seen_at=observed_at,
        member_count=1,
        source_count=1,
        cluster_score=90,
        embedding=[0.1, 0.2],
    )
    session.add(cluster)
    session.flush()
    session.add(
        ClusterMemberRecord(
            cluster_id=cluster.id,
            item_id=item.id,
            source_id="openai_news",
            relation_score=100,
            is_main=True,
        )
    )
