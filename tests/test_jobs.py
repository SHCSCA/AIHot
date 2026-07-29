import httpx

from intel_engine.jobs import crawl_enabled_sources
from intel_engine.storage import ItemRepository, create_engine_for_path, init_db


def write_channel_config(channels_dir, channel_id="ai"):
    channels_dir.mkdir()
    (channels_dir / f"{channel_id}.yaml").write_text(
        f"""
id: {channel_id}
name: 测试频道
description: 测试公开信源
categories:
  - id: news
    label: 动态
scoring:
  selected_threshold: 70
  weights:
    source_score: 0.20
    relevance_score: 0.20
    impact_score: 0.25
    novelty_score: 0.15
    actionability_score: 0.15
    freshness_score: 0.05
sources:
  - id: test_feed
    source_type: rss
    name: 测试 RSS
    url: https://example.com/feed.xml
    language: zh
    region: global
    trust_level: official
    base_weight: 90
    default_categories: [news]
    parser_type: rss
    enabled: true
  - id: disabled_feed
    source_type: rss
    name: 禁用 RSS
    url: https://example.com/disabled.xml
    language: zh
    region: global
    trust_level: official
    base_weight: 90
    default_categories: [news]
    parser_type: rss
    enabled: false
""",
        encoding="utf-8",
    )


def test_crawl_enabled_sources_fetches_enabled_sources_and_deduplicates(tmp_path):
    channels_dir = tmp_path / "channels"
    write_channel_config(channels_dir)
    engine = create_engine_for_path(tmp_path / "intel.sqlite3")
    init_db(engine)
    repo = ItemRepository(engine)

    rss = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
      <channel>
        <title>测试 Feed</title>
        <item>
          <title>OpenAI 发布模型更新</title>
          <link>https://example.com/model</link>
          <description>模型能力更新。</description>
        </item>
      </channel>
    </rss>
    """

    requested_urls = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, text=rss)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    first = crawl_enabled_sources(repo, channels_dir=channels_dir, client=client)
    second = crawl_enabled_sources(repo, channels_dir=channels_dir, client=client)
    items = repo.list_items(channel="ai")

    assert requested_urls == [
        "https://example.com/feed.xml",
        "https://example.com/feed.xml",
    ]
    assert first.fetched == 1
    assert first.inserted == 1
    assert first.duplicates == 0
    assert second.fetched == 1
    assert second.inserted == 0
    assert second.duplicates == 1
    assert first.errors == ()
    assert len(items) == 1


def test_crawl_enabled_sources_filters_channel(tmp_path):
    channels_dir = tmp_path / "channels"
    write_channel_config(channels_dir, "ai")
    (channels_dir / "amazon.yaml").write_text(
        (channels_dir / "ai.yaml")
        .read_text(encoding="utf-8")
        .replace("id: ai", "id: amazon", 1),
        encoding="utf-8",
    )
    engine = create_engine_for_path(tmp_path / "intel.sqlite3")
    init_db(engine)
    repo = ItemRepository(engine)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="""<rss version="2.0"><channel><item><title>Amazon 动态</title><link>https://example.com/a</link></item></channel></rss>""",
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    stats = crawl_enabled_sources(
        repo, channels_dir=channels_dir, channel_id="amazon", client=client
    )

    assert stats.sources == 1
    assert stats.inserted == 1
    assert repo.list_items(channel="ai") == []
    assert len(repo.list_items(channel="amazon")) == 1
