from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from intel_engine.clustering import ClusterCandidate, cluster_candidates
from intel_engine.fetchers import get_fetch_adapter
from intel_engine.llm import FakeLLMProvider, LLMProvider, ModelScore, build_llm_provider
from intel_engine.models import (
    ClusterMemberRecord,
    EventClusterRecord,
    FetchJobRecord,
    ModelScoreRecord,
    NormalizedItemRecord,
    PrefilterResultRecord,
    RankedItemRecord,
    RawDocumentRecord,
    SourceRecord,
    StrategyVersionRecord,
    utc_now,
)
from intel_engine.normalizer import canonicalize_url
from intel_engine.prescreen import PreScreenDecision
from intel_engine.quality import is_same_operational_day
from intel_engine.rank_policy import RankPolicy, RankPolicyInput
from intel_engine.raw_store import RawStore
from intel_engine.scheduler import claim_fetch_jobs, mark_job_failed, mark_job_succeeded, schedule_due_sources
from intel_engine.settings import Settings


@dataclass(frozen=True)
class PipelineStats:
    scheduled: int = 0
    claimed: int = 0
    succeeded: int = 0
    failed: int = 0
    raw_documents_inserted: int = 0
    duplicates: int = 0
    normalized_items: int = 0
    ranked_items: int = 0
    clusters: int = 0

    def add(self, other: "PipelineStats") -> "PipelineStats":
        return PipelineStats(
            scheduled=self.scheduled + other.scheduled,
            claimed=self.claimed + other.claimed,
            succeeded=self.succeeded + other.succeeded,
            failed=self.failed + other.failed,
            raw_documents_inserted=self.raw_documents_inserted + other.raw_documents_inserted,
            duplicates=self.duplicates + other.duplicates,
            normalized_items=self.normalized_items + other.normalized_items,
            ranked_items=self.ranked_items + other.ranked_items,
            clusters=self.clusters + other.clusters,
        )


@dataclass(frozen=True)
class ReprocessStats:
    items: int = 0
    failed: int = 0


def run_scheduler_once(
    SessionLocal: sessionmaker[Session],
    *,
    now: datetime | None = None,
    limit: int | None = None,
) -> PipelineStats:
    resolved_now = now or utc_now()
    with SessionLocal() as session:
        stats = schedule_due_sources(session, now=resolved_now, limit=limit)
        session.commit()
    return PipelineStats(scheduled=stats.created)


def run_worker_once(
    SessionLocal: sessionmaker[Session],
    *,
    worker_id: str,
    limit: int,
    now: datetime | None = None,
    client: httpx.Client | None = None,
    llm_provider: LLMProvider | None = None,
) -> PipelineStats:
    resolved_now = now or utc_now()
    with SessionLocal() as session:
        jobs = claim_fetch_jobs(session, worker_id=worker_id, limit=limit, now=resolved_now)
        session.commit()

    total = PipelineStats(claimed=len(jobs))
    for job in jobs:
        with SessionLocal() as session:
            stats = process_fetch_job(session, job.id, now=resolved_now, client=client, llm_provider=llm_provider)
            session.commit()
            total = total.add(stats)
    return total


def run_pipeline_once(
    SessionLocal: sessionmaker[Session],
    *,
    worker_id: str,
    limit: int,
    now: datetime | None = None,
    client: httpx.Client | None = None,
    llm_provider: LLMProvider | None = None,
) -> PipelineStats:
    resolved_now = now or utc_now()
    scheduled = run_scheduler_once(SessionLocal, now=resolved_now, limit=limit)
    worked = run_worker_once(
        SessionLocal,
        worker_id=worker_id,
        limit=limit,
        now=resolved_now,
        client=client,
        llm_provider=llm_provider,
    )
    return worked.add(scheduled)


def reprocess_existing_items(
    SessionLocal: sessionmaker[Session],
    *,
    channel: str | None = None,
    limit: int = 10,
    llm_provider: LLMProvider | None = None,
) -> ReprocessStats:
    settings = Settings()
    provider = llm_provider
    if provider is None and settings.llm_provider != "fake":
        provider = build_llm_provider(settings)

    processed = 0
    failed = 0
    with SessionLocal() as session:
        stmt = select(NormalizedItemRecord).order_by(NormalizedItemRecord.fetched_at.desc()).limit(limit)
        if channel:
            stmt = stmt.where(NormalizedItemRecord.channel == channel)
        items = list(session.scalars(stmt).all())

    for item in items:
        with SessionLocal() as session:
            current = session.get(NormalizedItemRecord, item.id)
            if current is None:
                continue
            source = session.get(SourceRecord, current.source_id)
            if source is None:
                failed += 1
                continue
            strategy = _ensure_active_strategy(session, current.channel)
            try:
                _upsert_model_score(session, current, source, strategy, llm_provider=provider)
            except Exception:  # noqa: BLE001 - keep historical backfill moving when one item fails.
                session.rollback()
                failed += 1
                continue
            session.commit()
            processed += 1
    return ReprocessStats(items=processed, failed=failed)


