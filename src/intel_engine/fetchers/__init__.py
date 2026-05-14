from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Protocol
from urllib.parse import urljoin

import feedparser
import httpx

from intel_engine.models import SourceRecord, utc_now
from intel_engine.normalizer import canonicalize_url, collapse_whitespace
from intel_engine.quality import is_publishable_original_url, is_within_recent_hours


TAG_RE = re.compile(r"<[^>]+>")
MAX_ACCEPTED_DOCUMENTS_PER_RSS_RUN = 5
MAX_ACCEPTED_DOCUMENTS_PER_HTML_LIST_RUN = 10


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
            image = _rss_entry_image(entry, summary_html, url)
            if image[0]:
                document_headers["x-intel-image-url"] = image[0]
                document_headers["x-intel-image-alt"] = image[1] or title
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

        body_html = response.text
        body_text = extract_article_text(body_html)
        title = extract_title(body_html) or source.name
        canonical_url = canonicalize_url(str(response.url))
        headers = {**dict(response.headers), "x-intel-title": title}
        image_url = extract_meta_image(body_html, str(response.url))
        if image_url:
            headers["x-intel-image-url"] = image_url
            headers["x-intel-image-alt"] = title
        document = FetchedDocument(
            source_id=source.id,
            url=str(response.url),
            canonical_url=canonical_url,
            content_type=content_type,
            body_text=body_text,
            body_html=body_html,
            response_headers_json=headers,
            content_hash=_document_hash(source.channel, source.id, canonical_url, title, body_text),
            fetched_at=self.now or utc_now(),
        )
        return FetchResult(
            status="succeeded",
            http_status=response.status_code,
            content_type=content_type,
            bytes_received=len(response.content),
            documents=(document,),
        )


class HtmlListAdapter:
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

        fetched_at = self.now or utc_now()
        documents: list[FetchedDocument] = []
        candidate_items = 0
        skipped_old_items = 0
        skipped_missing_date = 0
        skipped_invalid_original_url = 0
        skipped_over_limit = 0
        for block in _html_list_blocks(response.text):
            title_url = _html_block_anchor(block, str(response.url))
            if title_url is None:
                continue
            title, url = title_url
            candidate_items += 1
            published_at = _html_block_datetime(block)
            if published_at is None:
                skipped_missing_date += 1
                continue
            if not is_within_recent_hours(published_at, fetched_at):
                skipped_old_items += 1
                continue
            if not is_publishable_original_url(url, source.url):
                skipped_invalid_original_url += 1
                continue
            if len(documents) >= MAX_ACCEPTED_DOCUMENTS_PER_HTML_LIST_RUN:
                skipped_over_limit += 1
                continue
            summary = _html_block_summary(block)
            image_url, image_alt = _html_block_image(block, str(response.url))
            canonical_url = canonicalize_url(url)
            document_headers = {
                **dict(response.headers),
                "x-intel-title": title,
                "x-intel-published-at": published_at.isoformat(),
            }
            if image_url:
                document_headers["x-intel-image-url"] = image_url
                document_headers["x-intel-image-alt"] = image_alt or title
            documents.append(
                FetchedDocument(
                    source_id=source.id,
                    url=url,
                    canonical_url=canonical_url,
                    content_type=content_type,
                    body_text=summary,
                    body_html=block,
                    response_headers_json=document_headers,
                    content_hash=_document_hash(source.channel, source.id, canonical_url, title, summary),
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
                "candidate_items": candidate_items,
                "accepted_items": len(documents),
                "skipped_old_items": skipped_old_items,
                "skipped_missing_date": skipped_missing_date,
                "skipped_invalid_original_url": skipped_invalid_original_url,
                "skipped_over_limit": skipped_over_limit,
            },
        )


class AihotApiAdapter:
    CATEGORY_MAP = {
        "ai-models": "ai_models",
        "ai-products": "ai_products",
        "paper": "papers",
        "tip": "agent_tools",
        "industry": "industry",
    }

    def __init__(self, *, now: datetime | None = None):
        self.now = now

    def fetch(self, source: SourceRecord, *, client: httpx.Client | None = None) -> FetchResult:
        fetched_at = self.now or utc_now()
        since = (fetched_at - timedelta(hours=24)).isoformat().replace("+00:00", "Z")
        params = {"mode": "selected", "since": since, "take": "100"}
        headers = {
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 aihot-intel-engine/0.1"
            )
        }
        response = _get(client, source.url, headers=headers, params=params)
        content_type = response.headers.get("content-type")
        if response.status_code >= 400:
            return FetchResult(
                status="failed",
                http_status=response.status_code,
                content_type=content_type,
                bytes_received=len(response.content),
                error_message=f"HTTP {response.status_code}",
            )
        data = response.json()
        documents: list[FetchedDocument] = []
        skipped_missing_date = 0
        skipped_old_items = 0
        skipped_invalid_original_url = 0
        candidate_items = 0
        for item in data.get("items", []):
            if not isinstance(item, dict):
                continue
            candidate_items += 1
            title = collapse_whitespace(str(item.get("title") or ""))
            url = collapse_whitespace(str(item.get("url") or ""))
            summary = collapse_whitespace(str(item.get("summary") or ""))
            published_at = _iso_datetime(str(item.get("publishedAt") or ""))
            if published_at is None:
                skipped_missing_date += 1
                continue
            if not is_within_recent_hours(published_at, fetched_at):
                skipped_old_items += 1
                continue
            if not is_publishable_original_url(url, source.url):
                skipped_invalid_original_url += 1
                continue
            canonical_url = canonicalize_url(url)
            category = self.CATEGORY_MAP.get(str(item.get("category") or ""), str(item.get("category") or "agent_tools"))
            document_headers = {
                **dict(response.headers),
                "x-intel-title": title,
                "x-intel-published-at": published_at.isoformat(),
                "x-intel-category": category,
                "x-intel-source": str(item.get("source") or source.name),
            }
            body_text = collapse_whitespace(f"{summary} 来源：{item.get('source') or source.name}")
            documents.append(
                FetchedDocument(
                    source_id=source.id,
                    url=url,
                    canonical_url=canonical_url,
                    content_type=content_type,
                    body_text=body_text,
                    body_html=None,
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
                "candidate_items": candidate_items,
                "accepted_items": len(documents),
                "skipped_old_items": skipped_old_items,
                "skipped_missing_date": skipped_missing_date,
                "skipped_invalid_original_url": skipped_invalid_original_url,
            },
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


def get_fetch_adapter(adapter_name: str, *, now: datetime | None = None) -> FetchAdapter:
    if adapter_name == "rss":
        return RssFetchAdapter(now=now)
    if adapter_name == "http_article":
        return HttpArticleAdapter(now=now)
    if adapter_name == "html_list":
        return HtmlListAdapter(now=now)
    if adapter_name == "aihot_api":
        return AihotApiAdapter(now=now)
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


def extract_meta_image(document: str, base_url: str) -> str | None:
    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, document, flags=re.IGNORECASE)
        if match:
            return _safe_image_url(match.group(1), base_url)
    return None


