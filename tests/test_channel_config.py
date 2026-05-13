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

