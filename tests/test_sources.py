from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from intel_engine.db import (
    create_engine_from_settings,
    init_schema,
    sessionmaker_for_engine,
)
from intel_engine.models import SourceRecord, SourceStateRecord
from intel_engine.settings import Settings
from intel_engine.source_seed import seed_sources_from_channel_configs
from intel_engine.channel_config import (
    CHANNELS_DIR,
    CollectionPolicy,
    load_channel_configs,
)
from intel_engine.sources import (
    SourceRegistry,
    SourceUpsert,
    normalize_publisher_key,
    publisher_key_from_url,
)


def _session_factory(tmp_path):
    settings = Settings(database_url=f"sqlite+pysqlite:///{tmp_path / 'test.sqlite3'}")
    engine = create_engine_from_settings(settings)
    init_schema(engine)
    return sessionmaker_for_engine(engine)


def _write_channel_config(channels_dir):
    channels_dir.mkdir(exist_ok=True)
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
        source = session.scalar(
            select(SourceRecord).where(SourceRecord.id == "openai_news")
        )

    assert source is not None
    assert source.channel == "ai"
    assert source.source_type == "html"
    assert source.tier == "T1"
    assert source.fetch_adapter == "http_article"
    assert source.authority_weight == 95
    assert source.default_categories == ["ai_models"]
    assert source.fetch_interval_minutes == 720
    assert source.visibility == "public"
    assert source.source_group == "official"
    assert source.collection_status == "collectable"
    assert source.free_access is True


def test_bundled_channel_configs_have_production_source_coverage():
    configs = {config.id: config for config in load_channel_configs(CHANNELS_DIR)}

    assert len(configs["ai"].sources) >= 300
    assert len(configs["amazon"].sources) >= 300
    assert {source.trust_level for source in configs["ai"].sources}.issuperset(
        {"official", "authority", "expert", "media"}
    )
    assert {source.trust_level for source in configs["amazon"].sources}.issuperset(
        {"official", "authority", "expert", "media"}
    )
    assert all(
        60 <= source.base_weight <= 100
        for config in configs.values()
        for source in config.sources
    )
    assert all(
        source.crawl_interval_minutes == 720
        for config in configs.values()
        for source in config.sources
    )


def test_bundled_enabled_sources_are_stable_for_production_collection():
    configs = {config.id: config for config in load_channel_configs(CHANNELS_DIR)}

    stable_collection_parsers = {"rss", "atom", "aihot_api", "html_list"}
    for channel_id in ("ai", "amazon"):
        enabled_sources = [
            source for source in configs[channel_id].sources if source.enabled
        ]
        assert len(enabled_sources) >= 300
        assert all(
            source.parser_type in stable_collection_parsers
            for source in enabled_sources
        )
        assert all(source.url.startswith("https://") for source in enabled_sources)


def test_seed_supports_curated_api_and_html_list_adapters(tmp_path):
    SessionLocal = _session_factory(tmp_path)

    with SessionLocal() as session:
        seed_sources_from_channel_configs(session, CHANNELS_DIR)
        aihot = session.scalar(
            select(SourceRecord).where(SourceRecord.id == "aihot_virxact_selected")
        )
        amazon_ads = session.scalar(
            select(SourceRecord).where(SourceRecord.id == "amazon_ads_updates")
        )

    assert aihot is not None
    assert aihot.fetch_adapter == "aihot_api"
    assert aihot.source_group == "curated"
    assert amazon_ads is not None
    assert amazon_ads.fetch_adapter == "html_list"


def test_amazon_sources_prioritize_precise_official_or_seller_feeds():
    amazon = {config.id: config for config in load_channel_configs(CHANNELS_DIR)}[
        "amazon"
    ]
    sources = {source.id: source for source in amazon.sources}

    assert sources["amazon_sp_api_release_notes"].enabled is True
    assert sources["amazon_sp_api_release_notes"].parser_type == "html_list"
    assert sources["amazon_ads_updates"].enabled is False
    assert sources["amazon_ads_updates"].metadata.get("collection_status") == "watch"
    assert sources["amazon_ads_updates"].parser_type == "html_list"
    for precise_feed in (
        "marketplace_pulse",
        "junglescout_blog",
        "pacvue_blog",
        "ad_badger_blog",
        "datahawk_blog",
        "amazon_shipping_blog",
        "sellerboard_blog",
        "repricercom_blog",
        "supplykick_blog",
    ):
        assert sources[precise_feed].enabled is True
        assert sources[precise_feed].parser_type == "rss"
    assert sources["datahawk_blog"].url == "https://datahawk.co/feed/"
    assert sources["helium10_blog"].enabled is False
    assert sources["sellerapp_blog"].enabled is False
    assert sources["helium10_blog"].metadata.get("collection_status") == "unavailable"
    assert sources["sellerapp_blog"].metadata.get("collection_status") == "unavailable"


