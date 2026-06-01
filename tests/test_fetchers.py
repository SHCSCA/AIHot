from __future__ import annotations

from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from intel_engine.db import create_engine_from_settings, init_schema, sessionmaker_for_engine
from intel_engine.fetchers import AihotApiAdapter, FetchedDocument, FetchResult, HtmlListAdapter, HttpArticleAdapter, RssFetchAdapter
from intel_engine.models import FetchJobRecord, FetchRunRecord, RawDocumentRecord
from intel_engine.raw_store import RawStore
from intel_engine.scheduler import claim_fetch_jobs, schedule_due_sources
from intel_engine.settings import Settings
from intel_engine.sources import SourceRegistry, SourceUpsert


def _session_factory(tmp_path):
    settings = Settings(database_url=f"sqlite+pysqlite:///{tmp_path / 'test.sqlite3'}")
    engine = create_engine_from_settings(settings)
    init_schema(engine)
    return sessionmaker_for_engine(engine)


def _add_source(session, source_id="example_feed", adapter="rss"):
    registry = SourceRegistry(session)
    registry.upsert_source(
        SourceUpsert(
            id=source_id,
            channel="ai",
            source_type="rss" if adapter == "rss" else "html",
            tier="T1",
            name="Example",
            url="https://example.com/feed.xml" if adapter == "rss" else "https://example.com/article",
            language="en",
            region="global",
            marketplace=None,
            authority_weight=90,
            noise_level=0.1,
            fetch_adapter=adapter,
            parser_type="rss" if adapter == "rss" else "website",
            default_categories=["ai_models"],
            fetch_interval_minutes=60,
            enabled=True,
            visibility="public",
            notes=None,
        )
    )
    registry.update_state(source_id, next_fetch_at=datetime(1970, 1, 1, tzinfo=timezone.utc))


