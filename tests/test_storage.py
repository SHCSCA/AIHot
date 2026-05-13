from datetime import datetime, timezone

from intel_engine.normalizer import NormalizedItem
from intel_engine.storage import ItemRepository, create_engine_for_path, init_db


def make_item(content_hash: str = "hash-1") -> NormalizedItem:
    return NormalizedItem(
        channel="amazon",
        source_id="amazon_ads_updates",
        raw_title="Amazon Ads update",
        normalized_title="Amazon Ads update",
        url="https://example.com/ads",
        source_name="Amazon Ads Updates",
        published_at=datetime(2026, 5, 11, 8, 0, tzinfo=timezone.utc),
        content_hash=content_hash,
        raw_excerpt="Sponsored Ads update.",
        summary="Sponsored Ads update.",
        category="ads_ppc",
        keywords=(),
        source_score=92,
        relevance_score=50,
        impact_score=50,
        novelty_score=50,
        actionability_score=50,
        freshness_score=50,
        final_score=58.4,
        entry_reason="官方广告更新。",
        suggested_action="检查广告活动设置。",
        seller_action_level="review",
    )


def test_repository_skips_duplicate_content_hash(tmp_path):
    engine = create_engine_for_path(tmp_path / "intel.sqlite3")
    init_db(engine)
    repo = ItemRepository(engine)

    first = repo.upsert_item(make_item())
    second = repo.upsert_item(make_item())
    items = repo.list_items(channel="amazon")

    assert first.created is True
    assert second.created is False
    assert first.item_id == second.item_id
    assert len(items) == 1
    assert items[0].content_hash == "hash-1"

