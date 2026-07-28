from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx
from sqlalchemy import exists, select, text
from sqlalchemy.orm import Session, sessionmaker

from intel_engine.clustering import ClusterCandidate, cluster_candidates, same_event
from intel_engine.channel_config import get_channel_config
from intel_engine.corroboration import (
    CorroborationMember,
    CorroborationResult,
    corroborate_event,
)
from intel_engine.daily import generate_daily_digest
from intel_engine.fetchers import get_fetch_adapter
from intel_engine.llm import (
    FakeLLMProvider,
    EventAnalysisProvider,
    EventEvidenceAnalysis,
    LLMProvider,
    ModelScore,
    ScreeningProvider,
    ScreeningResult,
    build_event_analysis_provider,
    build_scoring_provider,
    build_screening_provider,
)
from intel_engine.models import (
    ClusterMemberRecord,
    EventClusterRecord,
    EventEvidenceAssessmentRecord,
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
    channel_rolling_window_hours,
    validate_model_score,
    validate_screening_result,
)
from intel_engine.scheduler import (
    claim_fetch_jobs,
    mark_job_failed,
    mark_job_succeeded,
    schedule_due_sources,
)
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
            raw_documents_inserted=self.raw_documents_inserted
            + other.raw_documents_inserted,
            duplicates=self.duplicates + other.duplicates,
            normalized_items=self.normalized_items + other.normalized_items,
            ranked_items=self.ranked_items + other.ranked_items,
            clusters=self.clusters + other.clusters,
        )


@dataclass(frozen=True)
class ReprocessStats:
    items: int = 0
    failed: int = 0


@dataclass(frozen=True)
class EvidenceBackfillStats:
    events: int = 0


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
    event_analysis_provider: EventAnalysisProvider | None = None,
) -> PipelineStats:
    resolved_now = now or utc_now()
    total = PipelineStats()
    for _index in range(limit):
        with SessionLocal() as session:
            jobs = claim_fetch_jobs(
                session, worker_id=worker_id, limit=1, now=resolved_now
            )
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
                event_analysis_provider=event_analysis_provider,
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
    event_analysis_provider: EventAnalysisProvider | None = None,
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
        event_analysis_provider=event_analysis_provider,
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
        stmt = (
            select(NormalizedItemRecord)
            .order_by(NormalizedItemRecord.fetched_at.desc())
            .limit(limit)
        )
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
                _upsert_model_score(
                    session, current, source, strategy, llm_provider=provider
                )
            except Exception:  # noqa: BLE001 - keep historical backfill moving when one item fails.
                session.rollback()
                failed += 1
                continue
            session.commit()
            processed += 1
    return ReprocessStats(items=processed, failed=failed)


def backfill_event_evidence(
    SessionLocal: sessionmaker[Session],
    *,
    channel: str | None = None,
    limit: int | None = None,
    use_ai: bool = False,
    event_analysis_provider: EventAnalysisProvider | None = None,
) -> EvidenceBackfillStats:
    processed = 0
    with SessionLocal() as session:
        channels = (
            [channel]
            if channel is not None
            else list(
                session.scalars(
                    select(EventClusterRecord.channel)
                    .distinct()
                    .order_by(EventClusterRecord.channel)
                ).all()
            )
        )
        for channel_id in channels:
            _acquire_cluster_advisory_lock(session, channel_id)
            stmt = (
                select(EventClusterRecord)
                .where(EventClusterRecord.channel == channel_id)
                .order_by(EventClusterRecord.id)
            )
            if limit is not None:
                stmt = stmt.limit(max(0, limit - processed))
            clusters = list(session.scalars(stmt).all())
            resolved_provider: EventAnalysisProvider | None = None
            provider_error: str | None = None
            if use_ai or event_analysis_provider is not None:
                resolved_provider, provider_error = _resolve_event_analysis_provider(
                    event_analysis_provider
                )
            for cluster in clusters:
                _upsert_event_evidence_assessment(
                    session,
                    cluster,
                    event_analysis_provider=resolved_provider,
                    provider_error=provider_error,
                )
                processed += 1
                if limit is not None and processed >= limit:
                    break
            if limit is not None and processed >= limit:
                break
        session.commit()
    return EvidenceBackfillStats(events=processed)


