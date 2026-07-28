from pathlib import Path

import pytest

from intel_engine.channel_config import (
    COLLECTION_CONFIG_PATH,
    CollectionPolicy,
    load_channel_configs,
    load_collection_policy,
)


def _write_channel_config(
    channels_dir: Path,
    *,
    crawl_interval_minutes: object = None,
) -> None:
    channels_dir.mkdir()
    interval_line = (
        ""
        if crawl_interval_minutes is None
        else f"    crawl_interval_minutes: {crawl_interval_minutes}\n"
    )
    (channels_dir / "ai.yaml").write_text(
        f"""
id: ai
name: AI
description: AI intelligence
categories:
  - id: models
    label: Models
scoring: {{}}
sources:
  - id: example
    source_type: rss
    name: Example
    url: https://example.com/feed.xml
    language: en
    region: global
    trust_level: official
    base_weight: 90
    default_categories: [models]
{interval_line}    parser_type: rss
    enabled: true
""",
        encoding="utf-8",
    )


def test_loads_ai_and_amazon_channels():
    configs = {config.id: config for config in load_channel_configs()}

    assert set(configs) == {"ai", "amazon"}
    assert configs["ai"].categories
    assert configs["amazon"].categories
    assert configs["ai"].sources
    assert configs["amazon"].sources


def test_project_collection_policy_defaults_to_twelve_hours():
    policy = load_collection_policy(COLLECTION_CONFIG_PATH)

    assert policy.crawl_interval_minutes == 720


def test_missing_collection_policy_has_no_hardcoded_fallback(tmp_path):
    with pytest.raises(FileNotFoundError, match="Collection policy does not exist"):
        load_collection_policy(tmp_path / "missing.yaml")


def test_source_inherits_project_collection_policy(tmp_path):
    channels_dir = tmp_path / "channels"
    _write_channel_config(channels_dir)

    source = load_channel_configs(channels_dir)[0].sources[0]

    assert source.crawl_interval_minutes == 720


def test_temporary_channels_can_use_an_explicit_collection_policy(tmp_path):
    channels_dir = tmp_path / "channels"
    _write_channel_config(channels_dir)

    source = load_channel_configs(
        channels_dir,
        policy=CollectionPolicy(crawl_interval_minutes=180),
    )[0].sources[0]

    assert source.crawl_interval_minutes == 180


def test_channel_can_load_external_source_catalog_with_global_policy(tmp_path):
    channels_dir = tmp_path / "channels"
    _write_channel_config(channels_dir)
    channel_path = channels_dir / "ai.yaml"
    channel_path.write_text(
        channel_path.read_text(encoding="utf-8").replace(
            "sources:",
            "source_catalogs:\n  - catalogs/ai_expansion.yaml\nsources:",
            1,
        ),
        encoding="utf-8",
    )
    catalog_dir = channels_dir / "catalogs"
    catalog_dir.mkdir()
    (catalog_dir / "ai_expansion.yaml").write_text(
        """
sources:
  - id: second
    source_type: rss
    name: Second
    url: https://second.example.com/feed.xml
    language: en
    region: global
    trust_level: authority
    base_weight: 85
    default_categories: [models]
    parser_type: rss
    enabled: true
    publisher_key: publisher:second
    collection_status: collectable
""",
        encoding="utf-8",
    )

    config = load_channel_configs(
        channels_dir,
        policy=CollectionPolicy(crawl_interval_minutes=360),
    )[0]

    assert len(config.sources) == 2
    assert {source.crawl_interval_minutes for source in config.sources} == {360}
    assert config.sources[1].metadata["publisher_key"] == "publisher:second"


def test_source_cannot_override_collection_policy(tmp_path):
    channels_dir = tmp_path / "channels"
    _write_channel_config(channels_dir, crawl_interval_minutes=60)

    with pytest.raises(ValueError, match="config/collection.yaml"):
        load_channel_configs(
            channels_dir,
            policy=CollectionPolicy(crawl_interval_minutes=720),
        )


@pytest.mark.parametrize("value", [0, -1, 1.5, True, "720", None])
def test_collection_policy_rejects_invalid_interval(tmp_path, value):
    policy_path = tmp_path / "collection.yaml"
    policy_path.write_text(
        f"crawl_interval_minutes: {value!r}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must be a positive integer"):
        load_collection_policy(policy_path)


@pytest.mark.parametrize("value", [0, -1, 1.5, True, "invalid", 720])
def test_source_interval_is_always_rejected(tmp_path, value):
    channels_dir = tmp_path / "channels"
    _write_channel_config(channels_dir, crawl_interval_minutes=value)

    with pytest.raises(ValueError, match="config/collection.yaml"):
        load_channel_configs(
            channels_dir,
            policy=CollectionPolicy(crawl_interval_minutes=720),
        )


def test_amazon_channel_contains_seller_specific_metadata():
    amazon = {config.id: config for config in load_channel_configs()}["amazon"]

    assert any(source.metadata.get("seller_area") == "ads" for source in amazon.sources)
    assert any(category.id == "account_health" for category in amazon.categories)


def test_bundled_channels_include_free_social_candidates_without_enabling_unstable_crawling():
    configs = {config.id: config for config in load_channel_configs()}

    ai_social = [
        source for source in configs["ai"].sources if source.source_type == "social"
    ]
    amazon_social = [
        source for source in configs["amazon"].sources if source.source_type == "social"
    ]

    assert len(ai_social) >= 5
    assert len(amazon_social) >= 3
    assert all(source.enabled is False for source in [*ai_social, *amazon_social])
    assert all(
        source.metadata.get("free_access") is True
        for source in [*ai_social, *amazon_social]
    )
    assert all(
        source.metadata.get("collection_status") == "pending_api"
        for source in [*ai_social, *amazon_social]
    )


def test_channels_have_300_collectable_sources_and_amazon_social_opinion_radar():
    configs = {config.id: config for config in load_channel_configs()}
    amazon = configs["amazon"]

    collectable_by_channel = {
        channel_id: [
            source
            for source in config.sources
            if source.enabled
            and source.metadata.get("collection_status", "collectable") == "collectable"
        ]
        for channel_id, config in configs.items()
    }
    collectable = collectable_by_channel["amazon"]
    opinion_sources = [
        source
        for source in amazon.sources
        if source.metadata.get("source_group") == "social_opinion"
    ]

    assert len(collectable_by_channel["ai"]) >= 300
    assert len(collectable_by_channel["amazon"]) >= 300
    assert len(opinion_sources) >= 20
    assert all(source.enabled is False for source in opinion_sources)
    assert all(
        source.metadata.get("collection_status") in {"pending_api", "watch"}
        for source in opinion_sources
    )
    assert len({source.id for source in amazon.sources}) == len(amazon.sources)
    assert len({source.url.rstrip("/") for source in collectable}) == len(collectable)
