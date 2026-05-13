from __future__ import annotations

from datetime import date, datetime, time, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from intel_engine.normalizer import canonicalize_url


OPERATIONAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
NON_ARTICLE_PATHS = {
    "",
    "/",
    "/blog",
    "/blogs",
    "/news",
    "/feed",
    "/feeds",
    "/rss",
    "/articles",
    "/updates",
    "/resources",
}


def operational_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(day, time.min, tzinfo=OPERATIONAL_TIMEZONE)
    end_local = datetime.combine(day, time.max, tzinfo=OPERATIONAL_TIMEZONE)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def is_same_operational_day(published_at: datetime | None, now: datetime) -> bool:
    if published_at is None:
        return False
    return _aware(published_at).astimezone(OPERATIONAL_TIMEZONE).date() == _aware(now).astimezone(
        OPERATIONAL_TIMEZONE
    ).date()


def is_publishable_original_url(item_url: str | None, source_url: str) -> bool:
    if not item_url:
        return False
    item = canonicalize_url(item_url)
    source = canonicalize_url(source_url)
    if item == source:
        return False

    item_parts = urlparse(item)
    if not item_parts.scheme or not item_parts.netloc:
        return False

    path = item_parts.path.rstrip("/").lower()
    if path in NON_ARTICLE_PATHS:
        return False
    if path.endswith((".xml", ".rss", ".atom")):
        return False

    source_parts = urlparse(source)
    if item_parts.scheme == source_parts.scheme and item_parts.netloc == source_parts.netloc:
        source_path = source_parts.path.rstrip("/").lower()
        if source_path and path == source_path:
            return False

    return True


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
