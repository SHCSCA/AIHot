from __future__ import annotations

from datetime import datetime, timezone

from intel_engine.clustering import ClusterCandidate, StaticEmbeddingProvider, cluster_candidates


def _candidate(**overrides):
    data = {
        "item_id": 1,
        "channel": "ai",
        "source_id": "openai_news",
        "source_tier": "T1",
        "source_authority_weight": 95,
        "title": "OpenAI launches GPT 5",
        "canonical_url": "https://example.com/gpt-5",
        "content_hash": "hash-1",
        "category": "ai_models",
        "published_at": datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc),
        "final_score": 90,
        "embedding": None,
    }
    data.update(overrides)
    return ClusterCandidate(**data)


def test_exact_url_or_hash_candidates_join_same_cluster():
    clusters = cluster_candidates(
        [
            _candidate(item_id=1, canonical_url="https://example.com/a", content_hash="hash-a"),
            _candidate(item_id=2, source_id="media", source_tier="T2", canonical_url="https://example.com/a", content_hash="hash-b"),
            _candidate(item_id=3, source_id="blog", source_tier="T3", canonical_url="https://example.com/c", content_hash="hash-a"),
        ]
    )

    assert len(clusters) == 1
    assert clusters[0].member_item_ids == (1, 2, 3)
    assert clusters[0].source_count == 3


def test_similar_titles_join_and_official_source_becomes_main_item():
    clusters = cluster_candidates(
        [
            _candidate(
                item_id=1,
                source_id="kol_blog",
                source_tier="T3",
                source_authority_weight=55,
                title="OpenAI launches GPT 5 model",
                canonical_url="https://blog.example.com/gpt5",
                content_hash="hash-1",
                final_score=96,
            ),
            _candidate(
                item_id=2,
                source_id="openai_news",
                source_tier="T1",
                source_authority_weight=95,
                title="OpenAI launches GPT-5",
                canonical_url="https://openai.com/news/gpt-5",
                content_hash="hash-2",
                final_score=88,
            ),
        ]
    )

    assert len(clusters) == 1
    assert clusters[0].main_item_id == 2
    assert clusters[0].canonical_title == "OpenAI launches GPT-5"
    assert clusters[0].cluster_score == 96


def test_embedding_provider_is_reserved_for_cluster_vectors():
    clusters = cluster_candidates(
        [_candidate()],
        embedding_provider=StaticEmbeddingProvider([0.1, 0.2, 0.3]),
    )

    assert clusters[0].embedding == [0.1, 0.2, 0.3]