def test_rss_adapter_fetches_entries_as_raw_documents():
    now = datetime(2026, 5, 12, 12, 0, tzinfo=timezone.utc)
    rss = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
      <channel>
        <title>Feed</title>
        <item>
          <title>OpenAI ships update</title>
          <link>https://example.com/article?utm_source=x</link>
          <pubDate>Tue, 12 May 2026 08:00:00 GMT</pubDate>
          <description><![CDATA[<p>Model update summary.</p><img src="https://example.com/card.png" alt="Card image" />]]></description>
        </item>
      </channel>
    </rss>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=rss, headers={"content-type": "application/rss+xml"})

    source = _source_record("example_feed", "rss")
    result = RssFetchAdapter(now=now).fetch(source, client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert result.status == "succeeded"
    assert result.http_status == 200
    assert len(result.documents) == 1
    assert result.documents[0].canonical_url == "https://example.com/article"
    assert result.documents[0].body_text == "Model update summary."
    assert result.documents[0].response_headers_json["x-intel-image-url"] == "https://example.com/card.png"
    assert result.documents[0].response_headers_json["x-intel-image-alt"] == "Card image"
    assert result.documents[0].content_hash


def test_rss_adapter_only_accepts_rolling_24_hour_specific_links():
    now = datetime(2026, 5, 12, 12, 0, tzinfo=timezone.utc)
    rss = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
      <channel>
        <title>Feed</title>
        <item>
          <title>Today in Beijing</title>
          <link>https://example.com/news/today</link>
          <pubDate>Mon, 11 May 2026 16:30:00 GMT</pubDate>
          <description>Accepted summary.</description>
        </item>
        <item>
          <title>Yesterday in Beijing</title>
          <link>https://example.com/news/yesterday</link>
          <pubDate>Mon, 11 May 2026 15:00:00 GMT</pubDate>
          <description>Old summary.</description>
        </item>
        <item>
          <title>No Date</title>
          <link>https://example.com/news/no-date</link>
          <description>Missing date summary.</description>
        </item>
        <item>
          <title>Category Page</title>
          <link>https://example.com/news</link>
          <pubDate>Tue, 12 May 2026 08:00:00 GMT</pubDate>
          <description>Category summary.</description>
        </item>
      </channel>
    </rss>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=rss, headers={"content-type": "application/rss+xml"})

    source = _source_record("example_feed", "rss")
    result = RssFetchAdapter(now=now).fetch(source, client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert [document.url for document in result.documents] == [
        "https://example.com/news/today",
        "https://example.com/news/yesterday",
    ]
    assert result.metadata_json["candidate_items"] == 4
    assert result.metadata_json["accepted_items"] == 2
    assert result.metadata_json["skipped_old_items"] == 0
    assert result.metadata_json["skipped_missing_date"] == 1
    assert result.metadata_json["skipped_invalid_original_url"] == 1


def test_rss_adapter_uses_week_window_for_amazon_sources():
    now = datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc)
    rss = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
      <channel>
        <title>Feed</title>
        <item>
          <title>Amazon FBA reimbursement update</title>
          <link>https://example.com/news/amazon-fba-reimbursement</link>
          <pubDate>Thu, 14 May 2026 12:00:00 GMT</pubDate>
          <description>Amazon sellers can review FBA reimbursement changes.</description>
        </item>
      </channel>
    </rss>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=rss, headers={"content-type": "application/rss+xml"})

    amazon_source = _source_record("amazon_feed", "rss")
    amazon_source.channel = "amazon"
    amazon_source.default_categories = ["fba_logistics"]
    amazon_result = RssFetchAdapter(now=now).fetch(
        amazon_source,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    ai_source = _source_record("ai_feed", "rss")
    ai_result = RssFetchAdapter(now=now).fetch(
        ai_source,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert [document.url for document in amazon_result.documents] == [
        "https://example.com/news/amazon-fba-reimbursement"
    ]
    assert amazon_result.metadata_json["skipped_old_items"] == 0
    assert ai_result.documents == ()
    assert ai_result.metadata_json["skipped_old_items"] == 1


def test_rss_adapter_caps_accepted_documents_per_source_run():
    now = datetime(2026, 5, 12, 12, 0, tzinfo=timezone.utc)
    items = "\n".join(
        f"""
        <item>
          <title>AI item {index}</title>
          <link>https://example.com/news/item-{index}</link>
          <pubDate>Tue, 12 May 2026 08:0{index}:00 GMT</pubDate>
          <description>Summary {index}.</description>
        </item>
        """
        for index in range(7)
    )
    rss = f"""<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0"><channel><title>Feed</title>{items}</channel></rss>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=rss, headers={"content-type": "application/rss+xml"})

    source = _source_record("example_feed", "rss")
    result = RssFetchAdapter(now=now).fetch(source, client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert len(result.documents) == 5
    assert result.metadata_json["candidate_items"] == 7
    assert result.metadata_json["accepted_items"] == 5
    assert result.metadata_json["skipped_over_limit"] == 2


def test_http_article_adapter_extracts_article_text():
    html = """
    <html>
      <head><title>Launch Notes</title><meta property="og:image" content="https://example.com/launch.png"></head>
      <body><article><h1>Launch Notes</h1><p>Important model release details.</p></article></body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    source = _source_record("example_article", "http_article")
    result = HttpArticleAdapter().fetch(source, client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert result.status == "succeeded"
    assert len(result.documents) == 1
    assert "Important model release details" in result.documents[0].body_text
    assert result.documents[0].body_html == html
    assert result.documents[0].response_headers_json["x-intel-image-url"] == "https://example.com/launch.png"


def test_aihot_api_adapter_uses_user_agent_and_maps_items():
    now = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)

    def handler(request: httpx.Request) -> httpx.Response:
        assert "aihot-intel-engine/0.1" in request.headers["user-agent"]
        assert request.url.params["mode"] == "selected"
        assert request.url.params["take"] == "100"
        assert "since" in request.url.params
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "item-1",
                        "title": "AIHOT 中文标题",
                        "summary": "AIHOT 中文摘要",
                        "url": "https://x.com/example/status/1",
                        "source": "X：Example",
                        "publishedAt": "2026-05-14T01:00:00Z",
                        "category": "ai-models",
                    }
                ]
            },
        )

    source = _source_record("aihot_virxact_selected", "aihot_api")
    source.url = "https://aihot.virxact.com/api/public/items"
    result = AihotApiAdapter(now=now).fetch(source, client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert result.status == "succeeded"
    assert len(result.documents) == 1
    assert result.documents[0].canonical_url == "https://x.com/example/status/1"
    assert result.documents[0].response_headers_json["x-intel-category"] == "ai_models"
    assert result.documents[0].response_headers_json["x-intel-source"] == "X：Example"
    assert "AIHOT 中文摘要" in result.documents[0].body_text


def test_html_list_adapter_extracts_recent_article_cards_with_images():
    now = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)
    html = """
    <html>
      <body>
        <article>
          <a href="/updates/ads-budget-rules">Amazon Ads adds new budget rules</a>
          <time datetime="2026-05-14T02:30:00Z">May 14, 2026</time>
          <p>Amazon Ads introduced a seller-facing budget control change.</p>
          <img src="/images/ads-budget.png" alt="Budget rule" />
        </article>
        <article>
          <a href="/updates/old-change">Old Amazon change</a>
          <time datetime="2026-05-12T02:30:00Z">May 12, 2026</time>
          <p>Old summary.</p>
        </article>
      </body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    source = _source_record("amazon_ads_updates", "html_list")
    source.channel = "amazon"
    source.url = "https://advertising.amazon.com/resources/whats-new"
    result = HtmlListAdapter(now=now).fetch(source, client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert result.status == "succeeded"
    assert [document.url for document in result.documents] == [
        "https://advertising.amazon.com/updates/ads-budget-rules",
        "https://advertising.amazon.com/updates/old-change",
    ]
    assert result.documents[0].response_headers_json["x-intel-title"] == "Amazon Ads adds new budget rules"
    assert result.documents[0].response_headers_json["x-intel-published-at"] == "2026-05-14T02:30:00+00:00"
    assert result.documents[0].response_headers_json["x-intel-image-url"] == (
        "https://advertising.amazon.com/images/ads-budget.png"
    )
    assert result.metadata_json["candidate_items"] == 2
    assert result.metadata_json["accepted_items"] == 2
    assert result.metadata_json["skipped_old_items"] == 0


def test_html_list_adapter_reads_dates_before_card_links():
    now = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)
    html = """
    <html>
      <body>
        <div class="post-card">
          <span class="date">May 14th, 2026</span>
          <a href="/blog/new-amazon-fba-fee-workflow">New Amazon FBA fee workflow</a>
          <p>Amazon sellers now have a changed fee workflow to review.</p>
        </div>
      </body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    source = _source_record("amazon_fee_blog", "html_list")
    source.channel = "amazon"
    source.url = "https://example.com/blog/"
    result = HtmlListAdapter(now=now).fetch(source, client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert result.status == "succeeded"
    assert [document.url for document in result.documents] == [
        "https://example.com/blog/new-amazon-fba-fee-workflow"
    ]
    assert result.documents[0].response_headers_json["x-intel-published-at"] == "2026-05-14T00:00:00+00:00"
    assert result.metadata_json["candidate_items"] == 1
    assert result.metadata_json["accepted_items"] == 1


def test_html_list_adapter_reads_iso_date_text_in_cards():
    now = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)
    html = """
    <html>
      <body>
        <a href="/resources/amazon-ads-keyword-update">Amazon Ads keyword update</a>
        <span>2026-05-14</span>
        <p>Amazon Ads changed a campaign keyword control for sellers.</p>
      </body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    source = _source_record("amazon_ads_cards", "html_list")
    source.channel = "amazon"
    source.url = "https://example.com/resources/"
    result = HtmlListAdapter(now=now).fetch(source, client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert result.status == "succeeded"
    assert [document.url for document in result.documents] == [
        "https://example.com/resources/amazon-ads-keyword-update"
    ]
    assert result.documents[0].response_headers_json["x-intel-published-at"] == "2026-05-14T00:00:00+00:00"
    assert result.metadata_json["candidate_items"] == 1
    assert result.metadata_json["accepted_items"] == 1


def test_html_list_adapter_extracts_sp_api_release_note_sections():
    now = datetime(2026, 5, 14, 10, 0, tzinfo=timezone.utc)
    escaped_release_notes = (
        "&lt;h2&gt;May 14, 2026&lt;/h2&gt;"
        "&lt;h4&gt;Listings Items API updates product type definitions&lt;/h4&gt;"
        "&lt;p&gt;Amazon updated Selling Partner API behavior for listing feeds and seller tooling.&lt;/p&gt;"
        "&lt;h2&gt;May 10, 2026&lt;/h2&gt;"
        "&lt;h4&gt;Older SP-API change&lt;/h4&gt;"
        "&lt;p&gt;Old change outside the 24 hour window.&lt;/p&gt;"
    )
    page = f"""<article class="rm-Article">
      <div dehydrated="{escaped_release_notes}"></div>
    </article>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=page, headers={"content-type": "text/html; charset=utf-8"})

    source = _source_record("amazon_sp_api_release_notes", "html_list")
    source.channel = "amazon"
    source.url = "https://developer-docs.amazon.com/sp-api/docs/sp-api-release-notes"
    result = HtmlListAdapter(now=now).fetch(source, client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert result.status == "succeeded"
    assert [document.url for document in result.documents] == [
        "https://developer-docs.amazon.com/sp-api/docs/sp-api-release-notes#may-14-2026",
        "https://developer-docs.amazon.com/sp-api/docs/sp-api-release-notes#may-10-2026",
    ]
    assert result.documents[0].response_headers_json["x-intel-title"] == (
        "Listings Items API updates product type definitions"
    )
    assert result.documents[0].response_headers_json["x-intel-published-at"] == "2026-05-14T00:00:00+00:00"
    assert "Selling Partner API behavior" in result.documents[0].body_text
    assert result.metadata_json["candidate_items"] == 2
    assert result.metadata_json["accepted_items"] == 2
    assert result.metadata_json["skipped_old_items"] == 0


def test_raw_store_saves_fetch_run_and_deduplicates_documents(tmp_path):
    now = datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc)
    SessionLocal = _session_factory(tmp_path)
    rss = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
      <channel>
        <title>Feed</title>
        <item>
          <title>OpenAI ships update</title>
          <link>https://example.com/article</link>
          <pubDate>Mon, 11 May 2026 08:00:00 GMT</pubDate>
          <description>Model update summary.</description>
        </item>
      </channel>
    </rss>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=rss, headers={"content-type": "application/rss+xml"})

    with SessionLocal() as session:
        _add_source(session)
        schedule_due_sources(session, now=now)
        job = claim_fetch_jobs(session, worker_id="worker-a", limit=1, now=now)[0]
        source = session.get(FetchJobRecord, job.id)
        assert source is not None
        result = RssFetchAdapter(now=now).fetch(
            _source_record("example_feed", "rss"), client=httpx.Client(transport=httpx.MockTransport(handler))
        )
        store = RawStore(session)
        first = store.save_fetch_result(job, result, now=now)
        second = store.save_fetch_result(job, result, now=now)
        runs = session.scalars(select(FetchRunRecord)).all()
        documents = session.scalars(select(RawDocumentRecord)).all()

    assert first.documents_inserted == 1
    assert first.duplicates == 0
    assert second.documents_inserted == 0
    assert second.duplicates == 1
    assert len(runs) == 2
    assert len(documents) == 1


