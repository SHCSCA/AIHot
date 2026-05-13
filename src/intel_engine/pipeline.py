from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from intel_engine.clustering import ClusterCandidate, cluster_candidates
from intel_engine.daily import generate_daily_digest
from intel_engine.fetchers import get_fetch_adapter
from intel_engine.llm import (
    FakeLLMProvider,
    LLMProvider,
    ModelScore,
    ScreeningProvider,
    ScreeningResult,
    build_scoring_provider,
    build_screening_provider,
)
from intel_engine.models import (
    ClusterMemberRecord,
    EventClusterRecord,
    FetchJobRecord,
    ModelScoreRecord,
    NormalizedItemRecord,
    PrefilterResultRecord,
    RankedItemRecord,
    RawDocumentRecord,
    RawScreeningResultRecord,
    SourceRecord,
    StrategyVersionRecord,
    utc_now,
)
from intel_engine.normalizer import canonicalize_url
from intel_engine.prescreen import PreScreenDecision
from intel_engine.quality import OPERATIONAL_TIMEZONE, is_within_recent_hours
from intel_engine.rank_policy import RankPolicy, RankPolicyInput
from intel_engine.raw_store import RawStore
from intel_engine.review import (
    ACCEPTED_BUCKETS,
    adjusted_selected_threshold,
    auto_review_decision,
    validate_model_score,
    validate_screening_result,
)
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
    screening_provider: ScreeningProvider | None = None,
) -> PipelineStats:
    resolved_now = now or utc_now()
    total = PipelineStats()
    for _index in range(limit):
        with SessionLocal() as session:
            jobs = claim_fetch_jobs(session, worker_id=worker_id, limit=1, now=resolved_now)
            session.commit()
        if not jobs:
            break
        job_id = jobs[0].id
        total = total.add(PipelineStats(claimed=1))
        with SessionLocal() as session:
            stats = process_fetch_job(
                session,
                job_id,
                now=resolved_now,
                client=client,
                llm_provider=llm_provider,
                screening_provider=screening_provider,
            )
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
    screening_provider: ScreeningProvider | None = None,
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
        screening_provider=screening_provider,
    )
    total = worked.add(scheduled)
    _auto_generate_recent_daily(SessionLocal, now=resolved_now)
    return total


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
        provider = build_scoring_provider(settings)

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
    screening_provider: ScreeningProvider | None = None,
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
        strategy = _ensure_active_strategy(session, source.channel)
        screening = _upsert_screening_result(
            session,
            raw_document,
            source,
            strategy,
            now=resolved_now,
            screening_provider=screening_provider,
        )
        item = _normalize_raw_document(session, source, raw_document, screening=screening)
        if item is None:
            continue
        normalized_count += 1
        prefilter = _upsert_prefilter(session, item, strategy)
        model_score = _upsert_model_score(session, item, source, strategy, llm_provider=llm_provider)
        score_validation = validate_model_score(model_score, channel=source.channel)
        if not score_validation.accepted:
            continue
        _upsert_ranked_item(
            session,
            item,
            source,
            strategy,
            prefilter,
            model_score,
            screening=screening,
            observed_at=resolved_now,
        )
        ranked_count += 1

    clusters_created = _persist_ranked_clusters(session, channel=source.channel)
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
    *,
    screening: RawScreeningResultRecord | None = None,
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
    if not is_within_recent_hours(published_at, raw_document.fetched_at):
        return None
    if screening is not None and (
        screening.screen_status != "accepted" or screening.screen_bucket not in ACCEPTED_BUCKETS
    ):
        return None
    item = NormalizedItemRecord(
        channel=source.channel,
        source_id=source.id,
        raw_document_id=raw_document.id,
        title_original=title,
        title_cn=screening.title_cn if screening is not None else None,
        url=raw_document.url,
        canonical_url=canonicalize_url(raw_document.canonical_url),
        summary_original=raw_document.body_text,
        summary_cn=screening.summary_cn if screening is not None else None,
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
        thresholds_json={"record": 70, "selected": 78 if channel == "amazon" else 80, "confidence": 80},
        model_config_json={
            "provider": Settings().llm_provider,
            "screeningModel": Settings().llm_screening_model,
            "scoringModel": Settings().llm_scoring_model,
        },
        activated_at=utc_now(),
    )
    session.add(strategy)
    session.flush()
    return strategy


