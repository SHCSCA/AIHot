from datetime import datetime, timezone

from intel_engine.normalizer import RawFetchedItem, normalize_fetched_item


def test_normalizer_canonicalizes_url_and_creates_stable_hash():
    published_at = datetime(2026, 5, 11, 8, 0, tzinfo=timezone.utc)
    first = RawFetchedItem(
        channel="ai",
        source_id="openai_news",
        source_name="OpenAI News",
        title="  OpenAI 发布新模型  ",
        url="https://example.com/news/new-model?utm_source=x#comments",
        published_at=published_at,
        excerpt="模型能力更新。",
        raw_content="模型能力更新。",
        default_category="ai_models",
        source_score=95,
    )
    second = RawFetchedItem(
        channel="ai",
        source_id="openai_news",
        source_name="OpenAI News",
        title="OpenAI 发布新模型",
        url="https://example.com/news/new-model",
        published_at=published_at,
        excerpt="模型能力更新。",
        raw_content="模型能力更新。",
        default_category="ai_models",
        source_score=95,
    )

    normalized_first = normalize_fetched_item(first)
    normalized_second = normalize_fetched_item(second)

    assert normalized_first.url == "https://example.com/news/new-model"
    assert normalized_first.normalized_title == "OpenAI 发布新模型"
    assert normalized_first.content_hash == normalized_second.content_hash
    assert normalized_first.category == "ai_models"

