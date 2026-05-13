from __future__ import annotations

import base64
import json
from datetime import date as date_type
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, exists, func, or_, select

from intel_engine.auth import require_admin
from intel_engine.channel_config import load_channel_configs
from intel_engine.daily import generate_daily_digest
from intel_engine.evaluation import activate_strategy_version, run_evaluation
from intel_engine.models import (
    ClusterMemberRecord,
    DailyDigestRecord,
    EvaluationRunRecord,
    EventClusterRecord,
    FeedbackEventRecord,
    FetchJobRecord,
    ModelScoreRecord,
    NormalizedItemRecord,
    PipelineRunRecord,
    RankedItemRecord,
    RawScreeningResultRecord,
    SourceRecord,
    SourceStateRecord,
    StrategyVersionRecord,
)
from intel_engine.pipeline import run_pipeline_once
from intel_engine.quality import is_publishable_original_url, operational_day_bounds_utc
from intel_engine.review import PUBLIC_WINDOW_LABEL, ROLLING_WINDOW_HOURS, public_cluster_ready
from intel_engine.rss import build_events_feed
from intel_engine.sources import SourceRegistry, SourceUpsert
from intel_engine.storage import ItemRepository


router = APIRouter()


class SourceWrite(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    channel: str
    source_type: str = Field(alias="sourceType")
    tier: str
    name: str
    url: str
    language: str
    region: str
    marketplace: str | None = None
    authority_weight: float = Field(alias="authorityWeight")
    noise_level: float = Field(alias="noiseLevel")
    fetch_adapter: str = Field(alias="fetchAdapter")
    parser_type: str = Field(alias="parserType")
    default_categories: list[str] = Field(alias="defaultCategories")
    fetch_interval_minutes: int = Field(alias="fetchIntervalMinutes")
    enabled: bool = True
    visibility: str = "public"
    notes: str | None = None


class SourcePatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    enabled: bool | None = None
    visibility: str | None = None
    authority_weight: float | None = Field(default=None, alias="authorityWeight")
    noise_level: float | None = Field(default=None, alias="noiseLevel")
    fetch_interval_minutes: int | None = Field(default=None, alias="fetchIntervalMinutes")
    notes: str | None = None


class StrategyVersionWrite(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    channel: str
    name: str
    status: str = "draft"
    prefilter_prompt_version: str = Field(alias="prefilterPromptVersion")
    score_prompt_version: str = Field(alias="scorePromptVersion")
    rank_formula_version: str = Field(alias="rankFormulaVersion")
    thresholds_json: dict[str, object] = Field(default_factory=dict, alias="thresholds")
    model_config_json: dict[str, object] = Field(default_factory=dict, alias="modelConfig")


class FeedbackEventWrite(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    item_id: int | None = Field(default=None, alias="itemId")
    cluster_id: int | None = Field(default=None, alias="clusterId")
    channel: str
    feedback_type: str = Field(alias="feedbackType")
    reason: str = ""
    actor: str = "system"


class EvaluationRunWrite(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    channel: str
    strategy_version: str = Field(alias="strategyVersion")
    name: str
    request_json: dict[str, object] = Field(default_factory=dict, alias="request")


class EventReviewWrite(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    review_status: str = Field(alias="reviewStatus")
    review_note: str | None = Field(default=None, alias="reviewNote")
    actor: str = "operator"


class DailyDigestGenerateWrite(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    channel: str
    digest_date: date_type = Field(alias="date")
    strategy_version: str = Field(alias="strategyVersion")


class ActorWrite(BaseModel):
    actor: str = "operator"


class PipelineRunWrite(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    worker_id: str = Field(default="manual-worker", alias="workerId")
    limit: int = Field(default=10, ge=1, le=100)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "intel-engine"}


@router.get("/api/public/channels")
def channels() -> dict[str, list[dict[str, object]]]:
    configs = load_channel_configs()
    return {
        "channels": [
            {
                "id": config.id,
                "name": config.name,
                "description": config.description,
                "categories": [
                    {"id": category.id, "label": category.label}
                    for category in config.categories
                ],
                "sourceCount": len([source for source in config.sources if source.enabled]),
            }
            for config in configs
        ]
    }


@router.get("/api/public/items")
def items(
    request: Request,
    channel: str | None = None,
    mode: str = Query(default="all", pattern="^(selected|all)$"),
    category: str | None = None,
    take: int = Query(default=20, ge=1, le=100),
) -> dict[str, object]:
    repository = ItemRepository(request.app.state.db_engine)
    records = repository.list_items(channel=channel, category=category, take=take, mode=mode)
    return {
        "count": len(records),
        "hasNext": False,
        "nextCursor": None,
        "items": [
            {
                "id": str(record.id),
                "channel": record.channel,
                "title": record.normalized_title,
                "url": record.url,
                "source": record.source_name,
                "publishedAt": record.published_at.isoformat(),
                "summary": record.summary,
                "category": record.category,
                "finalScore": record.final_score,
                "entryReason": record.entry_reason,
                "suggestedAction": record.suggested_action,
                "sellerActionLevel": record.seller_action_level,
            }
            for record in records
        ],
    }


@router.get("/api/v1/public/events")
def public_events(
    request: Request,
    channel: str | None = None,
    mode: str = Query(default="selected", pattern="^(selected|all)$"),
    category: str | None = None,
    event_date: date_type | None = Query(default=None, alias="date"),
    window: int | None = Query(default=None, ge=1, le=720),
    q: str | None = None,
    take: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = select(EventClusterRecord).where(EventClusterRecord.review_status == "approved")
        if channel:
            stmt = stmt.where(EventClusterRecord.channel == channel)
        if category:
            stmt = stmt.where(EventClusterRecord.category == category)
        if event_date is not None:
            start, end = operational_day_bounds_utc(event_date)
            stmt = stmt.where(EventClusterRecord.last_seen_at >= start).where(EventClusterRecord.last_seen_at <= end)
        else:
            hours = window or ROLLING_WINDOW_HOURS
            stmt = stmt.where(EventClusterRecord.last_seen_at >= datetime.now(timezone.utc) - timedelta(hours=hours))
        if q:
            stmt = stmt.where(EventClusterRecord.canonical_title.contains(q))
        if mode == "selected":
            stmt = stmt.where(
                exists()
                .where(RankedItemRecord.item_id == EventClusterRecord.main_item_id)
                .where(RankedItemRecord.selected.is_(True))
            )
        if cursor:
            cursor_value = _decode_cursor(cursor)
            stmt = stmt.where(
                or_(
                    EventClusterRecord.last_seen_at < cursor_value["sortAt"],
                    and_(
                        EventClusterRecord.last_seen_at == cursor_value["sortAt"],
                        EventClusterRecord.id < cursor_value["id"],
                    ),
                )
            )
        stmt = stmt.order_by(EventClusterRecord.last_seen_at.desc(), EventClusterRecord.id.desc()).limit(take + 1)
        page = _page_rows(list(session.scalars(stmt).all()), take, lambda cluster: cluster.last_seen_at, lambda cluster: cluster.id)
        clusters = [cluster for cluster in page["rows"] if _is_public_cluster_ready(session, cluster, require_selected=mode == "selected")]
        events = [_event_payload(session, cluster) for cluster in clusters]

    return {
        "count": len(events),
        "hasNext": page["hasNext"],
        "nextCursor": page["nextCursor"],
        "windowLabel": PUBLIC_WINDOW_LABEL,
        "events": events,
    }


@router.get("/api/v1/public/events/{event_id}")
def public_event_detail(request: Request, event_id: int) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        cluster = session.get(EventClusterRecord, event_id)
        if cluster is None:
            raise HTTPException(status_code=404, detail="event not found")
        if not _is_public_cluster_ready(session, cluster, require_selected=False):
            raise HTTPException(status_code=404, detail="event not found")

        members = []
        member_records = session.scalars(
            select(ClusterMemberRecord)
            .where(ClusterMemberRecord.cluster_id == event_id)
            .order_by(ClusterMemberRecord.is_main.desc(), ClusterMemberRecord.item_id)
        ).all()
        for member in member_records:
            item = session.get(NormalizedItemRecord, member.item_id)
            source = session.get(SourceRecord, member.source_id)
            if item is None:
                continue
            members.append(
                {
                    "id": str(item.id),
                    "title": item.title_cn or item.title_original,
                    "url": _safe_item_url(item, source),
                    "sourceId": item.source_id,
                    "sourceName": source.name if source else item.source_id,
                    "publishedAt": _iso(item.published_at),
                    "summary": _processed_summary(item),
                    "isMain": member.is_main,
                    "relationScore": member.relation_score,
                }
            )

        return {"event": _event_payload(session, cluster), "members": members}


@router.get("/api/v1/public/daily")
def public_daily(
    request: Request,
    channel: str,
    digest_date: date_type | None = Query(default=None, alias="date"),
) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = select(DailyDigestRecord).where(DailyDigestRecord.channel == channel).where(DailyDigestRecord.published.is_(True))
        if digest_date is not None:
            stmt = stmt.where(DailyDigestRecord.digest_date == digest_date)
        stmt = stmt.order_by(DailyDigestRecord.digest_date.desc(), DailyDigestRecord.generated_at.desc()).limit(1)
        digest = session.scalar(stmt)
        if digest is None:
            return {"daily": None}
        return {
            "daily": {
                "id": str(digest.id),
                "channel": digest.channel,
                "date": digest.digest_date.isoformat(),
                "generatedAt": digest.generated_at.isoformat(),
                "title": digest.title,
                "sections": digest.sections_json,
                "windowLabel": PUBLIC_WINDOW_LABEL,
            }
        }


@router.get("/feed/{channel}/events.xml")
def events_feed(request: Request, channel: str) -> Response:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        clusters = session.scalars(
            select(EventClusterRecord)
            .where(EventClusterRecord.channel == channel)
            .where(EventClusterRecord.review_status == "approved")
            .where(
                exists()
                .where(RankedItemRecord.item_id == EventClusterRecord.main_item_id)
                .where(RankedItemRecord.selected.is_(True))
            )
            .order_by(EventClusterRecord.last_seen_at.desc(), EventClusterRecord.cluster_score.desc())
            .limit(50)
        ).all()
        events = []
        for cluster in clusters:
            if not _is_public_cluster_ready(session, cluster, require_selected=True):
                continue
            payload = _event_payload(session, cluster)
            main_item = payload.get("mainItem") or {}
            events.append(
                {
                    "id": payload["id"],
                    "title": payload["title"],
                    "url": main_item.get("url") or "",
                    "summary": main_item.get("summary", ""),
                    "publishedAt": payload["lastSeenAt"],
                }
            )
    xml = build_events_feed(events, title=f"{channel.upper()} 情报事件", link=f"/feed/{channel}/events.xml", description="精选事件")
    return Response(content=xml, media_type="application/rss+xml")


@router.get("/feed/{channel}/daily.xml")
def daily_feed(request: Request, channel: str) -> Response:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        digests = session.scalars(
            select(DailyDigestRecord)
            .where(DailyDigestRecord.channel == channel)
            .where(DailyDigestRecord.published.is_(True))
            .order_by(DailyDigestRecord.digest_date.desc())
            .limit(30)
        ).all()
        events = [
            {
                "id": str(digest.id),
                "title": digest.title,
                "url": f"/api/v1/public/daily?channel={channel}&date={digest.digest_date.isoformat()}",
                "summary": _digest_summary(digest),
                "publishedAt": digest.generated_at.isoformat(),
            }
            for digest in digests
        ]
    xml = build_events_feed(events, title=f"{channel.upper()} 日报", link=f"/feed/{channel}/daily.xml", description="每日精选情报")
    return Response(content=xml, media_type="application/rss+xml")


ADMIN_DEPENDENCIES = [Depends(require_admin)]


@router.get("/api/v1/internal/dashboard", dependencies=ADMIN_DEPENDENCIES)
def internal_dashboard(request: Request) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        metrics = {
            "sourceCount": _count(session, select(func.count()).select_from(SourceRecord)),
            "healthWarningCount": _count(
                session,
                select(func.count())
                .select_from(SourceStateRecord)
                .where((SourceStateRecord.error_streak > 0) | (SourceStateRecord.health_score < 80)),
            ),
            "pendingJobCount": _count(
                session, select(func.count()).select_from(FetchJobRecord).where(FetchJobRecord.status == "pending")
            ),
            "failedJobCount": _count(
                session,
                select(func.count())
                .select_from(FetchJobRecord)
                .where(FetchJobRecord.status.in_(["failed", "dead", "pending"]))
                .where(FetchJobRecord.last_error.is_not(None)),
            ),
            "pendingReviewEventCount": _count(
                session,
                select(func.count()).select_from(EventClusterRecord).where(EventClusterRecord.review_status == "pending"),
            ),
            "publishedDailyCount": _count(
                session, select(func.count()).select_from(DailyDigestRecord).where(DailyDigestRecord.published.is_(True))
            ),
        }
        failed_jobs = session.scalars(
            select(FetchJobRecord)
            .where(FetchJobRecord.last_error.is_not(None))
            .order_by(FetchJobRecord.updated_at.desc(), FetchJobRecord.id.desc())
            .limit(5)
        ).all()
        pending_events = session.scalars(
            select(EventClusterRecord)
            .where(EventClusterRecord.review_status == "pending")
            .order_by(EventClusterRecord.last_seen_at.desc())
            .limit(5)
        ).all()
        pipeline_runs = session.scalars(select(PipelineRunRecord).order_by(PipelineRunRecord.started_at.desc()).limit(5)).all()
        return {
            "metrics": metrics,
            "recentFailedJobs": [_job_payload(job) for job in failed_jobs],
            "pendingReviewEvents": [_internal_event_payload(session, event) for event in pending_events],
            "recentPipelineRuns": [_pipeline_run_payload(run) for run in pipeline_runs],
        }


@router.get("/api/v1/internal/sources", dependencies=ADMIN_DEPENDENCIES)
def internal_sources(request: Request, channel: str | None = None) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        registry = SourceRegistry(session)
        return {"sources": [_source_payload(source) for source in registry.list_sources(channel=channel)]}


@router.post("/api/v1/internal/sources", dependencies=ADMIN_DEPENDENCIES)
def internal_create_source(request: Request, payload: SourceWrite) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        registry = SourceRegistry(session)
        result = registry.upsert_source(_source_upsert(payload))
        source = registry.get_source(result.source_id)
        session.commit()
        return {"source": _source_payload(source), "created": result.created}


@router.patch("/api/v1/internal/sources/{source_id}", dependencies=ADMIN_DEPENDENCIES)
def internal_patch_source(request: Request, source_id: str, payload: SourcePatch) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        source = session.get(SourceRecord, source_id)
        if source is None:
            raise HTTPException(status_code=404, detail="source not found")
        updates = payload.model_dump(exclude_unset=True)
        for field_name, value in updates.items():
            setattr(source, field_name, value)
        session.commit()
        session.refresh(source)
        return {"source": _source_payload(source)}


@router.get("/api/v1/internal/source-states", dependencies=ADMIN_DEPENDENCIES)
def internal_source_states(request: Request, channel: str | None = None) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = select(SourceStateRecord, SourceRecord).join(SourceRecord, SourceRecord.id == SourceStateRecord.source_id)
        if channel:
            stmt = stmt.where(SourceRecord.channel == channel)
        stmt = stmt.order_by(SourceRecord.channel, SourceRecord.id)
        states = [_source_state_payload(state, source) for state, source in session.execute(stmt).all()]
        return {"sourceStates": states}


@router.get("/api/v1/internal/jobs", dependencies=ADMIN_DEPENDENCIES)
def internal_jobs(
    request: Request,
    status: str | None = None,
    take: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = select(FetchJobRecord)
        if status:
            stmt = stmt.where(FetchJobRecord.status == status)
        stmt = _apply_cursor(stmt, FetchJobRecord.created_at, FetchJobRecord.id, cursor)
        stmt = stmt.order_by(FetchJobRecord.created_at.desc(), FetchJobRecord.id.desc()).limit(take + 1)
        page = _page_rows(list(session.scalars(stmt).all()), take, lambda job: job.created_at, lambda job: job.id)
        jobs = [_job_payload(job) for job in page["rows"]]
        return {"count": len(jobs), "hasNext": page["hasNext"], "nextCursor": page["nextCursor"], "jobs": jobs}


@router.post("/api/v1/internal/jobs/{job_id}/retry", dependencies=ADMIN_DEPENDENCIES)
def internal_retry_job(request: Request, job_id: int) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        job = session.get(FetchJobRecord, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        job.status = "pending"
        job.run_after = datetime.now(timezone.utc)
        job.locked_at = None
        job.locked_by = None
        job.attempt_count = 0
        job.last_error = None
        session.commit()
        session.refresh(job)
        return {"job": _job_payload(job)}


@router.get("/api/v1/internal/strategy-versions", dependencies=ADMIN_DEPENDENCIES)
def internal_strategy_versions(request: Request, channel: str | None = None) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = select(StrategyVersionRecord).order_by(StrategyVersionRecord.created_at.desc())
        if channel:
            stmt = stmt.where(StrategyVersionRecord.channel == channel)
        return {"strategyVersions": [_strategy_payload(strategy) for strategy in session.scalars(stmt).all()]}


@router.post("/api/v1/internal/strategy-versions", dependencies=ADMIN_DEPENDENCIES)
def internal_create_strategy_version(request: Request, payload: StrategyVersionWrite) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        strategy = StrategyVersionRecord(**payload.model_dump())
        session.add(strategy)
        session.commit()
        session.refresh(strategy)
        return {"strategyVersion": _strategy_payload(strategy)}


@router.post("/api/v1/internal/strategy-versions/{strategy_id}/activate", dependencies=ADMIN_DEPENDENCIES)
def internal_activate_strategy_version(request: Request, strategy_id: str) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        try:
            strategy = activate_strategy_version(session, strategy_id, now=datetime.now(timezone.utc))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        session.commit()
        session.refresh(strategy)
        return {"strategyVersion": _strategy_payload(strategy)}


@router.post("/api/v1/internal/feedback-events", dependencies=ADMIN_DEPENDENCIES)
def internal_create_feedback_event(request: Request, payload: FeedbackEventWrite) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        event = FeedbackEventRecord(**payload.model_dump())
        session.add(event)
        session.commit()
        session.refresh(event)
        return {"feedbackEvent": _feedback_payload(event)}


@router.get("/api/v1/internal/feedback-events", dependencies=ADMIN_DEPENDENCIES)
def internal_feedback_events(
    request: Request,
    channel: str | None = None,
    feedback_type: str | None = Query(default=None, alias="feedbackType"),
    cluster_id: int | None = Query(default=None, alias="clusterId"),
    take: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = select(FeedbackEventRecord)
        if channel:
            stmt = stmt.where(FeedbackEventRecord.channel == channel)
        if feedback_type:
            stmt = stmt.where(FeedbackEventRecord.feedback_type == feedback_type)
        if cluster_id is not None:
            stmt = stmt.where(FeedbackEventRecord.cluster_id == cluster_id)
        stmt = _apply_cursor(stmt, FeedbackEventRecord.created_at, FeedbackEventRecord.id, cursor)
        stmt = stmt.order_by(FeedbackEventRecord.created_at.desc(), FeedbackEventRecord.id.desc()).limit(take + 1)
        page = _page_rows(list(session.scalars(stmt).all()), take, lambda event: event.created_at, lambda event: event.id)
        events = [_feedback_payload(event) for event in page["rows"]]
        return {"count": len(events), "hasNext": page["hasNext"], "nextCursor": page["nextCursor"], "feedbackEvents": events}


@router.post("/api/v1/internal/evaluation-runs", dependencies=ADMIN_DEPENDENCIES)
def internal_create_evaluation_run(request: Request, payload: EvaluationRunWrite) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        run = EvaluationRunRecord(**payload.model_dump(), status="pending", metrics_json={})
        session.add(run)
        session.commit()
        session.refresh(run)
        return {"evaluationRun": _evaluation_run_payload(run)}


@router.get("/api/v1/internal/evaluation-runs", dependencies=ADMIN_DEPENDENCIES)
def internal_evaluation_runs(
    request: Request,
    channel: str | None = None,
    take: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = select(EvaluationRunRecord)
        if channel:
            stmt = stmt.where(EvaluationRunRecord.channel == channel)
        stmt = _apply_cursor(stmt, EvaluationRunRecord.created_at, EvaluationRunRecord.id, cursor)
        stmt = stmt.order_by(EvaluationRunRecord.created_at.desc(), EvaluationRunRecord.id.desc()).limit(take + 1)
        page = _page_rows(list(session.scalars(stmt).all()), take, lambda run: run.created_at, lambda run: run.id)
        runs = [_evaluation_run_payload(run) for run in page["rows"]]
        return {"count": len(runs), "hasNext": page["hasNext"], "nextCursor": page["nextCursor"], "evaluationRuns": runs}


@router.get("/api/v1/internal/evaluation-runs/{run_id}", dependencies=ADMIN_DEPENDENCIES)
def internal_evaluation_run_detail(request: Request, run_id: int) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        run = session.get(EvaluationRunRecord, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="evaluation run not found")
        return {"evaluationRun": _evaluation_run_payload(run)}


@router.post("/api/v1/internal/evaluation-runs/{run_id}/run", dependencies=ADMIN_DEPENDENCIES)
def internal_run_evaluation(request: Request, run_id: int) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        try:
            run = run_evaluation(session, run_id, now=datetime.now(timezone.utc))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        session.commit()
        session.refresh(run)
        return {"evaluationRun": _evaluation_run_payload(run)}


@router.get("/api/v1/internal/events", dependencies=ADMIN_DEPENDENCIES)
def internal_events(
    request: Request,
    channel: str | None = None,
    review_status: str | None = Query(default=None, alias="reviewStatus"),
    category: str | None = None,
    q: str | None = None,
    take: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = select(EventClusterRecord)
        if channel:
            stmt = stmt.where(EventClusterRecord.channel == channel)
        if review_status:
            stmt = stmt.where(EventClusterRecord.review_status == review_status)
        if category:
            stmt = stmt.where(EventClusterRecord.category == category)
        if q:
            stmt = stmt.where(EventClusterRecord.canonical_title.contains(q))
        stmt = _apply_cursor(stmt, EventClusterRecord.last_seen_at, EventClusterRecord.id, cursor)
        stmt = stmt.order_by(EventClusterRecord.last_seen_at.desc(), EventClusterRecord.id.desc()).limit(take + 1)
        page = _page_rows(list(session.scalars(stmt).all()), take, lambda event: event.last_seen_at, lambda event: event.id)
        events = [_internal_event_payload(session, event) for event in page["rows"]]
        return {"count": len(events), "hasNext": page["hasNext"], "nextCursor": page["nextCursor"], "events": events}


@router.get("/api/v1/internal/events/{event_id}", dependencies=ADMIN_DEPENDENCIES)
def internal_event_detail(request: Request, event_id: int) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        cluster = session.get(EventClusterRecord, event_id)
        if cluster is None:
            raise HTTPException(status_code=404, detail="event not found")
        return {
            "event": _internal_event_payload(session, cluster),
            "members": _cluster_member_payloads(session, event_id),
        }


@router.patch("/api/v1/internal/events/{event_id}/review", dependencies=ADMIN_DEPENDENCIES)
def internal_review_event(request: Request, event_id: int, payload: EventReviewWrite) -> dict[str, object]:
    if payload.review_status not in {"pending", "approved", "rejected"}:
        raise HTTPException(status_code=422, detail="invalid review status")
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        cluster = session.get(EventClusterRecord, event_id)
        if cluster is None:
            raise HTTPException(status_code=404, detail="event not found")
        cluster.review_status = payload.review_status
        cluster.review_note = payload.review_note
        cluster.reviewed_by = payload.actor
        cluster.reviewed_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(cluster)
        return {"event": _internal_event_payload(session, cluster)}


@router.get("/api/v1/internal/daily-digests", dependencies=ADMIN_DEPENDENCIES)
def internal_daily_digests(
    request: Request,
    channel: str | None = None,
    digest_date: date_type | None = Query(default=None, alias="date"),
    take: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = select(DailyDigestRecord)
        if channel:
            stmt = stmt.where(DailyDigestRecord.channel == channel)
        if digest_date is not None:
            stmt = stmt.where(DailyDigestRecord.digest_date == digest_date)
        stmt = _apply_cursor(stmt, DailyDigestRecord.generated_at, DailyDigestRecord.id, cursor)
        stmt = stmt.order_by(DailyDigestRecord.generated_at.desc(), DailyDigestRecord.id.desc()).limit(take + 1)
        page = _page_rows(list(session.scalars(stmt).all()), take, lambda digest: digest.generated_at, lambda digest: digest.id)
        digests = [_daily_digest_payload(digest) for digest in page["rows"]]
        return {"count": len(digests), "hasNext": page["hasNext"], "nextCursor": page["nextCursor"], "dailyDigests": digests}


@router.post("/api/v1/internal/daily-digests/generate", dependencies=ADMIN_DEPENDENCIES)
def internal_generate_daily_digest(request: Request, payload: DailyDigestGenerateWrite) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        result = generate_daily_digest(
            session,
            channel=payload.channel,
            digest_date=payload.digest_date,
            strategy_version=payload.strategy_version,
            auto_publish=False,
        )
        if result.digest_id is None:
            session.commit()
            return {"dailyDigest": None, "created": False, "eventCount": 0}
        digest = session.get(DailyDigestRecord, result.digest_id)
        session.commit()
        session.refresh(digest)
        return {
            "dailyDigest": _daily_digest_payload(digest),
            "created": result.created,
            "eventCount": result.event_count,
        }


@router.post("/api/v1/internal/daily-digests/{digest_id}/publish", dependencies=ADMIN_DEPENDENCIES)
def internal_publish_daily_digest(request: Request, digest_id: int, payload: ActorWrite) -> dict[str, object]:
    return _set_daily_digest_published(request, digest_id, published=True, actor=payload.actor)


@router.post("/api/v1/internal/daily-digests/{digest_id}/unpublish", dependencies=ADMIN_DEPENDENCIES)
def internal_unpublish_daily_digest(request: Request, digest_id: int, payload: ActorWrite) -> dict[str, object]:
    return _set_daily_digest_published(request, digest_id, published=False, actor=payload.actor)


@router.get("/api/v1/internal/pipeline-runs", dependencies=ADMIN_DEPENDENCIES)
def internal_pipeline_runs(
    request: Request,
    take: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = _apply_cursor(select(PipelineRunRecord), PipelineRunRecord.started_at, PipelineRunRecord.id, cursor)
        stmt = stmt.order_by(PipelineRunRecord.started_at.desc(), PipelineRunRecord.id.desc()).limit(take + 1)
        page = _page_rows(list(session.scalars(stmt).all()), take, lambda run: run.started_at, lambda run: run.id)
        runs = [_pipeline_run_payload(run) for run in page["rows"]]
        return {"count": len(runs), "hasNext": page["hasNext"], "nextCursor": page["nextCursor"], "pipelineRuns": runs}


@router.post("/api/v1/internal/pipeline-runs", dependencies=ADMIN_DEPENDENCIES)
def internal_create_pipeline_run(request: Request, payload: PipelineRunWrite) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    started_at = datetime.now(timezone.utc)
    with SessionLocal() as session:
        run = PipelineRunRecord(
            worker_id=payload.worker_id,
            limit=payload.limit,
            status="running",
            started_at=started_at,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id

    try:
        stats = run_pipeline_once(SessionLocal, worker_id=payload.worker_id, limit=payload.limit, now=started_at)
        status = "failed" if stats.failed else "succeeded"
        error_message = "部分信源抓取失败" if stats.failed else None
    except Exception as exc:  # noqa: BLE001 - record manual pipeline failures for operators.
        stats = None
        status = "failed"
        error_message = str(exc)

    with SessionLocal() as session:
        run = session.get(PipelineRunRecord, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="pipeline run not found")
        run.status = status
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = error_message
        if stats is not None:
            run.scheduled = stats.scheduled
            run.claimed = stats.claimed
            run.succeeded = stats.succeeded
            run.failed = stats.failed
            run.raw_documents_inserted = stats.raw_documents_inserted
            run.normalized_items = stats.normalized_items
            run.ranked_items = stats.ranked_items
            run.clusters = stats.clusters
        session.commit()
        session.refresh(run)
        return {"pipelineRun": _pipeline_run_payload(run)}


def _production_sessionmaker(request: Request):
    SessionLocal = getattr(request.app.state, "production_sessionmaker", None)
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="production database is not configured")
    return SessionLocal


def _page_rows(rows, take: int, sort_at, row_id) -> dict[str, object]:
    visible = rows[:take]
    has_next = len(rows) > take
    next_cursor = None
    if has_next and visible:
        last = visible[-1]
        next_cursor = _encode_cursor(sort_at(last), row_id(last))
    return {"rows": visible, "hasNext": has_next, "nextCursor": next_cursor}


def _apply_cursor(stmt, sort_field, id_field, cursor: str | None):
    if not cursor:
        return stmt
    cursor_value = _decode_cursor(cursor)
    return stmt.where(
        or_(
            sort_field < cursor_value["sortAt"],
            and_(
                sort_field == cursor_value["sortAt"],
                id_field < cursor_value["id"],
            ),
        )
    )


def _encode_cursor(sort_at: datetime, row_id: int) -> str:
    payload = {"sortAt": sort_at.isoformat(), "id": row_id}
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("ascii")


def _decode_cursor(value: str) -> dict[str, object]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8"))
        sort_at = datetime.fromisoformat(str(payload["sortAt"]))
        row_id = int(payload["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="invalid cursor") from exc
    if sort_at.tzinfo is None:
        sort_at = sort_at.replace(tzinfo=timezone.utc)
    return {"sortAt": sort_at, "id": row_id}


def _source_upsert(payload: SourceWrite) -> SourceUpsert:
    return SourceUpsert(**payload.model_dump())


def _source_payload(source: SourceRecord) -> dict[str, object]:
    return {
        "id": source.id,
        "channel": source.channel,
        "sourceType": source.source_type,
        "tier": source.tier,
        "name": source.name,
        "url": source.url,
        "language": source.language,
        "region": source.region,
        "marketplace": source.marketplace,
        "authorityWeight": source.authority_weight,
        "noiseLevel": source.noise_level,
        "fetchAdapter": source.fetch_adapter,
        "parserType": source.parser_type,
        "defaultCategories": source.default_categories,
        "fetchIntervalMinutes": source.fetch_interval_minutes,
        "enabled": source.enabled,
        "visibility": source.visibility,
        "notes": source.notes,
        "createdAt": _iso(source.created_at),
        "updatedAt": _iso(source.updated_at),
    }


def _source_state_payload(state: SourceStateRecord, source: SourceRecord) -> dict[str, object]:
    return {
        "sourceId": state.source_id,
        "channel": source.channel,
        "sourceName": source.name,
        "enabled": source.enabled,
        "lastSuccessAt": _iso(state.last_success_at),
        "lastErrorAt": _iso(state.last_error_at),
        "errorStreak": state.error_streak,
        "nextFetchAt": _iso(state.next_fetch_at),
        "backoffUntil": _iso(state.backoff_until),
        "avgLatencyMs": state.avg_latency_ms,
        "itemsPerRun": state.items_per_run,
        "duplicateRatio": state.duplicate_ratio,
        "noiseRatio": state.noise_ratio,
        "healthScore": state.health_score,
        "updatedAt": _iso(state.updated_at),
    }


def _job_payload(job: FetchJobRecord) -> dict[str, object]:
    return {
        "id": str(job.id),
        "sourceId": job.source_id,
        "status": job.status,
        "priority": job.priority,
        "runAfter": _iso(job.run_after),
        "lockedAt": _iso(job.locked_at),
        "lockedBy": job.locked_by,
        "attemptCount": job.attempt_count,
        "lastError": job.last_error,
        "createdAt": _iso(job.created_at),
        "updatedAt": _iso(job.updated_at),
    }


def _strategy_payload(strategy: StrategyVersionRecord) -> dict[str, object]:
    return {
        "id": strategy.id,
        "channel": strategy.channel,
        "name": strategy.name,
        "status": strategy.status,
        "prefilterPromptVersion": strategy.prefilter_prompt_version,
        "scorePromptVersion": strategy.score_prompt_version,
        "rankFormulaVersion": strategy.rank_formula_version,
        "thresholds": strategy.thresholds_json,
        "modelConfig": strategy.model_config_json,
        "createdAt": _iso(strategy.created_at),
        "activatedAt": _iso(strategy.activated_at),
        "retiredAt": _iso(strategy.retired_at),
    }


def _feedback_payload(event: FeedbackEventRecord) -> dict[str, object]:
    return {
        "id": str(event.id),
        "itemId": str(event.item_id) if event.item_id is not None else None,
        "clusterId": str(event.cluster_id) if event.cluster_id is not None else None,
        "channel": event.channel,
        "feedbackType": event.feedback_type,
        "reason": event.reason,
        "actor": event.actor,
        "createdAt": _iso(event.created_at),
    }


def _evaluation_run_payload(run: EvaluationRunRecord) -> dict[str, object]:
    return {
        "id": str(run.id),
        "channel": run.channel,
        "strategyVersion": run.strategy_version,
        "name": run.name,
        "status": run.status,
        "request": run.request_json,
        "metrics": _evaluation_metrics_payload(run.metrics_json),
        "createdAt": _iso(run.created_at),
        "completedAt": _iso(run.completed_at),
    }


def _daily_digest_payload(digest: DailyDigestRecord) -> dict[str, object]:
    return {
        "id": str(digest.id),
        "channel": digest.channel,
        "date": digest.digest_date.isoformat(),
        "generatedAt": _iso(digest.generated_at),
        "strategyVersion": digest.strategy_version,
        "title": digest.title,
        "sections": digest.sections_json,
        "published": digest.published,
        "publishedBy": digest.published_by,
        "publishedAt": _iso(digest.published_at),
        "createdAt": _iso(digest.created_at),
    }


def _pipeline_run_payload(run: PipelineRunRecord) -> dict[str, object]:
    return {
        "id": str(run.id),
        "workerId": run.worker_id,
        "limit": run.limit,
        "status": run.status,
        "scheduled": run.scheduled,
        "claimed": run.claimed,
        "succeeded": run.succeeded,
        "failed": run.failed,
        "rawDocumentsInserted": run.raw_documents_inserted,
        "normalizedItems": run.normalized_items,
        "rankedItems": run.ranked_items,
        "clusters": run.clusters,
        "errorMessage": run.error_message,
        "startedAt": _iso(run.started_at),
        "finishedAt": _iso(run.finished_at),
    }


def _digest_summary(digest: DailyDigestRecord) -> str:
    highlights = digest.sections_json.get("highlights", [])
    if not isinstance(highlights, list) or not highlights:
        return ""
    titles = [str(item.get("title", "")) for item in highlights if isinstance(item, dict)]
    return "；".join(title for title in titles if title)


def _event_payload(session, cluster: EventClusterRecord) -> dict[str, object]:
    main_item = session.get(NormalizedItemRecord, cluster.main_item_id) if cluster.main_item_id is not None else None
    source = session.get(SourceRecord, main_item.source_id) if main_item is not None else None
    score = _model_score_for_item(session, main_item.id) if main_item is not None else None
    raw_json = score.raw_json if score is not None else {}
    return {
        "id": str(cluster.id),
        "channel": cluster.channel,
        "title": _processed_event_title(cluster, main_item),
        "summary": _processed_summary(main_item),
        "category": score.category if score is not None else cluster.category,
        "score": cluster.cluster_score,
        "entryReason": score.reason if score is not None and score.reason else "待 AI 处理后生成推荐理由。",
        "sellerActionLevel": score.seller_action_level if score is not None else None,
        "confidenceScore": raw_json.get("confidenceScore"),
        "tags": _list_json(raw_json.get("tags")),
        "eventType": raw_json.get("eventType"),
        "keyFacts": _list_json(raw_json.get("keyFacts")),
        "windowLabel": PUBLIC_WINDOW_LABEL,
        "sourceCount": cluster.source_count,
        "memberCount": cluster.member_count,
        "firstSeenAt": _iso(cluster.first_seen_at),
        "lastSeenAt": _iso(cluster.last_seen_at),
        "mainItem": _main_item_payload(main_item, source),
    }


def _internal_event_payload(session, cluster: EventClusterRecord) -> dict[str, object]:
    payload = _event_payload(session, cluster)
    payload.update(
        {
            "reviewStatus": cluster.review_status,
            "reviewNote": cluster.review_note,
            "reviewedBy": cluster.reviewed_by,
            "reviewedAt": _iso(cluster.reviewed_at),
        }
    )
    main_item = session.get(NormalizedItemRecord, cluster.main_item_id) if cluster.main_item_id is not None else None
    ranked = _ranked_item_for_item(session, main_item.id) if main_item is not None else None
    score = _model_score_for_item(session, main_item.id) if main_item is not None else None
    screening = _screening_for_item(session, main_item.id) if main_item is not None else None
    payload["rank"] = _ranked_payload(ranked)
    payload["modelScore"] = _model_score_payload(score)
    payload["screenStatus"] = screening.screen_status if screening is not None else None
    payload["screenBucket"] = screening.screen_bucket if screening is not None else None
    payload["screenReasonCode"] = screening.reason_code if screening is not None else None
    payload["screenReason"] = screening.reason_cn if screening is not None else None
    payload["riskFlags"] = _list_json(score.raw_json.get("riskFlags")) if score is not None else []
    return payload


def _cluster_member_payloads(session, event_id: int) -> list[dict[str, object]]:
    member_records = session.scalars(
        select(ClusterMemberRecord)
        .where(ClusterMemberRecord.cluster_id == event_id)
        .order_by(ClusterMemberRecord.is_main.desc(), ClusterMemberRecord.item_id)
    ).all()
    members = []
    for member in member_records:
        item = session.get(NormalizedItemRecord, member.item_id)
        source = session.get(SourceRecord, member.source_id)
        if item is None:
            continue
        ranked = _ranked_item_for_item(session, item.id)
        score = _model_score_for_item(session, item.id)
        members.append(
            {
                "id": str(item.id),
                "title": item.title_cn or item.title_original,
                "url": _safe_item_url(item, source),
                "sourceId": item.source_id,
                "sourceName": source.name if source else item.source_id,
                "publishedAt": _iso(item.published_at),
                "summary": _processed_summary(item),
                "isMain": member.is_main,
                "relationScore": member.relation_score,
                "rank": _ranked_payload(ranked),
                "modelScore": _model_score_payload(score),
            }
        )
    return members


def _main_item_payload(item: NormalizedItemRecord | None, source: SourceRecord | None) -> dict[str, object] | None:
    if item is None:
        return None
    return {
        "id": str(item.id),
        "title": item.title_cn or item.title_original,
        "url": _safe_item_url(item, source),
        "sourceId": item.source_id,
        "sourceName": source.name if source else item.source_id,
        "publishedAt": _iso(item.published_at),
        "summary": _processed_summary(item),
    }


def _safe_item_url(item: NormalizedItemRecord, source: SourceRecord | None) -> str | None:
    if source is None:
        return item.canonical_url
    if not is_publishable_original_url(item.canonical_url, source.url):
        return None
    return item.canonical_url


def _processed_event_title(cluster: EventClusterRecord, item: NormalizedItemRecord | None) -> str:
    if item is not None and item.title_cn:
        return item.title_cn
    return cluster.canonical_title


def _processed_summary(item: NormalizedItemRecord | None) -> str:
    if item is not None and item.summary_cn:
        return item.summary_cn
    return "待 AI 处理后生成中文摘要。"


def _ranked_item_for_item(session, item_id: int) -> RankedItemRecord | None:
    return session.scalar(select(RankedItemRecord).where(RankedItemRecord.item_id == item_id).limit(1))


def _model_score_for_item(session, item_id: int) -> ModelScoreRecord | None:
    return session.scalar(select(ModelScoreRecord).where(ModelScoreRecord.item_id == item_id).limit(1))


def _screening_for_item(session, item_id: int) -> RawScreeningResultRecord | None:
    item = session.get(NormalizedItemRecord, item_id)
    if item is None:
        return None
    return session.scalar(
        select(RawScreeningResultRecord)
        .where(RawScreeningResultRecord.raw_document_id == item.raw_document_id)
        .order_by(RawScreeningResultRecord.created_at.desc())
        .limit(1)
    )


def _is_public_cluster_ready(session, cluster: EventClusterRecord, *, require_selected: bool) -> bool:
    main_item = session.get(NormalizedItemRecord, cluster.main_item_id) if cluster.main_item_id is not None else None
    source = session.get(SourceRecord, main_item.source_id) if main_item is not None else None
    screening = _screening_for_item(session, main_item.id) if main_item is not None else None
    score = _model_score_for_item(session, main_item.id) if main_item is not None else None
    ranked = _ranked_item_for_item(session, main_item.id) if main_item is not None else None
    return public_cluster_ready(
        cluster=cluster,
        item=main_item,
        source=source,
        screening=screening,
        score=score,
        ranked=ranked,
        require_selected=require_selected,
    )


def _ranked_payload(ranked: RankedItemRecord | None) -> dict[str, object] | None:
    if ranked is None:
        return None
    return {
        "strategyVersion": ranked.strategy_version,
        "finalScore": ranked.final_score,
        "selected": ranked.selected,
        "thresholdUsed": ranked.threshold_used,
        "selectionReason": ranked.selection_reason,
    }


def _model_score_payload(score: ModelScoreRecord | None) -> dict[str, object] | None:
    if score is None:
        return None
    raw_json = score.raw_json or {}
    return {
        "model": score.model,
        "category": score.category,
        "relevanceScore": score.relevance_score,
        "impactScore": score.impact_score,
        "noveltyScore": score.novelty_score,
        "actionabilityScore": score.actionability_score,
        "credibilityScore": score.credibility_score,
        "sellerActionLevel": score.seller_action_level,
        "reason": score.reason,
        "confidenceScore": raw_json.get("confidenceScore"),
        "tags": _list_json(raw_json.get("tags")),
        "eventType": raw_json.get("eventType"),
        "keyFacts": _list_json(raw_json.get("keyFacts")),
        "riskFlags": _list_json(raw_json.get("riskFlags")),
    }


def _list_json(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _evaluation_metrics_payload(values: dict[str, object]) -> dict[str, object]:
    return {
        "labels": {
            "selectedEventCount": "精选事件数",
            "falsePositiveCount": "误选反馈数",
            "falseNegativeCount": "漏选反馈数",
            "feedbackCount": "反馈总数",
            "categoryDistribution": "类别分布",
            "sourceContribution": "来源贡献",
        },
        "values": values,
    }


def _set_daily_digest_published(request: Request, digest_id: int, *, published: bool, actor: str) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        digest = session.get(DailyDigestRecord, digest_id)
        if digest is None:
            raise HTTPException(status_code=404, detail="daily digest not found")
        digest.published = published
        digest.published_by = actor if published else None
        digest.published_at = datetime.now(timezone.utc) if published else None
        session.commit()
        session.refresh(digest)
        return {"dailyDigest": _daily_digest_payload(digest)}


def _count(session, stmt) -> int:
    return int(session.scalar(stmt) or 0)


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()
