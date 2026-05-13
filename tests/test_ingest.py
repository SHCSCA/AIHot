from datetime import datetime, timezone

from intel_engine.ingest import ingest_items
from intel_engine.normalizer import RawFetchedItem
from intel_engine.storage import ItemRepository, create_engine_for_path, init_db


def make_raw_item(title: str = "OpenAI ships a new model") -> RawFetchedItem:
    return RawFetchedItem(
        channel="ai",
        source_id="openai_news",
        source_name="OpenAI News",
        title=title,
        url="https://example.com/model",
        published_at=datetime(2026, 5, 11, 8, 0, tzinfo=timezone.utc),
        excerpt="Short model update.",
        raw_content="Short model update.",
        default_category="ai_models",
        source_score=95,
    )


def test_ingest_items_normalizes_and_deduplicates(tmp_path):
    engine = create_engine_for_path(tmp_path / "intel.sqlite3")
    init_db(engine)
    repo = ItemRepository(engine)

    stats = ingest_items(repo, [make_raw_item(), make_raw_item("  OpenAI ships a new model  ")])
    items = repo.list_items(channel="ai")

    assert stats.inserted == 1
    assert stats.duplicates == 1
    assert len(items) == 1
    assert items[0].normalized_title == "OpenAI ships a new model"

