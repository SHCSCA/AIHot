from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHANNELS_DIR = PROJECT_ROOT / "channels"
COLLECTION_CONFIG_PATH = PROJECT_ROOT / "config" / "collection.yaml"


def _require_positive_interval(value: Any, field_name: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


@dataclass(frozen=True)
class CollectionPolicy:
    crawl_interval_minutes: int

    def __post_init__(self) -> None:
        _require_positive_interval(
            self.crawl_interval_minutes,
            "crawl_interval_minutes",
        )


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
        raise ValueError(f"YAML config must be a mapping: {path}")
    return data


def load_collection_policy(path: Path = COLLECTION_CONFIG_PATH) -> CollectionPolicy:
    if not path.is_file():
        raise FileNotFoundError(f"Collection policy does not exist: {path}")
    data = _load_yaml(path)
    return CollectionPolicy(
        crawl_interval_minutes=_require_positive_interval(
            data.get("crawl_interval_minutes"),
            "crawl_interval_minutes",
        )
    )


def _parse_category(data: dict[str, Any]) -> CategoryConfig:
    return CategoryConfig(
        id=_require_string(data, "id"), label=_require_string(data, "label")
    )


def _parse_source(
    data: dict[str, Any], collection_policy: CollectionPolicy
) -> SourceConfig:
    if "crawl_interval_minutes" in data:
        raise ValueError(
            "Source crawl_interval_minutes is not supported; configure "
            "config/collection.yaml instead"
        )
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
        "parser_type",
        "enabled",
    }
    categories = data.get("default_categories", [])
    if not isinstance(categories, list) or not all(
        isinstance(item, str) for item in categories
    ):
        raise ValueError("default_categories must be a list of strings")

    base_weight = data.get("base_weight")
    if not isinstance(base_weight, int):
        raise ValueError("base_weight must be an integer")

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
        crawl_interval_minutes=collection_policy.crawl_interval_minutes,
        parser_type=_require_string(data, "parser_type"),
        enabled=enabled,
        metadata=metadata,
    )


def parse_channel_config(
    data: dict[str, Any],
    *,
    policy: CollectionPolicy | None = None,
) -> ChannelConfig:
    effective_policy = policy or load_collection_policy()
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
        sources=tuple(_parse_source(item, effective_policy) for item in sources),
    )


def load_channel_configs(
    channels_dir: Path = CHANNELS_DIR,
    *,
    policy: CollectionPolicy | None = None,
) -> tuple[ChannelConfig, ...]:
    if not channels_dir.exists():
        raise FileNotFoundError(f"Channels directory does not exist: {channels_dir}")

    effective_policy = policy or load_collection_policy()
    configs = []
    for path in sorted(channels_dir.glob("*.yaml")):
        data = _load_yaml(path)
        catalog_paths = data.pop("source_catalogs", [])
        if not isinstance(catalog_paths, list) or not all(
            isinstance(item, str) and item.strip() for item in catalog_paths
        ):
            raise ValueError(f"source_catalogs must be a list of paths: {path}")
        merged_sources = data.get("sources", [])
        if not isinstance(merged_sources, list):
            raise ValueError(f"sources must be a list: {path}")
        merged_sources = list(merged_sources)
        for catalog_path in catalog_paths:
            catalog_file = (path.parent / catalog_path).resolve()
            if path.parent.resolve() not in catalog_file.parents:
                raise ValueError(
                    f"Source catalog must stay within channels/: {catalog_path}"
                )
            catalog = _load_yaml(catalog_file)
            catalog_sources = catalog.get("sources", [])
            if not isinstance(catalog_sources, list):
                raise ValueError(f"sources must be a list: {catalog_file}")
            merged_sources.extend(catalog_sources)
        data["sources"] = merged_sources
        _validate_unique_sources(merged_sources, path)
        configs.append(
            parse_channel_config(
                data,
                policy=effective_policy,
            )
        )

    if not configs:
        raise ValueError(f"No channel configs found in: {channels_dir}")
    return tuple(configs)


def _validate_unique_sources(sources: list[dict[str, Any]], channel_path: Path) -> None:
    source_ids: set[str] = set()
    source_urls: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError(f"Each source must be a mapping: {channel_path}")
        source_id = _require_string(source, "id")
        source_url = _require_string(source, "url").rstrip("/").lower()
        if source_id in source_ids:
            raise ValueError(f"Duplicate source id in {channel_path}: {source_id}")
        is_collectable = (
            source.get("enabled") is True
            and source.get("collection_status", "collectable") == "collectable"
        )
        if is_collectable and source_url in source_urls:
            raise ValueError(
                f"Duplicate enabled source url in {channel_path}: {source_url}"
            )
        source_ids.add(source_id)
        if is_collectable:
            source_urls.add(source_url)


def get_channel_config(
    channel_id: str,
    channels_dir: Path = CHANNELS_DIR,
    *,
    policy: CollectionPolicy | None = None,
) -> ChannelConfig:
    for config in load_channel_configs(
        channels_dir,
        policy=policy,
    ):
        if config.id == channel_id:
            return config
    raise KeyError(f"Unknown channel: {channel_id}")