def test_interval_change_realigns_next_fetch_from_last_success(tmp_path):
    channels_dir = tmp_path / "channels"
    _write_channel_config(channels_dir)
    SessionLocal = _session_factory(tmp_path)
    now = datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc)

    with SessionLocal() as session:
        seed_sources_from_channel_configs(
            session,
            channels_dir,
            policy=CollectionPolicy(crawl_interval_minutes=60),
        )
        SourceRegistry(session).update_state(
            "openai_news",
            last_success_at=now,
            next_fetch_at=now + timedelta(minutes=60),
        )
        seed_sources_from_channel_configs(
            session,
            channels_dir,
            policy=CollectionPolicy(crawl_interval_minutes=720),
        )
        source = session.get(SourceRecord, "openai_news")
        state = session.get(SourceStateRecord, "openai_news")

    assert source is not None
    assert source.fetch_interval_minutes == 720
    assert state is not None
    assert state.next_fetch_at == now + timedelta(minutes=720)


def test_seed_synchronizes_legacy_sources_to_global_policy_and_identity(tmp_path):
    channels_dir = tmp_path / "channels"
    _write_channel_config(channels_dir)
    SessionLocal = _session_factory(tmp_path)

    with SessionLocal() as session:
        SourceRegistry(session).upsert_source(
            SourceUpsert(
                id="legacy_huggingface",
                channel="ai",
                source_type="rss",
                tier="T2",
                name="Legacy Hugging Face",
                url="https://huggingface.co/blog/feed.xml",
                language="en",
                region="global",
                marketplace=None,
                authority_weight=80,
                noise_level=0.2,
                fetch_adapter="rss",
                parser_type="rss",
                default_categories=["ai_models"],
                fetch_interval_minutes=60,
                enabled=True,
                visibility="public",
                source_group="media",
                publisher_key="media:legacy_huggingface",
            )
        )
        seed_sources_from_channel_configs(session, channels_dir)
        source = session.get(SourceRecord, "legacy_huggingface")

    assert source is not None
    assert source.fetch_interval_minutes == 720
    assert source.publisher_key == "company:huggingface"


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
        source = session.scalar(
            select(SourceRecord).where(SourceRecord.id == "example_feed")
        )
        state = session.scalar(
            select(SourceStateRecord).where(
                SourceStateRecord.source_id == "example_feed"
            )
        )

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


def test_publisher_identity_groups_multiple_endpoints_from_the_same_owner():
    assert (
        publisher_key_from_url(
            "https://github.com/openai/openai-python/releases.atom",
            "openai_python",
        )
        == "github_org:openai"
    )
    assert (
        publisher_key_from_url(
            "https://github.com/openai/openai-node/releases.atom",
            "openai_node",
        )
        == "github_org:openai"
    )
    assert (
        publisher_key_from_url("https://www.reuters.com/technology/", "reuters")
        == "reuters.com"
    )
    assert (
        normalize_publisher_key(
            "github_org:microsoft",
            "https://github.com/microsoft/semantic-kernel/releases.atom",
            "semantic_kernel",
        )
        == "company:microsoft"
    )
    assert (
        normalize_publisher_key(
            None,
            "https://blogs.microsoft.com/ai/feed/",
            "microsoft_ai",
        )
        == "company:microsoft"
    )
    assert (
        normalize_publisher_key(
            "github_org:huggingface",
            "https://github.com/huggingface/transformers/releases.atom",
            "transformers",
        )
        == "company:huggingface"
    )
    assert (
        normalize_publisher_key(
            "github_org:nvidia",
            "https://github.com/NVIDIA/TensorRT/releases.atom",
            "tensorrt",
        )
        == "company:nvidia"
    )
    assert (
        normalize_publisher_key(
            "github_org:nvidia-nemo",
            "https://github.com/NVIDIA-NeMo/NeMo/releases.atom",
            "nemo",
        )
        == "company:nvidia"
    )
    assert (
        normalize_publisher_key(
            "github_org:google-ai-edge",
            "https://github.com/google-ai-edge/mediapipe/releases.atom",
            "mediapipe",
        )
        == "company:google"
    )
    assert (
        normalize_publisher_key(
            None,
            "https://export.arxiv.org/rss/cs.AI",
            "arxiv_ai",
        )
        == "research:arxiv"
    )
