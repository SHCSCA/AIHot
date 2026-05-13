from __future__ import annotations

import html
import re
from datetime import datetime, timezone

import feedparser
import httpx

from intel_engine.channel_config import SourceConfig
from intel_engine.normalizer import RawFetchedItem, collapse_whitespace


TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
DESCRIPTION_RE = re.compile(
    r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"'](.*?)[\"'][^>]*>",
    re.IGNORECASE | re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")


def _first_default_category(source: SourceConfig) -> str:
    return source.default_categories[0] if source.default_categories else "uncategorized"


def _parsed_time_to_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime(*value[:6], tzinfo=timezone.utc)  # type: ignore[index]
    except (TypeError, ValueError):
        return None


def parse_rss_document(source: SourceConfig, document: str, channel: str) -> list[RawFetchedItem]:
    parsed = feedparser.parse(document)
    items: list[RawFetchedItem] = []

    for entry in parsed.entries:
        title = collapse_whitespace(getattr(entry, "title", ""))
        url = collapse_whitespace(getattr(entry, "link", ""))
        if not title or not url:
            continue

        excerpt = getattr(entry, "summary", "") or getattr(entry, "description", "")
        published_at = _parsed_time_to_datetime(getattr(entry, "published_parsed", None))

        items.append(
            RawFetchedItem(
                channel=channel,
                source_id=source.id,
                source_name=source.name,
                title=title,
                url=url,
                published_at=published_at,
                excerpt=collapse_whitespace(html.unescape(TAG_RE.sub(" ", excerpt))),
                raw_content=excerpt,
                default_category=_first_default_category(source),
                source_score=source.base_weight,
            )
        )

    return items


def parse_website_document(source: SourceConfig, document: str, channel: str) -> RawFetchedItem:
    title_match = TITLE_RE.search(document)
    description_match = DESCRIPTION_RE.search(document)

    title = html.unescape(title_match.group(1)) if title_match else source.name
    excerpt = html.unescape(description_match.group(1)) if description_match else ""

    return RawFetchedItem(
        channel=channel,
        source_id=source.id,
        source_name=source.name,
        title=collapse_whitespace(TAG_RE.sub(" ", title)),
        url=source.url,
        published_at=None,
        excerpt=collapse_whitespace(TAG_RE.sub(" ", excerpt)),
        raw_content=document,
        default_category=_first_default_category(source),
        source_score=source.base_weight,
    )


def crawl_source(source: SourceConfig, channel: str, client: httpx.Client | None = None) -> list[RawFetchedItem]:
    owns_client = client is None
    active_client = client or httpx.Client(timeout=20)
    try:
        response = active_client.get(source.url)
        response.raise_for_status()
        if source.parser_type in {"rss", "feed"}:
            return parse_rss_document(source, response.text, channel)
        return [parse_website_document(source, response.text, channel)]
    finally:
        if owns_client:
            active_client.close()