def process_fetch_job(
    session: Session,
    job_id: int,
    *,
    now: datetime | None = None,
    client: httpx.Client | None = None,
    llm_provider: LLMProvider | None = None,
) -> PipelineStats:
    resolved_now = now or utc_now()
    job = _get_job(session, job_id)
    source = _get_source(session, job.source_id)
    try:
        result = get_fetch_adapter(source.fetch_adapter).fetch(source, client=client)
    except Exception as exc:  # noqa: BLE001 - isolate one bad source from the worker batch.
        mark_job_failed(session, job.id, error_message=str(exc), now=resolved_now)
        return PipelineStats(failed=1)
    raw_result = RawStore(session).save_fetch_result(job, result, now=resolved_now)

    if result.status != "succeeded":
        mark_job_failed(session, job.id, error_message=result.error_message or "fetch failed", now=resolved_now)
        return PipelineStats(
            failed=1,
            raw_documents_inserted=raw_result.documents_inserted,
            duplicates=raw_result.duplicates,
        )

    raw_documents = list(
        session.scalars(select(RawDocumentRecord).where(RawDocumentRecord.fetch_run_id == raw_result.fetch_run_id)).all()
    )
    normalized_count = 0
    ranked_count = 0
    for raw_document in raw_documents:
        item = _normalize_raw_document(session, source, raw_document)
        if item is None:
            continue
        normalized_count += 1
        strategy = _ensure_active_strategy(session, source.channel)
        prefilter = _upsert_prefilter(session, item, strategy)
        model_score = _upsert_model_score(session, item, source, strategy, llm_provider=llm_provider)
        _upsert_ranked_item(session, item, source, strategy, prefilter, model_score, observed_at=resolved_now)
        ranked_count += 1

    clusters_created = _persist_selected_clusters(session, channel=source.channel)
    mark_job_succeeded(
        session,
        job.id,
        now=resolved_now,
        item_count=len(result.documents),
        avg_latency_ms=None,
    )
    return PipelineStats(
        succeeded=1,
        raw_documents_inserted=raw_result.documents_inserted,
        duplicates=raw_result.duplicates,
        normalized_items=normalized_count,
        ranked_items=ranked_count,
        clusters=clusters_created,
    )


def _normalize_raw_document(
    session: Session,
    source: SourceRecord,
    raw_document: RawDocumentRecord,
) -> NormalizedItemRecord | None:
    existing = session.scalar(
        select(NormalizedItemRecord)
        .where(NormalizedItemRecord.channel == source.channel)
        .where(NormalizedItemRecord.content_hash == raw_document.content_hash)
        .limit(1)
    )
    if existing is not None:
        return None

    title = raw_document.response_headers_json.get("x-intel-title") or source.name
    published_at = _parse_datetime(raw_document.response_headers_json.get("x-intel-published-at"))
    if not is_same_operational_day(published_at, raw_document.fetched_at):
        return None
    item = NormalizedItemRecord(
        channel=source.channel,
        source_id=source.id,
        raw_document_id=raw_document.id,
        title_original=title,
        title_cn=None,
        url=raw_document.url,
        canonical_url=canonicalize_url(raw_document.canonical_url),
        summary_original=raw_document.body_text,
        summary_cn=None,
        published_at=published_at,
        fetched_at=raw_document.fetched_at,
        language=source.language,
        content_hash=raw_document.content_hash,
    )
    session.add(item)
    session.flush()
    return item


def _ensure_active_strategy(session: Session, channel: str) -> StrategyVersionRecord:
    strategy = session.scalar(
        select(StrategyVersionRecord)
        .where(StrategyVersionRecord.channel == channel)
        .where(StrategyVersionRecord.status == "active")
        .limit(1)
    )
    if strategy is not None:
        return strategy

    strategy = StrategyVersionRecord(
        id=f"{channel}-default-v1",
        channel=channel,
        name=f"{channel} default strategy",
        status="active",
        prefilter_prompt_version="prefilter-v1",
        score_prompt_version="score-v1",
        rank_formula_version="rank-v1",
        thresholds_json={"selected": 72},
        model_config_json={"provider": "fake"},
        activated_at=utc_now(),
    )
    session.add(strategy)
    session.flush()
    return strategy