def process_fetch_job(
    session: Session,
    job_id: int,
    *,
    now: datetime | None = None,
    client: httpx.Client | None = None,
    llm_provider: LLMProvider | None = None,
    screening_provider: ScreeningProvider | None = None,
    event_analysis_provider: EventAnalysisProvider | None = None,
) -> PipelineStats:
    resolved_now = now or utc_now()
    job = _get_job(session, job_id)
    source = _get_source(session, job.source_id)
    try:
        result = get_fetch_adapter(source.fetch_adapter, now=resolved_now).fetch(
            source, client=client
        )
        raw_result = RawStore(session).save_fetch_result(job, result, now=resolved_now)

        if result.status != "succeeded":
            mark_job_failed(
                session,
                job.id,
                error_message=result.error_message or "fetch failed",
                now=resolved_now,
            )
            return PipelineStats(
                failed=1,
                raw_documents_inserted=raw_result.documents_inserted,
                duplicates=raw_result.duplicates,
            )

        raw_documents = list(
            session.scalars(
                select(RawDocumentRecord).where(
                    RawDocumentRecord.fetch_run_id == raw_result.fetch_run_id
                )
            ).all()
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
            item = _normalize_raw_document(
                session, source, raw_document, screening=screening
            )
            if item is None:
                continue
            normalized_count += 1
            prefilter = _upsert_prefilter(session, item, strategy)
            model_score = _upsert_model_score(
                session, item, source, strategy, llm_provider=llm_provider
            )
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

        clusters_created = _persist_ranked_clusters(
            session,
            channel=source.channel,
            event_analysis_provider=event_analysis_provider,
        )
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
    except Exception as exc:  # noqa: BLE001 - keep one bad source/model result from stopping the worker.
        session.rollback()
        mark_job_failed(session, job_id, error_message=str(exc), now=resolved_now)
        return PipelineStats(failed=1)


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
    published_at = _effective_published_at(source, raw_document, screening)
    if not is_within_recent_hours(
        published_at,
        raw_document.fetched_at,
        hours=channel_rolling_window_hours(source.channel),
    ):
        return None
    if screening is not None and (
        screening.screen_status != "accepted"
        or screening.screen_bucket not in ACCEPTED_BUCKETS
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
        thresholds_json={
            "record": 70,
            "selected": _default_selected_threshold(channel),
            "confidence": 80,
        },
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


def _default_selected_threshold(channel: str) -> float:
    try:
        configured = get_channel_config(channel).scoring.get("selected_threshold")
    except (FileNotFoundError, KeyError, ValueError):
        configured = None
    if isinstance(configured, (int, float)):
        return float(configured)
    return 80.0


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
    result = _screen_raw_document(
        raw_document, source, now=now, screening_provider=screening_provider
    )
    result = _apply_screening_guardrails(result, raw_document, source)
    published_at = _effective_published_at(source, raw_document, result)
    published_was_inferred = (
        source.channel == "amazon"
        and raw_document.response_headers_json.get("x-intel-published-at") is None
        and published_at is not None
    )
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
                "screen_status": "rejected"
                if result.screen_status != "failed"
                else "failed",
                "screen_bucket": "invalid"
                if result.screen_bucket in ACCEPTED_BUCKETS
                else result.screen_bucket,
                "reason_code": validation.reason_code or result.reason_code,
                "reason_cn": validation.reason_cn or result.reason_cn,
            }
        )
    elif published_was_inferred:
        result = result.model_copy(
            update={
                "raw_json": {
                    **dict(result.raw_json),
                    "publishedAtInferred": "fetched_at",
                }
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


AMAZON_LOW_INFORMATION_REASON_CODES = {
    "low_info",
    "low_info_generic",
    "low_information_value",
    "tutorial_rejection",
    "evergreen_tutorial",
}

AMAZON_GUARDRAIL_REASON_CODES = AMAZON_LOW_INFORMATION_REASON_CODES | {
    "schema_invalid",
    "low_confidence",
}

AMAZON_SCREENING_CATEGORIES = {
    "policy",
    "account_health",
    "fba_logistics",
    "ads_ppc",
    "listing_seo",
    "fees_margin",
    "product_research",
    "tools",
    "compliance_trade",
}

AMAZON_SELLER_CONTEXT_TERMS = (
    "amazon seller",
    "seller central",
    "selling partner",
    "sp-api",
    "fba",
    "fulfillment by amazon",
    "amazon ads",
    "ppc",
)

AMAZON_OPERATIONAL_TERMS = (
    "account health",
    "advertising",
    "api",
    "campaign",
    "coupon",
    "deprecation",
    "fee",
    "fulfillment center",
    "inbound",
    "inventory",
    "listing",
    "lost",
    "missing",
    "placement",
    "pricing",
    "prime day",
    "reimbursement",
    "release notes",
    "review",
    "return",
    "seller central",
    "storage",
)


def _apply_screening_guardrails(
    result: ScreeningResult,
    raw_document: RawDocumentRecord,
    source: SourceRecord,
) -> ScreeningResult:
    if source.channel != "amazon":
        return result
    if (
        result.screen_status == "accepted"
        and result.relevance_score >= 70
        and result.confidence_score >= 70
    ):
        return result
    reason_code = result.reason_code.lower()
    if (
        reason_code not in AMAZON_GUARDRAIL_REASON_CODES
        and result.screen_status != "accepted"
    ):
        return result

    text = " ".join(
        [
            str(raw_document.response_headers_json.get("x-intel-title") or ""),
            raw_document.body_text or "",
            raw_document.canonical_url or "",
        ]
    ).lower()
    has_seller_context = any(term in text for term in AMAZON_SELLER_CONTEXT_TERMS)
    has_operational_signal = any(term in text for term in AMAZON_OPERATIONAL_TERMS)
    if not (has_seller_context and has_operational_signal):
        return result

    tags = [tag for tag in result.tags if tag]
    for tag in ("FBA", "库存赔付", "卖家运营"):
        if tag not in tags:
            tags.append(tag)
        if len(tags) >= 3:
            break

    raw_json = {
        **dict(result.raw_json),
        "guardrail": "amazon_seller_ops_signal",
        "original_screen_status": result.screen_status,
        "original_screen_bucket": result.screen_bucket,
        "original_reason_code": result.reason_code,
    }
    return result.model_copy(
        update={
            "screen_status": "accepted",
            "screen_bucket": "related",
            "category": result.category
            if result.category in AMAZON_SCREENING_CATEGORIES
            else _amazon_guardrail_category(text),
            "relevance_score": max(result.relevance_score, 72),
            "confidence_score": max(result.confidence_score, 72),
            "tags": tags[:5],
            "reason_code": "seller_ops_signal",
            "reason_cn": "内容包含 Amazon 卖家运营信号，涉及 FBA、库存、赔付、广告、费用或工具等可执行事项，按卖家价值规则修正为入库。",
            "raw_json": raw_json,
        }
    )


def _effective_published_at(
    source: SourceRecord,
    raw_document: RawDocumentRecord,
    screening: ScreeningResult | RawScreeningResultRecord | None = None,
) -> datetime | None:
    published_at = _parse_datetime(
        raw_document.response_headers_json.get("x-intel-published-at")
    )
    if published_at is not None:
        return published_at
    if _can_infer_amazon_published_at(source, raw_document, screening):
        return raw_document.fetched_at
    return None


def _can_infer_amazon_published_at(
    source: SourceRecord,
    raw_document: RawDocumentRecord,
    screening: ScreeningResult | RawScreeningResultRecord | None,
) -> bool:
    if source.channel != "amazon":
        return False
    if screening is None:
        return False
    if getattr(screening, "screen_status", None) != "accepted":
        return False
    if getattr(screening, "screen_bucket", None) not in ACCEPTED_BUCKETS:
        return False
    if getattr(screening, "category", None) not in AMAZON_SCREENING_CATEGORIES:
        return False
    text = _amazon_signal_text(raw_document)
    return _has_amazon_seller_ops_signal(text)


def _amazon_signal_text(raw_document: RawDocumentRecord) -> str:
    return " ".join(
        [
            str(raw_document.response_headers_json.get("x-intel-title") or ""),
            raw_document.body_text or "",
            raw_document.canonical_url or "",
        ]
    ).lower()


def _has_amazon_seller_ops_signal(text: str) -> bool:
    has_seller_context = any(term in text for term in AMAZON_SELLER_CONTEXT_TERMS)
    has_operational_signal = any(term in text for term in AMAZON_OPERATIONAL_TERMS)
    return has_seller_context and has_operational_signal


def _amazon_guardrail_category(text: str) -> str:
    if any(
        term in text
        for term in (
            "fba",
            "fulfillment",
            "inventory",
            "inbound",
            "storage",
            "placement",
        )
    ):
        return "fba_logistics"
    if any(
        term in text for term in ("advertising", "campaign", "ppc", "amazon ads", "dsp")
    ):
        return "ads_ppc"
    if any(
        term in text
        for term in ("fee", "reimbursement", "margin", "payment", "commission")
    ):
        return "fees_margin"
    if any(
        term in text
        for term in ("account health", "suspension", "appeal", "brand registry")
    ):
        return "account_health"
    if any(term in text for term in ("listing", "review", "keyword", "a+", "search")):
        return "listing_seo"
    if any(term in text for term in ("sp-api", "api", "seller central", "tool")):
        return "tools"
    return "policy"


def _screening_payload(
    raw_document: RawDocumentRecord, source: SourceRecord, *, now: datetime
) -> dict[str, object]:
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
        "titleOriginal": _truncate_text(
            raw_document.response_headers_json.get("x-intel-title") or source.name, 300
        ),
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
        "allowedCategories": [
            "ai_models",
            "ai_products",
            "agent_tools",
            "papers",
            "industry",
            "monetization",
        ],
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
    decision = PreScreenDecision(
        bucket="relevant",
        is_relevant=True,
        reason="规则预筛通过",
        signals=["has_title"],
    )
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
        return FakeLLMProvider(_fake_score(item, source)).score_item(
            _model_payload(item, source)
        )

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


def _model_payload(
    item: NormalizedItemRecord, source: SourceRecord
) -> dict[str, object]:
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
    base_threshold = float(
        strategy.thresholds_json.get(
            model_score.category, strategy.thresholds_json.get("selected", 80)
        )
    )
    threshold = adjusted_selected_threshold(
        channel=item.channel,
        base_threshold=base_threshold,
        source_tier=source.tier,
        screen_bucket=screening.screen_bucket,
        source_count=1,
        risk_flags=model_score.risk_flags,
    )
    policy = RankPolicy(
        default_threshold=float(threshold),
        category_thresholds={model_score.category: float(threshold)},
    )
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
    confidence_score = (
        model_score.confidence_score
        if model_score.confidence_score is not None
        else screening.confidence_score
    )
    if confidence_score < confidence_threshold:
        selected = False
        selection_reason = "低于精选置信度阈值"
    if model_score.raw_json.get("provider") != "deepseek" or model_score.raw_json.get(
        "fallbackReason"
    ):
        selected = False
        selection_reason = "非 DeepSeek 正式精筛结果，不进入精选"
    ranked = session.get(
        RankedItemRecord, {"item_id": item.id, "strategy_version": strategy.id}
    )
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
        ranked = RankedItemRecord(
            item_id=item.id, strategy_version=strategy.id, **payload
        )
        session.add(ranked)
    else:
        for key, value in payload.items():
            setattr(ranked, key, value)
    session.flush()
    return ranked


def _persist_ranked_clusters(
    session: Session,
    *,
    channel: str,
    event_analysis_provider: EventAnalysisProvider | None = None,
) -> int:
    _acquire_cluster_advisory_lock(session, channel)
    rows = session.execute(
        select(NormalizedItemRecord, SourceRecord, RankedItemRecord)
        .join(SourceRecord, SourceRecord.id == NormalizedItemRecord.source_id)
        .join(RankedItemRecord, RankedItemRecord.item_id == NormalizedItemRecord.id)
        .where(NormalizedItemRecord.channel == channel)
        .where(~exists().where(ClusterMemberRecord.item_id == NormalizedItemRecord.id))
    ).all()
    candidates: list[ClusterCandidate] = []
    for item, source, ranked in rows:
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

    if not candidates:
        return 0

    cluster_stmt = select(EventClusterRecord).where(
        EventClusterRecord.channel == channel
    )
    published_times = [
        candidate.published_at
        for candidate in candidates
        if candidate.published_at is not None
    ]
    if published_times:
        cluster_window = timedelta(hours=max(72, channel_rolling_window_hours(channel)))
        cluster_stmt = cluster_stmt.where(
            EventClusterRecord.last_seen_at >= min(published_times) - cluster_window,
            EventClusterRecord.first_seen_at <= max(published_times) + cluster_window,
        )
    existing_clusters = list(session.scalars(cluster_stmt).all())
    existing_candidates = {
        cluster.id: candidate
        for cluster in existing_clusters
        if (candidate := _cluster_main_candidate(session, cluster)) is not None
    }
    resolved_provider, provider_error = _resolve_event_analysis_provider(
        event_analysis_provider
    )

    created = 0
    for draft in cluster_candidates(candidates):
        draft_members = [
            candidate
            for candidate in candidates
            if candidate.item_id in draft.member_item_ids
        ]
        draft_main = next(
            candidate
            for candidate in draft_members
            if candidate.item_id == draft.main_item_id
        )
        cluster = next(
            (
                existing
                for existing in existing_clusters
                if (existing_candidate := existing_candidates.get(existing.id))
                is not None
                and _same_cluster_event(existing_candidate, draft_main)
            ),
            None,
        )
        if cluster is None:
            cluster = EventClusterRecord(
                channel=draft.channel,
                canonical_title=draft.canonical_title,
                main_item_id=draft.main_item_id,
                category=draft.category,
                first_seen_at=draft.first_seen_at or utc_now(),
                last_seen_at=draft.last_seen_at or utc_now(),
                member_count=0,
                source_count=0,
                cluster_score=draft.cluster_score,
                embedding=draft.embedding,
            )
            session.add(cluster)
            session.flush()
            existing_clusters.append(cluster)
            created += 1

        for candidate in draft_members:
            if (
                session.get(
                    ClusterMemberRecord,
                    {"cluster_id": cluster.id, "item_id": candidate.item_id},
                )
                is None
            ):
                session.add(
                    ClusterMemberRecord(
                        cluster_id=cluster.id,
                        item_id=candidate.item_id,
                        source_id=candidate.source_id,
                        relation_score=100
                        if candidate.item_id == draft.main_item_id
                        else 85,
                        is_main=candidate.item_id == draft.main_item_id,
                    )
                )
        session.flush()
        _refresh_cluster(session, cluster)
        _upsert_event_evidence_assessment(
            session,
            cluster,
            event_analysis_provider=resolved_provider,
            provider_error=provider_error,
        )
        refreshed_candidate = _cluster_main_candidate(session, cluster)
        if refreshed_candidate is not None:
            existing_candidates[cluster.id] = refreshed_candidate
    session.flush()
    return created


def _acquire_cluster_advisory_lock(session: Session, channel: str) -> None:
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"intel-engine:event-clustering:{channel}"},
    )