def _upsert_screening_result(
    session: Session,
    raw_document: RawDocumentRecord,
    source: SourceRecord,
    strategy: StrategyVersionRecord,
    *,
    now: datetime,
    screening_provider: ScreeningProvider | None = None,
) -> RawScreeningResultRecord:
    existing = session.scalar(
        select(RawScreeningResultRecord)
        .where(RawScreeningResultRecord.raw_document_id == raw_document.id)
        .where(RawScreeningResultRecord.strategy_version == strategy.id)
        .limit(1)
    )
    result = _screen_raw_document(raw_document, source, now=now, screening_provider=screening_provider)
    published_at = _parse_datetime(raw_document.response_headers_json.get("x-intel-published-at"))
    validation = validate_screening_result(
        result,
        channel=source.channel,
        published_at=published_at,
        observed_at=raw_document.fetched_at,
        original_url=raw_document.canonical_url,
        source_url=source.url,
    )
    if not validation.accepted:
        result = result.model_copy(
            update={
                "screen_status": "rejected" if result.screen_status != "failed" else "failed",
                "screen_bucket": "invalid" if result.screen_bucket in ACCEPTED_BUCKETS else result.screen_bucket,
                "reason_code": validation.reason_code or result.reason_code,
                "reason_cn": validation.reason_cn or result.reason_cn,
            }
        )
    raw_json = dict(result.raw_json)
    provider = str(raw_json.get("provider") or "unknown")
    model = str(raw_json.get("model") or "unknown")
    payload = {
        "raw_document_id": raw_document.id,
        "strategy_version": strategy.id,
        "provider": provider,
        "model": model,
        "screen_status": result.screen_status,
        "screen_bucket": result.screen_bucket,
        "relevance_score": result.relevance_score,
        "confidence_score": result.confidence_score,
        "category": result.category,
        "title_cn": result.title_cn,
        "summary_cn": result.summary_cn,
        "tags_json": result.tags,
        "reason_code": result.reason_code,
        "reason_cn": result.reason_cn,
        "raw_json": raw_json,
    }
    if existing is None:
        existing = RawScreeningResultRecord(**payload)
        session.add(existing)
    else:
        for key, value in payload.items():
            if key not in {"raw_document_id", "strategy_version"}:
                setattr(existing, key, value)
    session.flush()
    return existing


def _screen_raw_document(
    raw_document: RawDocumentRecord,
    source: SourceRecord,
    *,
    now: datetime,
    screening_provider: ScreeningProvider | None,
) -> ScreeningResult:
    provider = screening_provider
    if provider is None:
        try:
            provider = build_screening_provider(Settings())
        except Exception as exc:  # noqa: BLE001
            return _failed_screening_result("model_failed", f"初筛模型不可用：{exc}")
    try:
        return provider.screen_item(_screening_payload(raw_document, source, now=now))
    except Exception as exc:  # noqa: BLE001 - one bad model response should not stop the batch.
        return _failed_screening_result("model_failed", f"初筛模型失败：{exc}")


def _failed_screening_result(reason_code: str, reason_cn: str) -> ScreeningResult:
    return ScreeningResult(
        screen_status="failed",
        screen_bucket="invalid",
        relevance_score=0,
        confidence_score=0,
        category="industry",
        title_cn="初筛失败",
        summary_cn="初筛模型未能生成合格摘要。",
        tags=["初筛失败", "模型异常"],
        reason_code=reason_code,
        reason_cn=reason_cn,
        raw_json={"provider": "system", "model": "screening-failure"},
    )


