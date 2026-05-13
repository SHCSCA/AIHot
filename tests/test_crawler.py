import httpx

from intel_engine.channel_config import SourceConfig
from intel_engine.crawler import crawl_source, parse_rss_document, parse_website_document


def make_source(parser_type: str = "rss") -> SourceConfig:
    return SourceConfig(
        id="test_source",
        source_type="rss",
        name="Test Source",
        url="https://example.com/feed.xml",
        language="en",
        region="global",
        trust_level="official",
        base_weight=90,
        default_categories=("ai_models",),
        crawl_interval_minutes=60,
        parser_type=parser_type,
        enabled=True,
        metadata={},
    )


def test_parse_rss_document_returns_raw_items():
    rss = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
      <channel>
        <title>Test Feed</title>
        <item>
          <title>OpenAI ships a new model</title>
          <link>https://example.com/model</link>
          <description>Short model update.</description>
          <pubDate>Mon, 11 May 2026 08:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """

    items = parse_rss_document(make_source(), rss, channel="ai")

    assert len(items) == 1
    assert items[0].title == "OpenAI ships a new model"
    assert items[0].url == "https://example.com/model"
    assert items[0].default_category == "ai_models"
    assert items[0].source_score == 90


def test_crawl_source_fetches_and_parses_rss_with_injected_client():
    rss = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
      <channel>
        <title>Test Feed</title>
        <item>
          <title>Amazon policy update</title>
          <link>https://example.com/policy</link>
          <description>Seller policy update.</description>
        </item>
      </channel>
    </rss>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://example.com/feed.xml"
        return httpx.Response(200, text=rss)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    items = crawl_source(make_source(), channel="amazon", client=client)

    assert len(items) == 1
    assert items[0].channel == "amazon"
    assert items[0].title == "Amazon policy update"


def test_parse_website_document_uses_title_and_meta_description():
    html = """
    <html>
      <head>
        <title>Amazon fee update</title>
        <meta name="description" content="A public seller fee update." />
      </head>
      <body><h1>Amazon fee update</h1></body>
    </html>
    """

    item = parse_website_document(make_source(parser_type="website"), html, channel="amazon")

    assert item.title == "Amazon fee update"
    assert item.excerpt == "A public seller fee update."
    assert item.url == "https://example.com/feed.xml"
