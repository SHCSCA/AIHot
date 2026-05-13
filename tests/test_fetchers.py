from __future__ import annotations

from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from intel_engine.db import create_engine_from_settings, init_schema, sessionmaker_for_engine
from intel_engine.fetchers import HttpArticleAdapter, RssFetchAdapter
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
          <description>Model update summary.</description>
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


def test_http_article_adapter_extracts_article_text():
    html = """
    <html>
      <head><title>Launch Notes</title><meta name="description" content="Short summary"></head>
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


def _source_record(source_id: str, adapter: str):
    from intel_engine.models import SourceRecord

    return SourceRecord(
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
