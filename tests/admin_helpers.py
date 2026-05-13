from __future__ import annotations

import base64
from datetime import date, datetime, timezone

from intel_engine.main import create_app
from intel_engine.models import (
    ClusterMemberRecord,
    DailyDigestRecord,
    EventClusterRecord,
    FetchJobRecord,
    FetchRunRecord,
    ModelScoreRecord,
    NormalizedItemRecord,
    RawDocumentRecord,
    RawScreeningResultRecord,
    RankedItemRecord,
    SourceRecord,
    SourceStateRecord,
    StrategyVersionRecord,
)


def auth_header() -> dict[str, str]:
    token = base64.b64encode(b"admin:admin").decode("ascii")
    return {"Authorization": f"Basic {token}"}


def app_with_admin_data(tmp_path):
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
            source_group="official",
            contributor_no="AIHOT-001",
            social_handle=None,
            collection_status="collectable",
            free_access=True,
            notes=None,
        )
        strategy = StrategyVersionRecord(
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
        session.add_all(
            [
                source,
                SourceStateRecord(source_id="openai_news", health_score=75, error_streak=1),
                strategy,
                FetchJobRecord(source_id="openai_news", status="failed", priority=10, run_after=now, last_error="HTTP 403"),
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
                reason_cn="官方模型发布，信息增量明确。",
                raw_json={"provider": "deepseek", "model": "deepseek-v4-flash"},
            )
        )
        session.add(
            RankedItemRecord(
                item_id=item.id,
                strategy_version="ai-default-v1",
                source_weight=95,
                category_weight=90,
                freshness_weight=88,
                duplicate_penalty=0,
                channel_impact_weight=90,
                final_score=91.5,
                selected=True,
                threshold_used=72,
                selection_reason="测试精选",
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