def _upsert_prefilter(
    session: Session,
    item: NormalizedItemRecord,
    strategy: StrategyVersionRecord,
) -> PreScreenDecision:
    existing = session.scalar(
        select(PrefilterResultRecord)
        .where(PrefilterResultRecord.item_id == item.id)
        .where(PrefilterResultRecord.strategy_version == strategy.id)
        .limit(1)
    )
    decision = PreScreenDecision(bucket="relevant", is_relevant=True, reason="规则预筛通过", signals=["has_title"])
    if existing is None:
        session.add(
            PrefilterResultRecord(
                item_id=item.id,
                strategy_version=strategy.id,
                model="rules-v1",
                bucket=decision.bucket,
                is_relevant=decision.is_relevant,
                reason=decision.reason,
                raw_json=decision.model_dump(),
            )
        )
    else:
        existing.bucket = decision.bucket
        existing.is_relevant = decision.is_relevant
        existing.reason = decision.reason
        existing.raw_json = decision.model_dump()
    session.flush()
    return decision


def _upsert_model_score(
    session: Session,
    item: NormalizedItemRecord,
    source: SourceRecord,
    strategy: StrategyVersionRecord,
    *,
    llm_provider: LLMProvider | None = None,
) -> ModelScore:
    existing = session.scalar(
        select(ModelScoreRecord)
        .where(ModelScoreRecord.item_id == item.id)
        .where(ModelScoreRecord.strategy_version == strategy.id)
        .limit(1)
    )
    provider_score = _score_item(item, source, llm_provider=llm_provider)
    if provider_score.title_cn:
        item.title_cn = provider_score.title_cn
    if provider_score.summary_cn:
        item.summary_cn = provider_score.summary_cn
    payload = {
        "item_id": item.id,
        "strategy_version": strategy.id,
        "model": str(provider_score.raw_json.get("model") or "unknown"),
        "category": provider_score.category,
        "relevance_score": provider_score.relevance_score,
        "impact_score": provider_score.impact_score,
        "novelty_score": provider_score.novelty_score,
        "actionability_score": provider_score.actionability_score,
        "credibility_score": provider_score.credibility_score,
        "seller_action_level": provider_score.seller_action_level,
        "reason": provider_score.reason,
        "raw_json": provider_score.raw_json,
    }
    if existing is None:
        session.add(ModelScoreRecord(**payload))
    else:
        for key, value in payload.items():
            if key not in {"item_id", "strategy_version"}:
                setattr(existing, key, value)
    session.flush()
    return provider_score


def _score_item(
    item: NormalizedItemRecord,
    source: SourceRecord,
    *,
    llm_provider: LLMProvider | None,
) -> ModelScore:
    if llm_provider is not None:
        return llm_provider.score_item(_model_payload(item, source))

    settings = Settings()
    if settings.llm_provider == "fake":
        return FakeLLMProvider(_fake_score(item, source)).score_item(_model_payload(item, source))

    try:
        return build_llm_provider(settings).score_item(_model_payload(item, source))
    except Exception as exc:  # noqa: BLE001 - one model failure should not stop the whole worker batch.
        fallback = _fake_score(item, source)
        fallback_raw = dict(fallback.raw_json)
        fallback_raw.update(
            {
                "fallbackReason": str(exc),
                "failedProvider": settings.llm_provider,
            }
        )
        return fallback.model_copy(update={"raw_json": fallback_raw})


def _model_payload(item: NormalizedItemRecord, source: SourceRecord) -> dict[str, object]:
    return {
        "itemId": item.id,
        "channel": item.channel,
        "source": {
            "id": source.id,
            "name": source.name,
            "tier": source.tier,
            "trustLevel": source.tier,
            "authorityWeight": source.authority_weight,
            "defaultCategories": source.default_categories,
        },
        "titleOriginal": _truncate_text(item.title_original, 300),
        "summaryOriginal": _truncate_text(item.summary_original, 4000),
        "url": item.url,
        "publishedAt": item.published_at,
    }


def _truncate_text(value: str | None, max_chars: int) -> str:
    if not value:
        return ""
    if len(value) <= max_chars:
        return value
    return f"{value[:max_chars]}…"


