from intel_engine.channel_config import load_channel_configs


def test_loads_ai_and_amazon_channels():
    configs = {config.id: config for config in load_channel_configs()}

    assert set(configs) == {"ai", "amazon"}
    assert configs["ai"].categories
    assert configs["amazon"].categories
    assert configs["ai"].sources
    assert configs["amazon"].sources


def test_amazon_channel_contains_seller_specific_metadata():
    amazon = {config.id: config for config in load_channel_configs()}["amazon"]

    assert any(source.metadata.get("seller_area") == "ads" for source in amazon.sources)
    assert any(category.id == "account_health" for category in amazon.categories)


def test_bundled_channels_include_free_social_candidates_without_enabling_unstable_crawling():
    configs = {config.id: config for config in load_channel_configs()}

    ai_social = [source for source in configs["ai"].sources if source.source_type == "social"]
    amazon_social = [source for source in configs["amazon"].sources if source.source_type == "social"]

    assert len(ai_social) >= 5
    assert len(amazon_social) >= 3
    assert all(source.enabled is False for source in [*ai_social, *amazon_social])
    assert all(source.metadata.get("free_access") is True for source in [*ai_social, *amazon_social])
    assert all(source.metadata.get("collection_status") == "pending_api" for source in [*ai_social, *amazon_social])


def test_amazon_channel_has_100_collectable_sources_and_social_opinion_radar():
    amazon = {config.id: config for config in load_channel_configs()}["amazon"]

    collectable = [
        source
        for source in amazon.sources
        if source.enabled and source.metadata.get("collection_status", "collectable") == "collectable"
    ]
    opinion_sources = [
        source
        for source in amazon.sources
        if source.metadata.get("source_group") == "social_opinion"
    ]

    assert len(collectable) >= 100
    assert len(opinion_sources) >= 20
    assert all(source.enabled is False for source in opinion_sources)
    assert all(source.metadata.get("collection_status") in {"pending_api", "watch"} for source in opinion_sources)
    assert len({source.id for source in amazon.sources}) == len(amazon.sources)
    assert len({source.url.rstrip("/") for source in collectable}) == len(collectable)