def test_raw_store_deduplicates_documents_inside_same_fetch_result(tmp_path):
    now = datetime(2026, 5, 14, 10, 0, tzinfo=timezone.utc)
    SessionLocal = _session_factory(tmp_path)
    document = FetchedDocument(
        source_id="example_feed",
        url="https://example.com/article",
        canonical_url="https://example.com/article",
        content_type="application/json",
        body_text="同一批次内重复出现的内容",
        body_html=None,
        response_headers_json={},
        content_hash="duplicate-batch-hash",
        fetched_at=now,
    )
    result = FetchResult(
        status="succeeded",
        http_status=200,
        content_type="application/json",
        bytes_received=1024,
        documents=(document, document),
    )

    with SessionLocal() as session:
        _add_source(session)
        schedule_due_sources(session, now=now)
        job = claim_fetch_jobs(session, worker_id="worker-a", limit=1, now=now)[0]
        saved = RawStore(session).save_fetch_result(job, result, now=now)
        documents = session.scalars(select(RawDocumentRecord)).all()

    assert saved.documents_inserted == 1
    assert saved.duplicates == 1
    assert len(documents) == 1


def _source_record(source_id: str, adapter: str):
    from intel_engine.models import SourceRecord

    return SourceRecord(
        id=source_id,
        channel="ai",
        source_type="rss" if adapter == "rss" else "api" if adapter == "aihot_api" else "html",
        tier="T1",
        name="Example",
        url="https://example.com/feed.xml" if adapter == "rss" else "https://example.com/api" if adapter == "aihot_api" else "https://example.com/article",
        language="en",
        region="global",
        marketplace=None,
        authority_weight=90,
        noise_level=0.1,
        fetch_adapter=adapter,
        parser_type="rss" if adapter == "rss" else "api" if adapter == "aihot_api" else adapter,
        default_categories=["ai_models"],
        fetch_interval_minutes=60,
        enabled=True,
        visibility="public",
        notes=None,
    )
