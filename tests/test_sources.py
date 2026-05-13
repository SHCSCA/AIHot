from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from intel_engine.db import create_engine_from_settings, init_schema, sessionmaker_for_engine
from intel_engine.models import SourceRecord, SourceStateRecord
from intel_engine.settings import Settings
from intel_engine.source_seed import seed_sources_from_channel_configs
from intel_engine.channel_config import CHANNELS_DIR, load_channel_configs
from intel_engine.sources import SourceRegistry, SourceUpsert


def _session_factory(tmp_path):
    settings = Settings(database_url=f"sqlite+pysqlite:///{tmp_path / 'test.sqlite3'}")
    engine = create_engine_from_settings(settings)
    init_schema(engine)
    return sessionmaker_for_engine(engine)


def _write_channel_config(channels_dir):
    channels_dir.mkdir()
    (channels_dir / "ai.yaml").write_text(
        """
id: ai
name: AI 情报
description: AI 模型动态
categories:
  - id: ai_models
    label: 模型发布
scoring: {}
sources:
  - id: openai_news
    source_type: website
    name: OpenAI News
    url: https://openai.com/news/
    language: en
    region: global
    trust_level: official
    base_weight: 95
    default_categories: [ai_models]
    crawl_interval_minutes: 360
    parser_type: website
    enabled: true
""",
        encoding="utf-8",
    )


def test_seed_sources_from_channel_configs_is_idempotent(tmp_path):
    channels_dir = tmp_path / "channels"
    _write_channel_config(channels_dir)
    SessionLocal = _session_factory(tmp_path)

    with SessionLocal() as session:
        first = seed_sources_from_channel_configs(session, channels_dir)
        second = seed_sources_from_channel_configs(session, channels_dir)
        source_count = len(session.scalars(select(SourceRecord)).all())
        state_count = len(session.scalars(select(SourceStateRecord)).all())

    assert first.created == 1
    assert first.updated == 0
    assert second.created == 0
    assert second.updated == 1
    assert source_count == 1
    assert state_count == 1


def test_seed_maps_yaml_source_to_production_source(tmp_path):
    channels_dir = tmp_path / "channels"
    _write_channel_config(channels_dir)
    SessionLocal = _session_factory(tmp_path)

    with SessionLocal() as session:
        seed_sources_from_channel_configs(session, channels_dir)
        source = session.scalar(select(SourceRecord).where(SourceRecord.id == "openai_news"))

    assert source is not None
    assert source.channel == "ai"
    assert source.source_type == "html"
    assert source.tier == "T1"
    assert source.fetch_adapter == "http_article"
    assert source.authority_weight == 95
    assert source.default_categories == ["ai_models"]
    assert source.fetch_interval_minutes == 60
    assert source.visibility == "public"
    assert source.source_group == "official"
    assert source.collection_status == "collectable"
    assert source.free_access is True


def test_bundled_channel_configs_have_production_source_coverage():
    configs = {config.id: config for config in load_channel_configs(CHANNELS_DIR)}

    assert len(configs["ai"].sources) >= 20
    assert len(configs["amazon"].sources) >= 20
    assert {source.trust_level for source in configs["ai"].sources}.issuperset({"official", "authority", "expert", "media"})
    assert {source.trust_level for source in configs["amazon"].sources}.issuperset({"official", "authority", "expert", "media"})
    assert all(60 <= source.base_weight <= 100 for config in configs.values() for source in config.sources)


def test_bundled_enabled_sources_are_rss_first_for_hourly_production():
    configs = {config.id: config for config in load_channel_configs(CHANNELS_DIR)}

    for channel_id in ("ai", "amazon"):
        enabled_sources = [source for source in configs[channel_id].sources if source.enabled]
        assert len(enabled_sources) >= 15
        assert all(source.parser_type == "rss" for source in enabled_sources)
        assert all(source.url.startswith("https://") for source in enabled_sources)


def test_registry_can_upsert_toggle_and_update_state(tmp_path):
    SessionLocal = _session_factory(tmp_path)
    now = datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc)

    with SessionLocal() as session:
        registry = SourceRegistry(session)
        registry.upsert_source(
            SourceUpsert(
                id="example_feed",
                channel="ai",
                source_type="rss",
                tier="T2",
                name="Example Feed",
                url="https://example.com/feed.xml",
                language="en",
                region="global",
                marketplace=None,
                authority_weight=80,
                noise_level=0.2,
                fetch_adapter="rss",
                parser_type="rss",
                default_categories=["industry"],
                fetch_interval_minutes=120,
                enabled=True,
                visibility="internal",
                source_group="media",
                contributor_no="AIHOT-009",
                social_handle=None,
                collection_status="collectable",
                free_access=True,
                notes=None,
            )
        )
        registry.set_enabled("example_feed", False)
        registry.update_state(
            "example_feed",
            last_success_at=now,
            error_streak=0,
            duplicate_ratio=0.1,
            noise_ratio=0.2,
            health_score=92,
        )
        session.commit()

    with SessionLocal() as session:
        source = session.scalar(select(SourceRecord).where(SourceRecord.id == "example_feed"))
        state = session.scalar(select(SourceStateRecord).where(SourceStateRecord.source_id == "example_feed"))

    assert source is not None
    assert source.enabled is False
    assert source.source_group == "media"
    assert source.contributor_no == "AIHOT-009"
    assert source.collection_status == "collectable"
    assert source.free_access is True
    assert state is not None
    assert state.last_success_at == now
    assert state.duplicate_ratio == 0.1
    assert state.health_score == 92
