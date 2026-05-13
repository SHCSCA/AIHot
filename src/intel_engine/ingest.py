from __future__ import annotations

from dataclasses import dataclass

from intel_engine.normalizer import RawFetchedItem, normalize_fetched_item
from intel_engine.storage import ItemRepository


@dataclass(frozen=True)
class IngestStats:
    inserted: int
    duplicates: int


def ingest_items(repository: ItemRepository, raw_items: list[RawFetchedItem]) -> IngestStats:
    inserted = 0
    duplicates = 0

    for raw_item in raw_items:
        result = repository.upsert_item(normalize_fetched_item(raw_item))
        if result.created:
            inserted += 1
        else:
            duplicates += 1

    return IngestStats(inserted=inserted, duplicates=duplicates)

