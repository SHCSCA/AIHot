from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Protocol


TITLE_TOKEN_RE = re.compile(r"[a-z0-9\u4e00-\u9fff]+", re.IGNORECASE)
SOURCE_TIER_ORDER = {
    "T1": 0,
    "T1.5": 1,
    "T2": 2,
    "T3": 3,
}


@dataclass(frozen=True)
class ClusterCandidate:
    item_id: int
    channel: str
    source_id: str
    source_tier: str
    source_authority_weight: float
    title: str
    canonical_url: str
    content_hash: str
    category: str
    published_at: datetime | None
    final_score: float
    embedding: list[float] | None = None


@dataclass(frozen=True)
class EventClusterDraft:
    cluster_key: str
    channel: str
    canonical_title: str
    main_item_id: int
    category: str
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    member_item_ids: tuple[int, ...]
    source_ids: tuple[str, ...]
    member_count: int
    source_count: int
    cluster_score: float
    embedding: list[float] | None


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]:
        ...


class StaticEmbeddingProvider:
    def __init__(self, vector: list[float]):
        self.vector = vector

    def embed(self, text: str) -> list[float]:
        return list(self.vector)


def cluster_candidates(
    candidates: list[ClusterCandidate],
    *,
    title_similarity_threshold: float = 0.84,
    embedding_provider: EmbeddingProvider | None = None,
) -> list[EventClusterDraft]:
    groups: list[list[ClusterCandidate]] = []
    for candidate in candidates:
        matched = _find_group(groups, candidate, title_similarity_threshold)
        if matched is None:
            groups.append([candidate])
        else:
            matched.append(candidate)

    return [_build_cluster(group, embedding_provider=embedding_provider) for group in groups]


def _find_group(
    groups: list[list[ClusterCandidate]],
    candidate: ClusterCandidate,
    title_similarity_threshold: float,
) -> list[ClusterCandidate] | None:
    for group in groups:
        if any(_is_same_event(existing, candidate, title_similarity_threshold) for existing in group):
            return group
    return None


def _is_same_event(first: ClusterCandidate, second: ClusterCandidate, title_similarity_threshold: float) -> bool:
    if first.channel != second.channel:
        return False
    if first.canonical_url and first.canonical_url == second.canonical_url:
        return True
    if first.content_hash and first.content_hash == second.content_hash:
        return True
    return _title_similarity(first.title, second.title) >= title_similarity_threshold


def _build_cluster(
    members: list[ClusterCandidate],
    *,
    embedding_provider: EmbeddingProvider | None,
) -> EventClusterDraft:
    main = max(members, key=_main_candidate_key)
    published_times = [member.published_at for member in members if member.published_at is not None]
    embedding = main.embedding
    if embedding is None and embedding_provider is not None:
        embedding = embedding_provider.embed(main.title)

    return EventClusterDraft(
        cluster_key=_cluster_key(main),
        channel=main.channel,
        canonical_title=main.title,
        main_item_id=main.item_id,
        category=main.category,
        first_seen_at=min(published_times) if published_times else None,
        last_seen_at=max(published_times) if published_times else None,
        member_item_ids=tuple(member.item_id for member in members),
        source_ids=tuple(sorted({member.source_id for member in members})),
        member_count=len(members),
        source_count=len({member.source_id for member in members}),
        cluster_score=max(member.final_score for member in members),
        embedding=embedding,
    )


def _main_candidate_key(candidate: ClusterCandidate) -> tuple[int, float, float, datetime | None]:
    tier_rank = -SOURCE_TIER_ORDER.get(candidate.source_tier, 99)
    return (tier_rank, candidate.source_authority_weight, candidate.final_score, candidate.published_at)


def _cluster_key(candidate: ClusterCandidate) -> str:
    if candidate.canonical_url:
        return f"url:{candidate.canonical_url}"
    if candidate.content_hash:
        return f"hash:{candidate.content_hash}"
    return f"title:{_normalize_title(candidate.title)}"


def _title_similarity(first: str, second: str) -> float:
    return SequenceMatcher(a=_normalize_title(first), b=_normalize_title(second)).ratio()


def _normalize_title(title: str) -> str:
    return " ".join(token.lower() for token in TITLE_TOKEN_RE.findall(title))
