from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from intel_engine.models import SourceRecord, SourceStateRecord, utc_now


PUBLISHER_KEY_ALIASES = {
    "amazon": "company:amazon",
    "github:amzn": "company:amazon",
    "github:aws": "company:amazon",
    "github_org:amzn": "company:amazon",
    "github_org:aws": "company:amazon",
    "github:microsoft": "company:microsoft",
    "github_org:microsoft": "company:microsoft",
    "github:google": "company:google",
    "github:google-deepmind": "company:google",
    "github:google-ai-edge": "company:google",
    "github_org:google": "company:google",
    "github_org:google-deepmind": "company:google",
    "github_org:google-ai-edge": "company:google",
    "github_org:genkit-ai": "company:google",
    "github_org:tensorflow": "company:google",
    "github_org:keras-team": "company:google",
    "github:openai": "company:openai",
    "github_org:openai": "company:openai",
    "github:anthropics": "company:anthropic",
    "github_org:anthropics": "company:anthropic",
    "github:huggingface": "company:huggingface",
    "github_org:huggingface": "company:huggingface",
    "github:nvidia": "company:nvidia",
    "github_org:nvidia": "company:nvidia",
    "github_org:nvidia-nemo": "company:nvidia",
    "github_org:nvlabs": "company:nvidia",
    "github_org:autogluon": "company:amazon",
    "research:arxiv": "research:arxiv",
}

PUBLISHER_HOST_ALIASES = {
    "openai.com": "company:openai",
    "anthropic.com": "company:anthropic",
    "google.com": "company:google",
    "googleblog.com": "company:google",
    "deepmind.google": "company:google",
    "microsoft.com": "company:microsoft",
    "amazon.com": "company:amazon",
    "aboutamazon.com": "company:amazon",
    "meta.com": "company:meta",
    "huggingface.co": "company:huggingface",
    "nvidia.com": "company:nvidia",
    "arxiv.org": "research:arxiv",
}


@dataclass(frozen=True)
class SourceUpsert:
    id: str
    channel: str
    source_type: str
    tier: str
    name: str
    url: str
    language: str
    region: str
    marketplace: str | None
    authority_weight: float
    noise_level: float
    fetch_adapter: str
    parser_type: str
    default_categories: list[str]
    fetch_interval_minutes: int
    enabled: bool
    visibility: str
    source_group: str = "media"
    publisher_key: str | None = None
    contributor_no: str | None = None
    social_handle: str | None = None
    collection_status: str = "collectable"
    free_access: bool = True
    notes: str | None = None


@dataclass(frozen=True)
class SourceUpsertResult:
    source_id: str
    created: bool


