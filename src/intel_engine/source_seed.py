from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from intel_engine.channel_config import CHANNELS_DIR, SourceConfig, load_channel_configs
from intel_engine.sources import SourceRegistry, SourceUpsert


@dataclass(frozen=True)
class SourceSeedStats:
    created: int
    updated: int
    total: int


TRUST_LEVEL_TO_TIER = {
    "official": "T1",
    "official_social": "T1.5",
    "authority": "T2",
    "expert": "T2",
    "community": "T3",
    "media": "T3",
}

SOURCE_TYPE_MAP = {
    "rss": "rss",
    "feed": "rss",
    "website": "html",
    "official": "html",
    "authority": "html",
    "blog": "html",
    "api": "api",
    "github": "github",
    "docs": "docs",
    "social": "social",
    "forum": "forum",
}


def _source_type(source: SourceConfig) -> str:
    return SOURCE_TYPE_MAP.get(source.source_type, "html")


def _tier(source: SourceConfig) -> str:
    return TRUST_LEVEL_TO_TIER.get(source.trust_level, "T3")


def _fetch_adapter(source: SourceConfig) -> str:
    parser_type = source.parser_type.lower()
    mapped_type = _source_type(source)
    if parser_type in {"rss", "atom"} or mapped_type == "rss":
        return "rss"
    if mapped_type == "github":
        return "github"
    if mapped_type == "api":
        return "api"
    return "http_article"


def _noise_level(tier: str) -> float:
    return {
        "T1": 0.05,
        "T1.5": 0.12,
        "T2": 0.18,
        "T3": 0.35,
    }[tier]


def source_upsert_from_config(channel_id: str, source: SourceConfig) -> SourceUpsert:
    tier = _tier(source)
    return SourceUpsert(
        id=source.id,
        channel=channel_id,
        source_type=_source_type(source),
        tier=tier,
        name=source.name,
        url=source.url,
        language=source.language,
        region=source.region,
        marketplace=source.metadata.get("marketplace"),
        authority_weight=float(source.base_weight),
        noise_level=_noise_level(tier),
        fetch_adapter=_fetch_adapter(source),
        parser_type=source.parser_type,
        default_categories=list(source.default_categories),
        fetch_interval_minutes=60,
        enabled=source.enabled,
        visibility="public" if source.enabled else "hidden",
        notes=None,
    )


def seed_sources_from_channel_configs(
    session: Session,
    channels_dir: Path = CHANNELS_DIR,
) -> SourceSeedStats:
    registry = SourceRegistry(session)
    created = 0
    updated = 0
    total = 0

    for channel in load_channel_configs(channels_dir):
        for source in channel.sources:
            total += 1
            result = registry.upsert_source(source_upsert_from_config(channel.id, source))
            if result.created:
                created += 1
            else:
                updated += 1

    session.flush()
    return SourceSeedStats(created=created, updated=updated, total=total)