def _screening_payload(raw_document: RawDocumentRecord, source: SourceRecord, *, now: datetime) -> dict[str, object]:
    return {
        "rawDocumentId": raw_document.id,
        "channel": source.channel,
        "source": {
            "id": source.id,
            "name": source.name,
            "tier": source.tier,
            "authorityWeight": source.authority_weight,
            "defaultCategories": source.default_categories,
            "sourceGroup": source.source_group,
            "socialHandle": source.social_handle,
            "collectionStatus": source.collection_status,
        },
        "titleOriginal": _truncate_text(raw_document.response_headers_json.get("x-intel-title") or source.name, 300),
        "summaryOriginal": _truncate_text(raw_document.body_text, 3000),
        "url": raw_document.canonical_url,
        "publishedAt": raw_document.response_headers_json.get("x-intel-published-at"),
        "fetchedAt": raw_document.fetched_at,
        "observedAt": now,
        "rules": _channel_screening_rules(source.channel),
    }


def _channel_screening_rules(channel: str) -> dict[str, object]:
    if channel == "amazon":
        return {
            "allowedCategories": [
                "policy",
                "account_health",
                "fba_logistics",
                "ads_ppc",
                "listing_seo",
                "fees_margin",
                "product_research",
                "tools",
                "compliance_trade",
            ],
            "tagRules": "标签 2-5 个；除品牌、平台、API、产品名外必须使用中文短词；禁止 news/update/AI/Amazon 等泛标签。",
            "reasonRules": "推荐理由必须说明对 Amazon 卖家利润、风险、广告、库存、Listing 或合规动作的具体价值。",
            "accepted": [
                "平台政策、费用、广告、FBA、账号健康、合规、税务、贸易变化",
                "SP-API、Seller Central、Brand Registry、广告控制台等卖家工具变更",
                "对选品、Listing、广告、库存、利润、账号风险有明确影响",
            ],
            "rejected": [
                "泛泛运营教程",
                "工具商软文和优惠推广",
                "与 Amazon 卖家无直接关系的泛电商新闻",
                "旧政策重复解释",
            ],
        }
    return {
        "allowedCategories": ["ai_models", "ai_products", "agent_tools", "papers", "industry", "monetization"],
        "tagRules": "标签 2-5 个；除品牌、模型名、产品名、账号名外必须使用中文短词；禁止 news/update/AI/Amazon 等泛标签。",
        "reasonRules": "推荐理由必须说明为什么值得关注，关联模型能力、产品变化、开发者动作或行业影响。",
        "accepted": [
            "新模型发布、模型能力变化、开源模型、API 或价格变化",
            "AI 产品上线、功能更新、商业化变化、重要合作",
            "Agent、编程工具、开发框架、论文、技术报告、行业变化",
        ],
        "rejected": [
            "只提到 AI 但没有具体变化",
            "泛教程、列表合集、SEO 文章",
            "无来源、无发布时间、无明确事件的转述",
        ],
    }


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
        "raw_json": {
            **provider_score.raw_json,
            "confidenceScore": provider_score.confidence_score,
            "tags": provider_score.tags,
            "eventType": provider_score.event_type,
            "keyFacts": provider_score.key_facts,
            "riskFlags": provider_score.risk_flags,
        },
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
        return build_scoring_provider(settings).score_item(_model_payload(item, source))
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
            "sourceGroup": source.source_group,
            "socialHandle": source.social_handle,
            "collectionStatus": source.collection_status,
        },
        "titleOriginal": _truncate_text(item.title_original, 300),
        "summaryOriginal": _truncate_text(item.summary_original, 4000),
        "url": item.url,
        "publishedAt": item.published_at,
        "rules": _channel_scoring_rules(item.channel),
    }