def _same_cluster_event(first: ClusterCandidate, second: ClusterCandidate) -> bool:
    if first.canonical_url and first.canonical_url == second.canonical_url:
        return True
    if first.content_hash and first.content_hash == second.content_hash:
        return True
    if first.published_at is None or second.published_at is None:
        return False
    window_hours = max(72, channel_rolling_window_hours(first.channel))
    if abs(first.published_at - second.published_at) > timedelta(hours=window_hours):
        return False
    return same_event(first, second)


def _cluster_main_candidate(
    session: Session,
    cluster: EventClusterRecord,
) -> ClusterCandidate | None:
    if cluster.main_item_id is None:
        return None
    item = session.get(NormalizedItemRecord, cluster.main_item_id)
    source = session.get(SourceRecord, item.source_id) if item is not None else None
    ranked = _ranked_for_item(session, item.id) if item is not None else None
    if item is None or source is None or ranked is None:
        return None
    return ClusterCandidate(
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


def _refresh_cluster(session: Session, cluster: EventClusterRecord) -> None:
    member_records = list(
        session.scalars(
            select(ClusterMemberRecord).where(
                ClusterMemberRecord.cluster_id == cluster.id
            )
        ).all()
    )
    resolved_members: list[
        tuple[
            ClusterMemberRecord,
            NormalizedItemRecord,
            SourceRecord,
            RankedItemRecord,
        ]
    ] = []
    for member in member_records:
        item = session.get(NormalizedItemRecord, member.item_id)
        source = session.get(SourceRecord, member.source_id)
        ranked = _ranked_for_item(session, member.item_id)
        if item is not None and source is not None and ranked is not None:
            resolved_members.append((member, item, source, ranked))
    if not resolved_members:
        return

    tier_priority = {"T1": 4, "T1.5": 3, "T2": 2, "T3": 1}
    _main_member, main_item, main_source, main_ranked = max(
        resolved_members,
        key=lambda row: (
            tier_priority.get(row[2].tier, 0),
            row[2].authority_weight,
            row[3].final_score,
            row[1].published_at.timestamp() if row[1].published_at else 0,
        ),
    )
    for member, *_rest in resolved_members:
        member.is_main = member.item_id == main_item.id
        if member.is_main:
            member.relation_score = 100

    published_times = [
        item.published_at
        for _member, item, _source, _ranked in resolved_members
        if item.published_at is not None
    ]
    cluster.main_item_id = main_item.id
    cluster.canonical_title = main_item.title_cn or main_item.title_original
    cluster.category = ranked_category(session, main_item.id)
    cluster.member_count = len(resolved_members)
    cluster.source_count = len(
        {source.id for _member, _item, source, _ranked in resolved_members}
    )
    cluster.cluster_score = max(
        ranked.final_score for _member, _item, _source, ranked in resolved_members
    )
    if published_times:
        cluster.first_seen_at = min(published_times)
        cluster.last_seen_at = max(published_times)

    if cluster.reviewed_by in {None, "ai-reviewer"}:
        review = auto_review_decision(
            item=main_item,
            source=main_source,
            screening=_screening_for_item(session, main_item.id),
            score=_model_score_for_item(session, main_item.id),
            ranked=main_ranked,
        )
        cluster.review_status = review.status
        cluster.review_note = review.note
        cluster.reviewed_by = "ai-reviewer"
        cluster.reviewed_at = utc_now()
    session.flush()


def _resolve_event_analysis_provider(
    provider: EventAnalysisProvider | None,
) -> tuple[EventAnalysisProvider | None, str | None]:
    if provider is not None:
        return provider, None
    settings = Settings()
    if settings.llm_provider == "fake":
        return None, None
    try:
        return build_event_analysis_provider(settings), None
    except Exception as exc:  # noqa: BLE001 - deterministic corroboration remains available.
        return None, str(exc)


def _upsert_event_evidence_assessment(
    session: Session,
    cluster: EventClusterRecord,
    *,
    event_analysis_provider: EventAnalysisProvider | None,
    provider_error: str | None,
) -> EventEvidenceAssessmentRecord:
    corroboration_members: list[CorroborationMember] = []
    payload_members: list[dict[str, object]] = []
    member_records = list(
        session.scalars(
            select(ClusterMemberRecord)
            .where(ClusterMemberRecord.cluster_id == cluster.id)
            .order_by(
                ClusterMemberRecord.is_main.desc(),
                ClusterMemberRecord.item_id,
            )
        ).all()
    )
    for member in member_records:
        item = session.get(NormalizedItemRecord, member.item_id)
        source = session.get(SourceRecord, member.source_id)
        score = _model_score_for_item(session, member.item_id)
        if item is None or source is None:
            continue
        raw_json = score.raw_json if score is not None else {}
        key_facts = _string_values(raw_json.get("keyFacts"))
        risk_flags = _string_values(raw_json.get("riskFlags"))
        publisher_key = (
            source.publisher_key
            if source.publisher_key and source.publisher_key != "unknown"
            else f"source:{source.id}"
        )
        corroboration_members.append(
            CorroborationMember(
                publisher_key=publisher_key,
                source_tier=source.tier,
                title=item.title_cn or item.title_original,
                source_id=source.id,
                summary=item.summary_cn or item.summary_original,
                key_facts=key_facts,
                risk_flags=risk_flags,
            )
        )
        payload_members.append(
            {
                "itemId": item.id,
                "sourceId": source.id,
                "publisherKey": publisher_key,
                "sourceTier": source.tier,
                "title": item.title_cn or item.title_original,
                "summary": _truncate_text(
                    item.summary_cn or item.summary_original,
                    1800,
                ),
                "keyFacts": list(key_facts),
                "riskFlags": list(risk_flags),
            }
        )

    fallback = corroborate_event(corroboration_members)
    ai_analysis: EventEvidenceAnalysis | None = None
    ai_error = provider_error
    if event_analysis_provider is not None and fallback.independent_source_count >= 2:
        try:
            ai_analysis = event_analysis_provider.analyze_event(
                {
                    "eventId": cluster.id,
                    "channel": cluster.channel,
                    "title": cluster.canonical_title,
                    "members": payload_members,
                    "rules": {
                        "minimumIndependentPublishers": 2,
                        "publisherIdentityField": "publisherKey",
                    },
                }
            )
        except Exception as exc:  # noqa: BLE001 - deterministic fallback is mandatory.
            ai_error = str(exc)

    combined = _combine_event_evidence(fallback, ai_analysis)
    raw_json: dict[str, object] = {
        "fallbackStatus": fallback.verification_status,
        "fallbackSummary": fallback.summary,
    }
    provider = "rules"
    model = "corroboration-v1"
    if ai_analysis is not None:
        raw_json.update(ai_analysis.raw_json)
        raw_json["aiConfidenceScore"] = ai_analysis.confidence_score
        raw_json["aiVerificationStatus"] = ai_analysis.verification_status
        raw_json["aiSupportedFacts"] = list(ai_analysis.supported_facts)
        raw_json["aiConflictingClaims"] = list(ai_analysis.conflicting_claims)
        raw_json["aiSummary"] = ai_analysis.summary
        raw_json["aiDisagreesWithRules"] = (
            ai_analysis.verification_status != fallback.verification_status
        )
        provider = str(ai_analysis.raw_json.get("provider") or "ai")
        model = str(ai_analysis.raw_json.get("model") or "event-evidence-v1")
    if ai_error:
        raw_json["fallbackReason"] = ai_error

    record = session.get(EventEvidenceAssessmentRecord, cluster.id)
    payload = {
        "provider": provider,
        "model": model,
        "verification_status": combined.verification_status,
        "independent_source_count": combined.independent_source_count,
        "authoritative_source_count": combined.authoritative_source_count,
        "evidence_score": combined.evidence_score,
        "supported_facts_json": list(combined.supported_facts),
        "supported_claims_json": _supported_claim_payload(combined),
        "conflicting_claims_json": list(combined.conflicting_claims),
        "summary": combined.summary,
        "raw_json": raw_json,
        "analyzed_at": utc_now(),
    }
    if record is None:
        record = EventEvidenceAssessmentRecord(event_id=cluster.id, **payload)
        session.add(record)
    else:
        for key, value in payload.items():
            setattr(record, key, value)
    session.flush()
    return record


def _combine_event_evidence(
    fallback: CorroborationResult,
    ai_analysis: EventEvidenceAnalysis | None,
) -> CorroborationResult:
    if ai_analysis is None:
        return fallback

    conclusions_disagree = (
        ai_analysis.verification_status != fallback.verification_status
    )
    status = fallback.verification_status
    summary = fallback.summary
    if conclusions_disagree and fallback.verification_status != "conflicted":
        status = "insufficient"
        summary = "确定性证据与 AI 分析结论不一致，暂不晋级，需要人工复核。"
        evidence_score = min(fallback.evidence_score, 39.0)
    elif conclusions_disagree:
        evidence_score = fallback.evidence_score
    else:
        evidence_score = round(
            fallback.evidence_score * 0.7 + ai_analysis.confidence_score * 0.3,
            2,
        )
    if status == "single_source":
        evidence_score = min(evidence_score, 49.0)
    elif status == "insufficient":
        evidence_score = min(evidence_score, 39.0)
    elif status == "conflicted":
        evidence_score = min(evidence_score, 44.0)
    return CorroborationResult(
        verification_status=status,
        independent_source_count=fallback.independent_source_count,
        authoritative_source_count=fallback.authoritative_source_count,
        evidence_score=evidence_score,
        supported_claims=fallback.supported_claims,
        supported_facts=fallback.supported_facts,
        conflicting_claims=fallback.conflicting_claims,
        summary=summary,
    )


def _supported_claim_payload(
    evidence: CorroborationResult,
) -> list[dict[str, object]]:
    return [
        {
            "claim": supported.claim,
            "publisherKeys": list(supported.publisher_keys),
            "sourceIds": list(supported.source_ids),
        }
        for supported in evidence.supported_claims
    ]


def _string_values(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _screening_for_item(
    session: Session, item_id: int
) -> RawScreeningResultRecord | None:
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
    return session.scalar(
        select(ModelScoreRecord).where(ModelScoreRecord.item_id == item_id).limit(1)
    )


def _ranked_for_item(session: Session, item_id: int) -> RankedItemRecord | None:
    return session.scalar(
        select(RankedItemRecord).where(RankedItemRecord.item_id == item_id).limit(1)
    )


def _auto_generate_recent_daily(
    SessionLocal: sessionmaker[Session], *, now: datetime
) -> None:
    digest_date = now.astimezone(OPERATIONAL_TIMEZONE).date()
    with SessionLocal() as session:
        channels = list(
            session.scalars(
                select(StrategyVersionRecord.channel).where(
                    StrategyVersionRecord.status == "active"
                )
            ).all()
        )
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
    model_score = session.scalar(
        select(ModelScoreRecord).where(ModelScoreRecord.item_id == item_id).limit(1)
    )
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