def _get(client: httpx.Client | None, url: str, **kwargs) -> httpx.Response:
    if client is not None:
        return client.get(url, **kwargs)
    with httpx.Client(timeout=20) as local_client:
        return local_client.get(url, **kwargs)


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


def _rss_entry_image(entry, summary_html: str, base_url: str) -> tuple[str | None, str | None]:
    for attr in ("media_thumbnail", "media_content", "links"):
        values = getattr(entry, attr, None)
        if isinstance(values, list):
            for value in values:
                if not isinstance(value, dict):
                    continue
                href = value.get("url") or value.get("href")
                media_type = str(value.get("type") or "")
                rel = str(value.get("rel") or "")
                if href and (media_type.startswith("image/") or attr != "links" or rel == "enclosure"):
                    return _safe_image_url(str(href), base_url), str(value.get("alt") or "")
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', summary_html, flags=re.IGNORECASE)
    if not match:
        return None, None
    image_url = _safe_image_url(match.group(1), base_url)
    alt_match = re.search(r'alt=["\']([^"\']*)["\']', match.group(0), flags=re.IGNORECASE)
    return image_url, html.unescape(alt_match.group(1)) if alt_match else None


def _html_list_blocks(document: str) -> list[str]:
    blocks = re.findall(r"<article\b[^>]*>.*?</article>", document, flags=re.IGNORECASE | re.DOTALL)
    if blocks:
        return blocks
    blocks = [
        block
        for block in re.findall(r"<li\b[^>]*>.*?</li>", document, flags=re.IGNORECASE | re.DOTALL)
        if "href=" in block.lower()
    ]
    if blocks:
        return blocks
    return [
        match.group(0)
        for match in re.finditer(r"<a\b[^>]+href=[\"'][^\"']+[\"'][^>]*>.*?</a>.{0,800}", document, flags=re.IGNORECASE | re.DOTALL)
    ]


def _html_block_anchor(block: str, base_url: str) -> tuple[str, str] | None:
    match = re.search(r"<a\b[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", block, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    href = html.unescape(match.group(1)).strip()
    if href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    title = collapse_whitespace(html.unescape(TAG_RE.sub(" ", match.group(2))))
    if not title:
        title_attr = re.search(r"title=[\"']([^\"']+)[\"']", match.group(0), flags=re.IGNORECASE)
        title = collapse_whitespace(html.unescape(title_attr.group(1))) if title_attr else ""
    if not title:
        return None
    return title, urljoin(base_url, href)


def _html_block_datetime(block: str) -> datetime | None:
    patterns = [
        r"<time\b[^>]+datetime=[\"']([^\"']+)[\"']",
        r"datetime=[\"']([^\"']+)[\"']",
        r"datePublished[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']",
    ]
    for pattern in patterns:
        match = re.search(pattern, block, flags=re.IGNORECASE)
        if match:
            parsed = _iso_datetime(match.group(1)) or _rfc_datetime(match.group(1))
            if parsed is not None:
                return parsed
    text = collapse_whitespace(html.unescape(TAG_RE.sub(" ", block)))
    for match in re.finditer(r"\b[A-Z][a-z]{2,8}\s+\d{1,2},\s+\d{4}\b", text):
        parsed = _rfc_datetime(match.group(0))
        if parsed is not None:
            return parsed
    return None


def _html_block_summary(block: str) -> str:
    match = re.search(r"<p\b[^>]*>(.*?)</p>", block, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return collapse_whitespace(html.unescape(TAG_RE.sub(" ", match.group(1))))
    return collapse_whitespace(html.unescape(TAG_RE.sub(" ", block)))


def _html_block_image(block: str, base_url: str) -> tuple[str | None, str | None]:
    match = re.search(r"<img\b[^>]+src=[\"']([^\"']+)[\"'][^>]*>", block, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None, None
    image_url = _safe_image_url(match.group(1), base_url)
    alt_match = re.search(r'alt=["\']([^"\']*)["\']', match.group(0), flags=re.IGNORECASE)
    return image_url, html.unescape(alt_match.group(1)) if alt_match else None


def _safe_image_url(value: str, base_url: str) -> str | None:
    image_url = urljoin(base_url, html.unescape(value).strip())
    if not image_url.startswith(("http://", "https://")):
        return None
    return image_url


def _iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _rfc_datetime(value: str) -> datetime | None:
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