class SourceRegistry:
    def __init__(self, session: Session):
        self.session = session

    def upsert_source(self, source: SourceUpsert) -> SourceUpsertResult:
        record = self.session.get(SourceRecord, source.id)
        created = record is None
        previous_interval = (
            record.fetch_interval_minutes if record is not None else None
        )
        if record is None:
            record = SourceRecord(id=source.id)
            self.session.add(record)

        record.channel = source.channel
        record.source_type = source.source_type
        record.tier = source.tier
        record.name = source.name
        record.url = source.url
        record.language = source.language
        record.region = source.region
        record.marketplace = source.marketplace
        record.authority_weight = float(source.authority_weight)
        record.noise_level = float(source.noise_level)
        record.fetch_adapter = source.fetch_adapter
        record.parser_type = source.parser_type
        record.default_categories = list(source.default_categories)
        record.fetch_interval_minutes = source.fetch_interval_minutes
        record.enabled = source.enabled
        record.visibility = source.visibility
        record.source_group = source.source_group
        record.publisher_key = normalize_publisher_key(
            source.publisher_key,
            source.url,
            source.id,
        )
        record.contributor_no = source.contributor_no
        record.social_handle = source.social_handle
        record.collection_status = source.collection_status
        record.free_access = source.free_access
        record.notes = source.notes

        state = self.session.get(SourceStateRecord, source.id)
        if state is None:
            self.session.add(
                SourceStateRecord(
                    source_id=source.id,
                    next_fetch_at=datetime(1970, 1, 1, tzinfo=timezone.utc),
                )
            )
        elif (
            previous_interval != source.fetch_interval_minutes
            and state.last_success_at is not None
        ):
            state.next_fetch_at = state.last_success_at + timedelta(
                minutes=source.fetch_interval_minutes
            )

        self.session.flush()
        return SourceUpsertResult(source_id=source.id, created=created)

    def get_source(self, source_id: str) -> SourceRecord:
        record = self.session.get(SourceRecord, source_id)
        if record is None:
            raise KeyError(f"Unknown source: {source_id}")
        return record

    def list_sources(
        self, channel: str | None = None, enabled: bool | None = None
    ) -> list[SourceRecord]:
        stmt = select(SourceRecord).order_by(SourceRecord.channel, SourceRecord.id)
        if channel is not None:
            stmt = stmt.where(SourceRecord.channel == channel)
        if enabled is not None:
            stmt = stmt.where(SourceRecord.enabled == enabled)
        return list(self.session.scalars(stmt).all())

    def set_enabled(self, source_id: str, enabled: bool) -> None:
        record = self.get_source(source_id)
        record.enabled = enabled
        record.updated_at = utc_now()
        self.session.flush()

    def update_state(
        self,
        source_id: str,
        *,
        last_success_at: datetime | None = None,
        last_error_at: datetime | None = None,
        error_streak: int | None = None,
        next_fetch_at: datetime | None = None,
        backoff_until: datetime | None = None,
        avg_latency_ms: float | None = None,
        items_per_run: float | None = None,
        duplicate_ratio: float | None = None,
        noise_ratio: float | None = None,
        health_score: float | None = None,
    ) -> SourceStateRecord:
        if self.session.get(SourceRecord, source_id) is None:
            raise KeyError(f"Unknown source: {source_id}")

        state = self.session.get(SourceStateRecord, source_id)
        if state is None:
            state = SourceStateRecord(source_id=source_id)
            self.session.add(state)

        updates = {
            "last_success_at": last_success_at,
            "last_error_at": last_error_at,
            "error_streak": error_streak,
            "next_fetch_at": next_fetch_at,
            "backoff_until": backoff_until,
            "avg_latency_ms": avg_latency_ms,
            "items_per_run": items_per_run,
            "duplicate_ratio": duplicate_ratio,
            "noise_ratio": noise_ratio,
            "health_score": health_score,
        }
        for field_name, value in updates.items():
            if value is not None:
                setattr(state, field_name, value)
        state.updated_at = utc_now()
        self.session.flush()
        return state


def publisher_key_from_url(url: str, source_id: str) -> str:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower().removeprefix("www.")
    path_parts = [part for part in parsed.path.split("/") if part]
    if hostname == "github.com" and path_parts:
        return f"github_org:{path_parts[0].lower()}"
    if hostname.endswith("feedburner.com") and path_parts:
        return f"feedburner:{path_parts[0].lower()}"
    if hostname == "medium.com" and path_parts:
        publisher = path_parts[-1].removeprefix("@").lower()
        return f"medium:{publisher}" if publisher else f"source:{source_id}"
    return hostname or f"source:{source_id}"


def normalize_publisher_key(
    publisher_key: str | None,
    url: str,
    source_id: str,
) -> str:
    normalized_input = publisher_key.strip().casefold() if publisher_key else ""
    derived = normalized_input or publisher_key_from_url(url, source_id)
    if derived in PUBLISHER_KEY_ALIASES:
        return PUBLISHER_KEY_ALIASES[derived]

    hostname = (urlparse(url).hostname or "").lower().removeprefix("www.")
    for host_suffix, canonical_key in PUBLISHER_HOST_ALIASES.items():
        if hostname == host_suffix or hostname.endswith(f".{host_suffix}"):
            return canonical_key
    return derived