def _channel_scoring_rules(channel: str) -> dict[str, object]:
    rules = _channel_screening_rules(channel)
    return {
        "allowedCategories": rules["allowedCategories"],
        "tagRules": rules["tagRules"],
        "reasonRules": rules["reasonRules"],
        "scoreRules": "五维评分均为 0-100；只输出中间评分，不允许决定 selected；推荐理由不能为空。",
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
    screening: RawScreeningResultRecord,
    observed_at: datetime,
) -> RankedItemRecord:
    base_threshold = float(strategy.thresholds_json.get(model_score.category, strategy.thresholds_json.get("selected", 80)))
    threshold = adjusted_selected_threshold(
        channel=item.channel,
        base_threshold=base_threshold,
        source_tier=source.tier,
        screen_bucket=screening.screen_bucket,
        source_count=1,
        risk_flags=model_score.risk_flags,
    )
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
    selected = decision.selected
    selection_reason = decision.selection_reason
    confidence_threshold = float(strategy.thresholds_json.get("confidence", 80))
    confidence_score = model_score.confidence_score if model_score.confidence_score is not None else screening.confidence_score
    if confidence_score < confidence_threshold:
        selected = False
        selection_reason = "低于精选置信度阈值"
    if model_score.raw_json.get("provider") != "deepseek" or model_score.raw_json.get("fallbackReason"):
        selected = False
        selection_reason = "非 DeepSeek 正式精筛结果，不进入精选"
    ranked = session.get(RankedItemRecord, {"item_id": item.id, "strategy_version": strategy.id})
    payload = {
        "source_weight": decision.source_weight,
        "category_weight": decision.category_weight,
        "freshness_weight": decision.freshness_weight,
        "duplicate_penalty": decision.duplicate_penalty,
        "channel_impact_weight": decision.channel_impact_weight,
        "final_score": decision.final_score,
        "selected": selected,
        "threshold_used": decision.threshold_used,
        "selection_reason": selection_reason,
    }
    if ranked is None:
        ranked = RankedItemRecord(item_id=item.id, strategy_version=strategy.id, **payload)
        session.add(ranked)
    else:
        for key, value in payload.items():
            setattr(ranked, key, value)
    session.flush()
    return ranked


def _persist_ranked_clusters(session: Session, *, channel: str) -> int:
    rows = session.execute(
        select(NormalizedItemRecord, SourceRecord, RankedItemRecord)
        .join(SourceRecord, SourceRecord.id == NormalizedItemRecord.source_id)
        .join(RankedItemRecord, RankedItemRecord.item_id == NormalizedItemRecord.id)
        .where(NormalizedItemRecord.channel == channel)
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
        main_item = session.get(NormalizedItemRecord, draft.main_item_id)
        main_source = session.get(SourceRecord, main_item.source_id) if main_item is not None else None
        main_screening = _screening_for_item(session, draft.main_item_id)
        main_score = _model_score_for_item(session, draft.main_item_id)
        main_ranked = _ranked_for_item(session, draft.main_item_id)
        review = auto_review_decision(
            item=main_item,
            source=main_source,
            screening=main_screening,
            score=main_score,
            ranked=main_ranked,
        )
        cluster.review_status = review.status
        cluster.review_note = review.note
        cluster.reviewed_by = "ai-reviewer"
        cluster.reviewed_at = utc_now()
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


def _screening_for_item(session: Session, item_id: int) -> RawScreeningResultRecord | None:
    item = session.get(NormalizedItemRecord, item_id)
    if item is None:
        return None
    return session.scalar(
        select(RawScreeningResultRecord)
        .where(RawScreeningResultRecord.raw_document_id == item.raw_document_id)
        .order_by(RawScreeningResultRecord.created_at.desc())
        .limit(1)
    )


def _model_score_for_item(session: Session, item_id: int) -> ModelScoreRecord | None:
    return session.scalar(select(ModelScoreRecord).where(ModelScoreRecord.item_id == item_id).limit(1))


def _ranked_for_item(session: Session, item_id: int) -> RankedItemRecord | None:
    return session.scalar(select(RankedItemRecord).where(RankedItemRecord.item_id == item_id).limit(1))


def _auto_generate_recent_daily(SessionLocal: sessionmaker[Session], *, now: datetime) -> None:
    digest_date = now.astimezone(OPERATIONAL_TIMEZONE).date()
    with SessionLocal() as session:
        channels = list(session.scalars(select(StrategyVersionRecord.channel).where(StrategyVersionRecord.status == "active")).all())
        for channel in sorted(set(channels)):
            strategy = _ensure_active_strategy(session, channel)
            generate_daily_digest(
                session,
                channel=channel,
                digest_date=digest_date,
                strategy_version=strategy.id,
                now=now,
                auto_publish=True,
            )
        session.commit()


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
        confidence_score=82,
        tags=["本地验证", "模型评分"],
        event_type="test",
        key_facts=["本地流水线验证数据"],
        risk_flags=[],
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
