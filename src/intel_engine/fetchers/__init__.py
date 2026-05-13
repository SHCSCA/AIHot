from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

import feedparser
import httpx

from intel_engine.models import SourceRecord, utc_now
from intel_engine.normalizer import canonicalize_url, collapse_whitespace
from intel_engine.quality import is_publishable_original_url, is_within_recent_hours


TAG_RE = re.compile(r"<[^>]+>")
MAX_ACCEPTED_DOCUMENTS_PER_RSS_RUN = 5


@dataclass(frozen=True)
class FetchedDocument:
    source_id: str
    url: str
    canonical_url: str
    content_type: str | None
    body_text: str
    body_html: str | None
    response_headers_json: dict[str, str]
    content_hash: str
    fetched_at: datetime


@dataclass(frozen=True)
class FetchResult:
    status: str
    http_status: int | None
    content_type: str | None
    bytes_received: int
    documents: tuple[FetchedDocument, ...] = field(default_factory=tuple)
    error_message: str | None = None
    metadata_json: dict[str, object] = field(default_factory=dict)


class FetchAdapter(Protocol):
    def fetch(self, source: SourceRecord, *, client: httpx.Client | None = None) -> FetchResult:
        ...


class RssFetchAdapter:
    def __init__(self, *, now: datetime | None = None):
        self.now = now

    def fetch(self, source: SourceRecord, *, client: httpx.Client | None = None) -> FetchResult:
        response = _get(client, source.url)
        content_type = response.headers.get("content-type")
        if response.status_code >= 400:
            return FetchResult(
                status="failed",
                http_status=response.status_code,
                content_type=content_type,
                bytes_received=len(response.content),
                error_message=f"HTTP {response.status_code}",
            )

        parsed = feedparser.parse(response.text)
        fetched_at = self.now or utc_now()
        documents: list[FetchedDocument] = []
        headers = dict(response.headers)
        candidate_items = 0
        skipped_old_items = 0
        skipped_missing_date = 0
        skipped_invalid_original_url = 0
        skipped_over_limit = 0
        for entry in parsed.entries:
            candidate_items += 1
            title = collapse_whitespace(getattr(entry, "title", ""))
            url = collapse_whitespace(getattr(entry, "link", ""))
            if not title or not url:
                continue
            published_at = _entry_time_to_datetime(entry)
            if published_at is None:
                skipped_missing_date += 1
                continue
            if not is_within_recent_hours(published_at, fetched_at):
                skipped_old_items += 1
                continue
            if not is_publishable_original_url(url, source.url):
                skipped_invalid_original_url += 1
                continue
            if len(documents) >= MAX_ACCEPTED_DOCUMENTS_PER_RSS_RUN:
                skipped_over_limit += 1
                continue
            summary_html = getattr(entry, "summary", "") or getattr(entry, "description", "")
            body_text = collapse_whitespace(html.unescape(TAG_RE.sub(" ", summary_html)))
            canonical_url = canonicalize_url(url)
            document_headers = {**headers, "x-intel-title": title}
            document_headers["x-intel-published-at"] = published_at.isoformat()
            documents.append(
                FetchedDocument(
                    source_id=source.id,
                    url=url,
                    canonical_url=canonical_url,
                    content_type=content_type,
                    body_text=body_text,
                    body_html=summary_html,
                    response_headers_json=document_headers,
                    content_hash=_document_hash(source.channel, source.id, canonical_url, title, body_text),
                    fetched_at=fetched_at,
                )
            )

        return FetchResult(
            status="succeeded",
            http_status=response.status_code,
            content_type=content_type,
            bytes_received=len(response.content),
            documents=tuple(documents),
            metadata_json={
                "feed_bozo": bool(getattr(parsed, "bozo", False)),
                "candidate_items": candidate_items,
                "accepted_items": len(documents),
                "skipped_old_items": skipped_old_items,
                "skipped_missing_date": skipped_missing_date,
                "skipped_invalid_original_url": skipped_invalid_original_url,
                "skipped_over_limit": skipped_over_limit,
            },
        )


class HttpArticleAdapter:
    def fetch(self, source: SourceRecord, *, client: httpx.Client | None = None) -> FetchResult:
        response = _get(client, source.url)
        content_type = response.headers.get("content-type")
        if response.status_code >= 400:
            return FetchResult(
                status="failed",
                http_status=response.status_code,
                content_type=content_type,
                bytes_received=len(response.content),
                error_message=f"HTTP {response.status_code}",
            )

        body_html = response.text
        body_text = extract_article_text(body_html)
        title = extract_title(body_html) or source.name
        canonical_url = canonicalize_url(str(response.url))
        headers = {**dict(response.headers), "x-intel-title": title}
        document = FetchedDocument(
            source_id=source.id,
            url=str(response.url),
            canonical_url=canonical_url,
            content_type=content_type,
            body_text=body_text,
            body_html=body_html,
            response_headers_json=headers,
            content_hash=_document_hash(source.channel, source.id, canonical_url, title, body_text),
            fetched_at=utc_now(),
        )
        return FetchResult(
            status="succeeded",
            http_status=response.status_code,
            content_type=content_type,
            bytes_received=len(response.content),
            documents=(document,),
        )


class PendingApiAdapter:
    def fetch(self, source: SourceRecord, *, client: httpx.Client | None = None) -> FetchResult:
        return FetchResult(
            status="failed",
            http_status=None,
            content_type=None,
            bytes_received=0,
            error_message=f"{source.source_type} 信源需要专用 API 适配器，当前处于待接入状态。",
            metadata_json={"collection_status": getattr(source, "collection_status", "pending_api")},
        )


def get_fetch_adapter(adapter_name: str) -> FetchAdapter:
    if adapter_name == "rss":
        return RssFetchAdapter()
    if adapter_name == "http_article":
        return HttpArticleAdapter()
    if adapter_name == "api":
        return PendingApiAdapter()
    raise KeyError(f"Unsupported fetch adapter: {adapter_name}")


def extract_article_text(document: str) -> str:
    try:
        import trafilatura
    except ImportError:
        trafilatura = None

    if trafilatura is not None:
        extracted = trafilatura.extract(document)
        if extracted:
            return collapse_whitespace(extracted)
    return collapse_whitespace(html.unescape(TAG_RE.sub(" ", document)))


def extract_title(document: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", document, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return collapse_whitespace(html.unescape(TAG_RE.sub(" ", match.group(1))))


def _get(client: httpx.Client | None, url: str) -> httpx.Response:
    if client is not None:
        return client.get(url)
    with httpx.Client(timeout=20) as local_client:
        return local_client.get(url)


def _document_hash(channel: str, source_id: str, canonical_url: str, title: str, body_text: str) -> str:
    payload = "\n".join([channel, source_id, canonical_url, collapse_whitespace(title), collapse_whitespace(body_text)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parsed_time_to_datetime(parsed_time) -> datetime | None:
    if parsed_time is None:
        return None
    return datetime(*parsed_time[:6], tzinfo=timezone.utc)


def _entry_time_to_datetime(entry) -> datetime | None:
    return _parsed_time_to_datetime(getattr(entry, "published_parsed", None)) or _parsed_time_to_datetime(
        getattr(entry, "updated_parsed", None)
    )
