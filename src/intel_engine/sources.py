from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from intel_engine.models import SourceRecord, SourceStateRecord, utc_now


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
        record.contributor_no = source.contributor_no
        record.social_handle = source.social_handle
        record.collection_status = source.collection_status
        record.free_access = source.free_access
        record.notes = source.notes

        if self.session.get(SourceStateRecord, source.id) is None:
            self.session.add(SourceStateRecord(source_id=source.id, next_fetch_at=datetime(1970, 1, 1, tzinfo=timezone.utc)))

        self.session.flush()
        return SourceUpsertResult(source_id=source.id, created=created)

    def get_source(self, source_id: str) -> SourceRecord:
        record = self.session.get(SourceRecord, source_id)
        if record is None:
            raise KeyError(f"Unknown source: {source_id}")
        return record

    def list_sources(self, channel: str | None = None, enabled: bool | None = None) -> list[SourceRecord]:
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
