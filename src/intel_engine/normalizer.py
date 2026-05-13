from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from intel_engine.scoring import ScoreInput, calculate_final_score, seller_action_level


TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


@dataclass(frozen=True)
class RawFetchedItem:
    channel: str
    source_id: str
    source_name: str
    title: str
    url: str
    published_at: datetime | None
    excerpt: str
    raw_content: str
    default_category: str
    source_score: int


@dataclass(frozen=True)
class NormalizedItem:
    channel: str
    source_id: str
    raw_title: str
    normalized_title: str
    url: str
    source_name: str
    published_at: datetime
    content_hash: str
    raw_excerpt: str
    summary: str
    category: str
    keywords: tuple[str, ...]
    source_score: float
    relevance_score: float
    impact_score: float
    novelty_score: float
    actionability_score: float
    freshness_score: float
    final_score: float
    entry_reason: str
    suggested_action: str
    seller_action_level: str | None


def collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query_items = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key in TRACKING_QUERY_KEYS:
            continue
        if any(key.startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES):
            continue
        query_items.append((key, value))

    query = urlencode(query_items, doseq=True)
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/") or parts.path, query, ""))


def build_content_hash(channel: str, source_id: str, title: str, url: str) -> str:
    payload = "\n".join([channel, source_id, collapse_whitespace(title).lower(), canonicalize_url(url)])
    return sha256(payload.encode("utf-8")).hexdigest()


def normalize_fetched_item(raw: RawFetchedItem) -> NormalizedItem:
    normalized_title = collapse_whitespace(raw.title)
    canonical_url = canonicalize_url(raw.url)
    published_at = raw.published_at or datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    score_input = ScoreInput(
        source_score=float(raw.source_score),
        relevance_score=50,
        impact_score=50,
        novelty_score=50,
        actionability_score=50,
        freshness_score=50,
    )
    final_score = calculate_final_score(score_input)
    action_level = None
    if raw.channel == "amazon":
        action_level = seller_action_level(final_score, score_input.impact_score, score_input.actionability_score)

    excerpt = collapse_whitespace(raw.excerpt)

    return NormalizedItem(
        channel=raw.channel,
        source_id=raw.source_id,
        raw_title=raw.title,
        normalized_title=normalized_title,
        url=canonical_url,
        source_name=raw.source_name,
        published_at=published_at,
        content_hash=build_content_hash(raw.channel, raw.source_id, normalized_title, canonical_url),
        raw_excerpt=excerpt,
        summary=excerpt,
        category=raw.default_category,
        keywords=(),
        source_score=float(raw.source_score),
        relevance_score=score_input.relevance_score,
        impact_score=score_input.impact_score,
        novelty_score=score_input.novelty_score,
        actionability_score=score_input.actionability_score,
        freshness_score=score_input.freshness_score,
        final_score=final_score,
        entry_reason="公开信源条目，已完成基础规范化。",
        suggested_action="人工复核后决定是否进入精选。",
        seller_action_level=action_level,
    )