def _upsert_ranked_item(
    session: Session,
    item: NormalizedItemRecord,
    source: SourceRecord,
    strategy: StrategyVersionRecord,
    prefilter: PreScreenDecision,
    model_score: ModelScore,
    *,
    observed_at: datetime,
) -> RankedItemRecord:
    threshold = strategy.thresholds_json.get(model_score.category, strategy.thresholds_json.get("selected", 72))
    policy = RankPolicy(default_threshold=float(threshold), category_thresholds={model_score.category: float(threshold)})
    decision = policy.evaluate(
        RankPolicyInput(
            channel=item.channel,
            source_tier=source.tier,
            category=model_score.category,
            observed_at=observed_at,
            published_at=item.published_at,
            prefilter=prefilter,
            model_score=model_score,
            duplicate_penalty=0,
        )
    )
    ranked = session.get(RankedItemRecord, {"item_id": item.id, "strategy_version": strategy.id})
    payload = {
        "source_weight": decision.source_weight,
        "category_weight": decision.category_weight,
        "freshness_weight": decision.freshness_weight,
        "duplicate_penalty": decision.duplicate_penalty,
        "channel_impact_weight": decision.channel_impact_weight,
        "final_score": decision.final_score,
        "selected": decision.selected,
        "threshold_used": decision.threshold_used,
        "selection_reason": decision.selection_reason,
    }
    if ranked is None:
        ranked = RankedItemRecord(item_id=item.id, strategy_version=strategy.id, **payload)
        session.add(ranked)
    else:
        for key, value in payload.items():
            setattr(ranked, key, value)
    session.flush()
    return ranked


def _persist_selected_clusters(session: Session, *, channel: str) -> int:
    rows = session.execute(
        select(NormalizedItemRecord, SourceRecord, RankedItemRecord)
        .join(SourceRecord, SourceRecord.id == NormalizedItemRecord.source_id)
        .join(RankedItemRecord, RankedItemRecord.item_id == NormalizedItemRecord.id)
        .where(NormalizedItemRecord.channel == channel)
        .where(RankedItemRecord.selected.is_(True))
    ).all()
    candidates: list[ClusterCandidate] = []
    for item, source, ranked in rows:
        member_exists = session.scalar(
            select(ClusterMemberRecord.cluster_id).where(ClusterMemberRecord.item_id == item.id).limit(1)
        )
        if member_exists is not None:
            continue
        candidates.append(
            ClusterCandidate(
                item_id=item.id,
                channel=item.channel,
                source_id=item.source_id,
                source_tier=source.tier,
                source_authority_weight=source.authority_weight,
                title=item.title_cn or item.title_original,
                canonical_url=item.canonical_url,
                content_hash=item.content_hash,
                category=ranked_category(session, item.id),
                published_at=item.published_at,
                final_score=ranked.final_score,
            )
        )

    created = 0
    for draft in cluster_candidates(candidates):
        cluster = EventClusterRecord(
            channel=draft.channel,
            canonical_title=draft.canonical_title,
            main_item_id=draft.main_item_id,
            category=draft.category,
            first_seen_at=draft.first_seen_at or utc_now(),
            last_seen_at=draft.last_seen_at or utc_now(),
            member_count=draft.member_count,
            source_count=draft.source_count,
            cluster_score=draft.cluster_score,
            embedding=draft.embedding,
        )
        session.add(cluster)
        session.flush()
        for candidate in candidates:
            if candidate.item_id in draft.member_item_ids:
                session.add(
                    ClusterMemberRecord(
                        cluster_id=cluster.id,
                        item_id=candidate.item_id,
                        source_id=candidate.source_id,
                        relation_score=100 if candidate.item_id == draft.main_item_id else 85,
                        is_main=candidate.item_id == draft.main_item_id,
                    )
                )
        created += 1
    session.flush()
    return created


def ranked_category(session: Session, item_id: int) -> str:
    model_score = session.scalar(select(ModelScoreRecord).where(ModelScoreRecord.item_id == item_id).limit(1))
    if model_score is None:
        return "general"
    return model_score.category


def _fake_score(item: NormalizedItemRecord, source: SourceRecord) -> ModelScore:
    category = source.default_categories[0] if source.default_categories else "general"
    base = min(100.0, max(55.0, source.authority_weight))
    return ModelScore(
        category=category,
        relevance_score=base,
        impact_score=min(100.0, base + 2),
        novelty_score=75.0,
        actionability_score=78.0,
        credibility_score=source.authority_weight,
        summary_cn=item.summary_cn or "待 AI 处理后生成中文摘要。",
        title_cn=item.title_cn,
        reason="Fake provider 生成的结构化评分，仅用于流水线验证。",
        seller_action_level="review",
        raw_json={"provider": "fake", "model": "fake-default"},
    )


def _get_job(session: Session, job_id: int) -> FetchJobRecord:
    job = session.get(FetchJobRecord, job_id)
    if job is None:
        raise KeyError(f"Unknown fetch job: {job_id}")
    return job


def _get_source(session: Session, source_id: str) -> SourceRecord:
    source = session.get(SourceRecord, source_id)
    if source is None:
        raise KeyError(f"Unknown source: {source_id}")
    return source


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value)
