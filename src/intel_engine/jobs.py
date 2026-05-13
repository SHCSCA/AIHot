from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

from intel_engine.channel_config import CHANNELS_DIR, ChannelConfig, load_channel_configs
from intel_engine.crawler import crawl_source
from intel_engine.ingest import ingest_items
from intel_engine.storage import ItemRepository


@dataclass(frozen=True)
class CrawlError:
    channel: str
    source_id: str
    message: str


@dataclass(frozen=True)
class CrawlRunStats:
    channels: int
    sources: int
    fetched: int
    inserted: int
    duplicates: int
    errors: tuple[CrawlError, ...]


def _select_channels(configs: tuple[ChannelConfig, ...], channel_id: str | None) -> tuple[ChannelConfig, ...]:
    if channel_id is None:
        return configs
    return tuple(config for config in configs if config.id == channel_id)


def crawl_enabled_sources(
    repository: ItemRepository,
    channels_dir: Path = CHANNELS_DIR,
    channel_id: str | None = None,
    client: httpx.Client | None = None,
) -> CrawlRunStats:
    configs = _select_channels(load_channel_configs(channels_dir), channel_id)
    sources = 0
    fetched = 0
    inserted = 0
    duplicates = 0
    errors: list[CrawlError] = []

    for config in configs:
        for source in config.sources:
            if not source.enabled:
                continue
            sources += 1
            try:
                raw_items = crawl_source(source, config.id, client=client)
                fetched += len(raw_items)
                stats = ingest_items(repository, raw_items)
                inserted += stats.inserted
                duplicates += stats.duplicates
            except Exception as exc:  # noqa: BLE001 - keep one bad source from stopping the run.
                errors.append(CrawlError(channel=config.id, source_id=source.id, message=str(exc)))

    return CrawlRunStats(
        channels=len(configs),
        sources=sources,
        fetched=fetched,
        inserted=inserted,
        duplicates=duplicates,
        errors=tuple(errors),
    )

