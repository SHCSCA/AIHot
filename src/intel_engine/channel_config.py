from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHANNELS_DIR = PROJECT_ROOT / "channels"


@dataclass(frozen=True)
class CategoryConfig:
    id: str
    label: str


@dataclass(frozen=True)
class SourceConfig:
    id: str
    source_type: str
    name: str
    url: str
    language: str
    region: str
    trust_level: str
    base_weight: int
    default_categories: tuple[str, ...]
    crawl_interval_minutes: int
    parser_type: str
    enabled: bool
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ChannelConfig:
    id: str
    name: str
    description: str
    categories: tuple[CategoryConfig, ...]
    scoring: dict[str, Any]
    sources: tuple[SourceConfig, ...]


def _require_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing required string field: {key}")
    return value


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Channel config must be a mapping: {path}")
    return data


def _parse_category(data: dict[str, Any]) -> CategoryConfig:
    return CategoryConfig(id=_require_string(data, "id"), label=_require_string(data, "label"))


def _parse_source(data: dict[str, Any]) -> SourceConfig:
    known_keys = {
        "id",
        "source_type",
        "name",
        "url",
        "language",
        "region",
        "trust_level",
        "base_weight",
        "default_categories",
        "crawl_interval_minutes",
        "parser_type",
        "enabled",
    }
    categories = data.get("default_categories", [])
    if not isinstance(categories, list) or not all(isinstance(item, str) for item in categories):
        raise ValueError("default_categories must be a list of strings")

    base_weight = data.get("base_weight")
    if not isinstance(base_weight, int):
        raise ValueError("base_weight must be an integer")

    crawl_interval = data.get("crawl_interval_minutes")
    if not isinstance(crawl_interval, int):
        raise ValueError("crawl_interval_minutes must be an integer")

    enabled = data.get("enabled")
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be a boolean")

    metadata = {key: value for key, value in data.items() if key not in known_keys}

    return SourceConfig(
        id=_require_string(data, "id"),
        source_type=_require_string(data, "source_type"),
        name=_require_string(data, "name"),
        url=_require_string(data, "url"),
        language=_require_string(data, "language"),
        region=_require_string(data, "region"),
        trust_level=_require_string(data, "trust_level"),
        base_weight=base_weight,
        default_categories=tuple(categories),
        crawl_interval_minutes=crawl_interval,
        parser_type=_require_string(data, "parser_type"),
        enabled=enabled,
        metadata=metadata,
    )


def parse_channel_config(data: dict[str, Any]) -> ChannelConfig:
    categories = data.get("categories", [])
    if not isinstance(categories, list) or not categories:
        raise ValueError("categories must be a non-empty list")

    sources = data.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("sources must be a list")

    scoring = data.get("scoring", {})
    if not isinstance(scoring, dict):
        raise ValueError("scoring must be a mapping")

    return ChannelConfig(
        id=_require_string(data, "id"),
        name=_require_string(data, "name"),
        description=_require_string(data, "description"),
        categories=tuple(_parse_category(item) for item in categories),
        scoring=scoring,
        sources=tuple(_parse_source(item) for item in sources),
    )


def load_channel_configs(channels_dir: Path = CHANNELS_DIR) -> tuple[ChannelConfig, ...]:
    if not channels_dir.exists():
        raise FileNotFoundError(f"Channels directory does not exist: {channels_dir}")

    configs = []
    for path in sorted(channels_dir.glob("*.yaml")):
        configs.append(parse_channel_config(_load_yaml(path)))

    if not configs:
        raise ValueError(f"No channel configs found in: {channels_dir}")
    return tuple(configs)


def get_channel_config(channel_id: str, channels_dir: Path = CHANNELS_DIR) -> ChannelConfig:
    for config in load_channel_configs(channels_dir):
        if config.id == channel_id:
            return config
    raise KeyError(f"Unknown channel: {channel_id}")

