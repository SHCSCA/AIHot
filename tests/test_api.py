from fastapi.testclient import TestClient

from intel_engine.main import create_app
from intel_engine.normalizer import NormalizedItem
from intel_engine.storage import ItemRepository
from datetime import datetime, timezone


def test_health_endpoint():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "intel-engine"}


def test_channels_endpoint_returns_both_channels():
    client = TestClient(create_app())

    response = client.get("/api/public/channels")

    assert response.status_code == 200
    payload = response.json()
    channel_ids = {channel["id"] for channel in payload["channels"]}
    assert channel_ids == {"ai", "amazon"}


def test_items_endpoint_returns_stored_items(tmp_path):
    app = create_app(db_path=tmp_path / "intel.sqlite3")
    repo = ItemRepository(app.state.db_engine)
    repo.upsert_item(
        NormalizedItem(
            channel="ai",
            source_id="openai_news",
            raw_title="OpenAI ships a new model",
            normalized_title="OpenAI ships a new model",
            url="https://example.com/model",
            source_name="OpenAI News",
            published_at=datetime(2026, 5, 11, 8, 0, tzinfo=timezone.utc),
            content_hash="hash-api-1",
            raw_excerpt="Short model update.",
            summary="Short model update.",
            category="ai_models",
            keywords=(),
            source_score=95,
            relevance_score=80,
            impact_score=85,
            novelty_score=70,
            actionability_score=65,
            freshness_score=90,
            final_score=81.5,
            entry_reason="官方模型更新。",
            suggested_action="关注模型能力变化。",
            seller_action_level=None,
        )
    )
    client = TestClient(app)

    response = client.get("/api/public/items?channel=ai&take=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["title"] == "OpenAI ships a new model"
    assert payload["items"][0]["finalScore"] == 81.5
