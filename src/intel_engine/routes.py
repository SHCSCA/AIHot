from __future__ import annotations

import base64
import json
from datetime import date as date_type
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, delete, exists, func, or_, select

from intel_engine.auth import (
    audit_log,
    clear_session_cookie,
    create_session,
    create_user,
    current_principal,
    principal_payload,
    Principal,
    replace_user_roles,
    require_permission,
    revoke_session,
    set_session_cookie,
    verify_password,
)
from intel_engine.channel_config import load_channel_configs
from intel_engine.daily import generate_daily_digest
from intel_engine.evaluation import activate_strategy_version, run_evaluation
from intel_engine.fetchers import get_fetch_adapter
from intel_engine.models import (
    ClusterMemberRecord,
    DailyDigestRecord,
    EvaluationRunRecord,
    EventClusterRecord,
    FeedbackEventRecord,
    FetchJobRecord,
    FetchRunRecord,
    ModelScoreRecord,
    NormalizedItemRecord,
    PipelineRunRecord,
    RankedItemRecord,
    RawDocumentRecord,
    RawScreeningResultRecord,
    SourceRecord,
    SourceStateRecord,
    AuditLogRecord,
    PermissionRecord,
    RolePermissionRecord,
    RoleRecord,
    SessionRecord,
    StrategyVersionRecord,
    UserPreferenceRecord,
    UserRecord,
    UserRoleRecord,
)
from intel_engine.normalizer import canonicalize_url
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
    source_group: str = Field(default="media", alias="sourceGroup")
    contributor_no: str | None = Field(default=None, alias="contributorNo")
    social_handle: str | None = Field(default=None, alias="socialHandle")
    collection_status: str = Field(default="collectable", alias="collectionStatus")
    free_access: bool = Field(default=True, alias="freeAccess")
    notes: str | None = None


class SourcePatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    enabled: bool | None = None
    visibility: str | None = None
    authority_weight: float | None = Field(default=None, alias="authorityWeight")
    noise_level: float | None = Field(default=None, alias="noiseLevel")
    fetch_interval_minutes: int | None = Field(default=None, alias="fetchIntervalMinutes")
    source_group: str | None = Field(default=None, alias="sourceGroup")
    contributor_no: str | None = Field(default=None, alias="contributorNo")
    social_handle: str | None = Field(default=None, alias="socialHandle")
    collection_status: str | None = Field(default=None, alias="collectionStatus")
    free_access: bool | None = Field(default=None, alias="freeAccess")
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
    contact: str | None = None
    status: str = "unread"


class PublicFeedbackWrite(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    item_id: int | None = Field(default=None, alias="itemId")
    cluster_id: int | None = Field(default=None, alias="clusterId")
    channel: str
    feedback_type: str = Field(alias="feedbackType")
    reason: str = ""
    contact: str | None = None


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


class LoginWrite(BaseModel):
    username: str
    password: str


class UserCreateWrite(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    username: str
    password: str
    display_name: str | None = Field(default=None, alias="displayName")
    email: str | None = None
    role_ids: list[str] = Field(default_factory=lambda: ["operator"], alias="roleIds")
    status: str = "active"


class UserPatchWrite(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    password: str | None = None
    display_name: str | None = Field(default=None, alias="displayName")
    email: str | None = None
    role_ids: list[str] | None = Field(default=None, alias="roleIds")
    status: str | None = None


class RolePatchWrite(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    permission_ids: list[str] = Field(alias="permissionIds")


class PreferencePatchWrite(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    theme: str | None = None
    default_channel: str | None = Field(default=None, alias="defaultChannel")
    compact_mode: bool | None = Field(default=None, alias="compactMode")


PUBLIC_FEEDBACK_TYPES = {"general", "false_positive", "false_negative", "promote", "demote", "category_fix"}


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
    source_group: str | None = Query(default=None, alias="sourceGroup"),
    event_date: date_type | None = Query(default=None, alias="date"),
    window: int | None = Query(default=None, ge=1, le=720),
    q: str | None = None,
    take: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = select(EventClusterRecord).where(EventClusterRecord.review_status == "approved")
        if channel:
            stmt = stmt.where(EventClusterRecord.channel == channel)
        category_values = _split_filter_values(category)
        if category_values:
            stmt = stmt.where(EventClusterRecord.category.in_(category_values))
        source_group_values = _split_filter_values(source_group)
        if source_group_values:
            stmt = (
                stmt.join(NormalizedItemRecord, NormalizedItemRecord.id == EventClusterRecord.main_item_id)
                .join(SourceRecord, SourceRecord.id == NormalizedItemRecord.source_id)
                .where(SourceRecord.source_group.in_(source_group_values))
            )
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
        if page is not None:
            rows = list(session.scalars(stmt.order_by(EventClusterRecord.last_seen_at.desc(), EventClusterRecord.id.desc())).all())
            clusters = [
                cluster
                for cluster in rows
                if _is_public_cluster_ready(session, cluster, require_selected=mode == "selected")
            ]
            page_data = _numbered_page(clusters, page=page, page_size=page_size)
            events = [_event_payload(session, cluster) for cluster in page_data["rows"]]
            return {
                **_pagination_meta(page_data, len(events)),
                "nextCursor": None,
                "windowLabel": PUBLIC_WINDOW_LABEL,
                "events": events,
            }

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
        "page": 1,
        "pageSize": take,
        "total": len(events),
        "totalPages": 1 if events else 0,
        "hasPrev": False,
        "windowLabel": PUBLIC_WINDOW_LABEL,
        "events": events,
    }


@router.get("/api/v1/public/sources")
def public_sources(
    request: Request,
    channel: str | None = None,
    source_group: str | None = Query(default=None, alias="sourceGroup"),
    q: str | None = None,
    take: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=24, ge=1, le=200, alias="pageSize"),
) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = select(SourceRecord).where(SourceRecord.visibility == "public")
        if channel:
            stmt = stmt.where(SourceRecord.channel == channel)
        source_group_values = _split_filter_values(source_group)
        if source_group_values:
            stmt = stmt.where(SourceRecord.source_group.in_(source_group_values))
        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(
                    SourceRecord.id.like(like),
                    SourceRecord.name.like(like),
                    SourceRecord.url.like(like),
                    SourceRecord.social_handle.like(like),
                )
            )
        if page is not None:
            rows = list(session.scalars(stmt.order_by(SourceRecord.updated_at.desc(), SourceRecord.id.desc())).all())
            page_data = _numbered_page(rows, page=page, page_size=page_size)
            sources = [_source_payload(source) for source in page_data["rows"]]
            return {**_pagination_meta(page_data, len(sources)), "nextCursor": None, "sources": sources}
        stmt = _apply_cursor(stmt, SourceRecord.updated_at, SourceRecord.id, cursor)
        stmt = stmt.order_by(SourceRecord.updated_at.desc(), SourceRecord.id.desc()).limit(take + 1)
        page = _page_rows(list(session.scalars(stmt).all()), take, lambda source: source.updated_at, lambda source: source.id)
        sources = [_source_payload(source) for source in page["rows"]]
        return {
            "count": len(sources),
            "hasNext": page["hasNext"],
            "nextCursor": page["nextCursor"],
            "page": 1,
            "pageSize": take,
            "total": len(sources),
            "totalPages": 1 if sources else 0,
            "hasPrev": False,
            "sources": sources,
        }


@router.post("/api/v1/public/feedback-events")
def public_create_feedback_event(request: Request, payload: PublicFeedbackWrite) -> dict[str, object]:
    reason = payload.reason.strip()
    if payload.feedback_type not in PUBLIC_FEEDBACK_TYPES:
        raise HTTPException(status_code=422, detail="unsupported feedback type")
    if len(reason) < 2:
        raise HTTPException(status_code=422, detail="feedback reason is required")

    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        if payload.cluster_id is not None:
            cluster = session.get(EventClusterRecord, payload.cluster_id)
            if cluster is None or not _is_public_cluster_ready(session, cluster, require_selected=False):
                raise HTTPException(status_code=404, detail="event not found")
        event = FeedbackEventRecord(
            item_id=payload.item_id,
            cluster_id=payload.cluster_id,
            channel=payload.channel,
            feedback_type=payload.feedback_type,
            reason=reason,
            actor="public-user",
            contact=payload.contact,
            status="unread",
        )
        session.add(event)
        session.commit()
        session.refresh(event)
        return {"feedbackEvent": _feedback_payload(event)}


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
                    **_item_image_payload(session, item),
                    "sourceId": item.source_id,
                    "sourceName": source.name if source else item.source_id,
                    "sourceGroup": source.source_group if source else None,
                    "sourceType": source.source_type if source else None,
                    "sourceTier": source.tier if source else None,
                    "socialHandle": source.social_handle if source else None,
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
        return {"daily": _public_daily_payload(session, digest)}


@router.get("/api/v1/public/dailies")
def public_dailies(
    request: Request,
    channel: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = (
            select(DailyDigestRecord)
            .where(DailyDigestRecord.channel == channel)
            .where(DailyDigestRecord.published.is_(True))
            .order_by(DailyDigestRecord.digest_date.desc(), DailyDigestRecord.generated_at.desc(), DailyDigestRecord.id.desc())
        )
        rows = list(session.scalars(stmt).all())
        page_data = _numbered_page(rows, page=page, page_size=page_size)
        items = [_daily_archive_item(digest) for digest in page_data["rows"]]
        return {**_pagination_meta(page_data, len(items)), "items": items}


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


OPS_DASHBOARD = [Depends(require_permission("ops.dashboard.read"))]
SOURCES_READ = [Depends(require_permission("sources.read"))]
SOURCES_WRITE = [Depends(require_permission("sources.write"))]
HEALTH_READ = [Depends(require_permission("health.read"))]
QUALITY_READ = [Depends(require_permission("quality.read"))]
JOBS_READ = [Depends(require_permission("jobs.read"))]
JOBS_RETRY = [Depends(require_permission("jobs.retry"))]
STRATEGIES_READ = [Depends(require_permission("strategies.read"))]
STRATEGIES_WRITE = [Depends(require_permission("strategies.write"))]
STRATEGIES_ACTIVATE = [Depends(require_permission("strategies.activate"))]
FEEDBACK_READ = [Depends(require_permission("feedback.read"))]
FEEDBACK_UPDATE = [Depends(require_permission("feedback.update"))]
EVALUATIONS_READ = [Depends(require_permission("evaluations.read"))]
EVALUATIONS_RUN = [Depends(require_permission("evaluations.run"))]
EVENTS_READ = [Depends(require_permission("events.read"))]
EVENTS_REVIEW = [Depends(require_permission("events.review"))]
DAILY_READ = [Depends(require_permission("daily.read"))]
DAILY_PUBLISH = [Depends(require_permission("daily.publish"))]
USERS_MANAGE = [Depends(require_permission("users.manage"))]
ROLES_MANAGE = [Depends(require_permission("roles.manage"))]
SYSTEM_MANAGE = [Depends(require_permission("system.manage"))]


@router.post("/api/v1/auth/login")
def auth_login(request: Request, response: Response, payload: LoginWrite) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        user = session.scalar(select(UserRecord).where(UserRecord.username == payload.username))
        if user is None or user.status != "active" or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": "账号或密码错误。"})
        token = create_session(session, user)
        session.commit()
        set_session_cookie(response, token)
        principal = _principal_payload_for_user(session, user)
        return principal_payload(principal)


@router.post("/api/v1/auth/logout")
def auth_logout(request: Request, response: Response) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        revoke_session(session, request.cookies.get("aihot_session"))
        session.commit()
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/api/v1/me")
def auth_me(request: Request) -> dict[str, object]:
    return principal_payload(current_principal(request))


@router.patch("/api/v1/me/preferences")
def auth_patch_preferences(
    request: Request,
    payload: PreferencePatchWrite,
    principal=Depends(require_permission("public.read")),
) -> dict[str, object]:
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail={"code": "unauthenticated", "message": "请先登录。"})
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        prefs = session.get(UserPreferenceRecord, principal.user_id)
        if prefs is None:
            prefs = UserPreferenceRecord(user_id=principal.user_id)
            session.add(prefs)
        if payload.theme is not None:
            prefs.theme = payload.theme
        if payload.default_channel is not None:
            prefs.default_channel = payload.default_channel
        if payload.compact_mode is not None:
            prefs.compact_mode = payload.compact_mode
        session.commit()
        user = session.get(UserRecord, principal.user_id)
        return principal_payload(_principal_payload_for_user(session, user))


@router.get("/api/v1/internal/users", dependencies=USERS_MANAGE)
def internal_users(request: Request) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        users = session.scalars(select(UserRecord).order_by(UserRecord.created_at.desc(), UserRecord.id.desc())).all()
        return {"users": [_user_payload(session, user) for user in users]}


@router.post("/api/v1/internal/users", dependencies=USERS_MANAGE)
def internal_create_user(request: Request, payload: UserCreateWrite) -> dict[str, object]:
    if payload.status not in {"active", "disabled"}:
        raise HTTPException(status_code=422, detail="invalid user status")
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        if session.scalar(select(UserRecord).where(UserRecord.username == payload.username)) is not None:
            raise HTTPException(status_code=409, detail="username already exists")
        _ensure_roles_exist(session, payload.role_ids)
        user = create_user(
            session,
            username=payload.username,
            password=payload.password,
            display_name=payload.display_name,
            email=payload.email,
            role_ids=payload.role_ids,
            status=payload.status,
        )
        audit_log(request, session, action="users.create", target_type="user", target_id=user.id)
        session.commit()
        return {"user": _user_payload(session, user)}


@router.patch("/api/v1/internal/users/{user_id}", dependencies=USERS_MANAGE)
def internal_patch_user(request: Request, user_id: int, payload: UserPatchWrite) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        user = session.get(UserRecord, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="user not found")
        if payload.status is not None:
            if payload.status not in {"active", "disabled"}:
                raise HTTPException(status_code=422, detail="invalid user status")
            user.status = payload.status
        if payload.display_name is not None:
            user.display_name = payload.display_name
        if payload.email is not None:
            user.email = payload.email
        if payload.password:
            from intel_engine.auth import hash_password

            user.password_hash = hash_password(payload.password)
        if payload.role_ids is not None:
            _ensure_roles_exist(session, payload.role_ids)
            replace_user_roles(session, user.id, payload.role_ids)
        audit_log(request, session, action="users.update", target_type="user", target_id=user.id)
        session.commit()
        return {"user": _user_payload(session, user)}


@router.get("/api/v1/internal/roles", dependencies=ROLES_MANAGE)
def internal_roles(request: Request) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        roles = session.scalars(select(RoleRecord).order_by(RoleRecord.id)).all()
        permissions = session.scalars(select(PermissionRecord).order_by(PermissionRecord.group, PermissionRecord.id)).all()
        return {
            "roles": [_role_payload(session, role) for role in roles],
            "permissions": [_permission_payload(permission) for permission in permissions],
        }


@router.patch("/api/v1/internal/roles/{role_id}", dependencies=ROLES_MANAGE)
def internal_patch_role(request: Request, role_id: str, payload: RolePatchWrite) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        role = session.get(RoleRecord, role_id)
        if role is None:
            raise HTTPException(status_code=404, detail="role not found")
        _ensure_permissions_exist(session, payload.permission_ids)
        session.execute(delete(RolePermissionRecord).where(RolePermissionRecord.role_id == role_id))
        for permission_id in payload.permission_ids:
            session.add(RolePermissionRecord(role_id=role_id, permission_id=permission_id))
        audit_log(request, session, action="roles.update", target_type="role", target_id=role_id)
        session.commit()
        return {"role": _role_payload(session, role)}


@router.get("/api/v1/internal/audit-logs", dependencies=SYSTEM_MANAGE)
def internal_audit_logs(
    request: Request,
    actor: str | None = None,
    action: str | None = None,
    take: int = Query(default=50, ge=1, le=200),
) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = select(AuditLogRecord)
        if actor:
            stmt = stmt.where(AuditLogRecord.actor_username == actor)
        if action:
            stmt = stmt.where(AuditLogRecord.action == action)
        logs = session.scalars(stmt.order_by(AuditLogRecord.created_at.desc(), AuditLogRecord.id.desc()).limit(take)).all()
        return {"auditLogs": [_audit_payload(log) for log in logs]}


@router.get("/api/v1/internal/dashboard", dependencies=OPS_DASHBOARD)
def internal_dashboard(request: Request, channel: str | None = None) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        failed_jobs_stmt = select(FetchJobRecord).where(FetchJobRecord.last_error.is_not(None))
        if channel:
            failed_jobs_stmt = failed_jobs_stmt.join(SourceRecord, SourceRecord.id == FetchJobRecord.source_id).where(
                SourceRecord.channel == channel
            )
        failed_jobs = session.scalars(
            failed_jobs_stmt.order_by(FetchJobRecord.updated_at.desc(), FetchJobRecord.id.desc()).limit(5)
        ).all()
        pending_events_stmt = select(EventClusterRecord).where(EventClusterRecord.review_status == "pending")
        if channel:
            pending_events_stmt = pending_events_stmt.where(EventClusterRecord.channel == channel)
        pending_events = session.scalars(pending_events_stmt.order_by(EventClusterRecord.last_seen_at.desc()).limit(5)).all()
        pipeline_runs = session.scalars(select(PipelineRunRecord).order_by(PipelineRunRecord.started_at.desc()).limit(5)).all()
        return {
            "metrics": _dashboard_metrics(session),
            "channelMetrics": [
                {"channel": channel_id, "metrics": _dashboard_metrics(session, channel=channel_id)}
                for channel_id in _dashboard_channel_ids(session)
            ],
            "recentFailedJobs": [_job_payload(job) for job in failed_jobs],
            "pendingReviewEvents": [_internal_event_payload(session, event) for event in pending_events],
            "recentPipelineRuns": [_pipeline_run_payload(run) for run in pipeline_runs],
        }


@router.get("/api/v1/internal/quality-dashboard", dependencies=QUALITY_READ)
def internal_quality_dashboard(
    request: Request,
    window: int = Query(default=24, ge=1, le=720),
) -> dict[str, object]:
    generated_at = datetime.now(timezone.utc)
    started_at = generated_at - timedelta(hours=window)
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        channels = session.scalars(select(SourceRecord.channel).distinct().order_by(SourceRecord.channel)).all()
        return {
            "windowHours": window,
            "generatedAt": generated_at.isoformat(),
            "channels": [
                _quality_channel_payload(session, channel=channel, started_at=started_at)
                for channel in channels
            ],
        }


@router.get("/api/v1/internal/sources", dependencies=SOURCES_READ)
def internal_sources(
    request: Request,
    channel: str | None = None,
    q: str | None = None,
    source_group: str | None = Query(default=None, alias="sourceGroup"),
    collection_status: str | None = Query(default=None, alias="collectionStatus"),
    enabled: bool | None = None,
    take: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=50, ge=1, le=200, alias="pageSize"),
) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = _apply_source_filters(
            select(SourceRecord),
            channel=channel,
            q=q,
            source_group=source_group,
            collection_status=collection_status,
            enabled=enabled,
        )
        metric_rows = list(session.scalars(stmt).all())
        if page is not None:
            rows = list(session.scalars(stmt.order_by(SourceRecord.updated_at.desc(), SourceRecord.id.desc())).all())
            page_data = _numbered_page(rows, page=page, page_size=page_size)
            sources = [_source_payload(source) for source in page_data["rows"]]
            return {
                **_pagination_meta(page_data, len(sources)),
                "nextCursor": None,
                "metrics": _source_list_metrics(metric_rows),
                "sources": sources,
            }
        stmt = _apply_cursor(stmt, SourceRecord.updated_at, SourceRecord.id, cursor)
        stmt = stmt.order_by(SourceRecord.updated_at.desc(), SourceRecord.id.desc()).limit(take + 1)
        page = _page_rows(list(session.scalars(stmt).all()), take, lambda source: source.updated_at, lambda source: source.id)
        sources = [_source_payload(source) for source in page["rows"]]
        return {
            "count": len(sources),
            "hasNext": page["hasNext"],
            "nextCursor": page["nextCursor"],
            "metrics": _source_list_metrics(metric_rows),
            "sources": sources,
        }


@router.post("/api/v1/internal/sources", dependencies=SOURCES_WRITE)
def internal_create_source(request: Request, payload: SourceWrite) -> dict[str, object]:
    payload = _clean_source_payload(payload)
    _ensure_source_required_fields(payload)
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        _ensure_source_not_duplicate(session, payload)
        _ensure_source_connectivity(request, payload)
        registry = SourceRegistry(session)
        result = registry.upsert_source(_source_upsert(payload))
        source = registry.get_source(result.source_id)
        audit_log(
            request,
            session,
            action="sources.create" if result.created else "sources.update",
            target_type="source",
            target_id=source.id,
        )
        session.commit()
        return {"source": _source_payload(source), "created": result.created}


@router.patch("/api/v1/internal/sources/{source_id}", dependencies=SOURCES_WRITE)
def internal_patch_source(request: Request, source_id: str, payload: SourcePatch) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        source = session.get(SourceRecord, source_id)
        if source is None:
            raise HTTPException(status_code=404, detail="source not found")
        updates = payload.model_dump(exclude_unset=True)
        for field_name, value in updates.items():
            setattr(source, field_name, value)
        audit_log(request, session, action="sources.update", target_type="source", target_id=source.id, metadata=updates)
        session.commit()
        session.refresh(source)
        return {"source": _source_payload(source)}


@router.get("/api/v1/internal/source-states", dependencies=HEALTH_READ)
def internal_source_states(
    request: Request,
    channel: str | None = None,
    take: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = select(SourceStateRecord, SourceRecord).join(SourceRecord, SourceRecord.id == SourceStateRecord.source_id)
        if channel:
            stmt = stmt.where(SourceRecord.channel == channel)
        stmt = _apply_cursor(stmt, SourceStateRecord.updated_at, SourceRecord.id, cursor)
        stmt = stmt.order_by(SourceStateRecord.updated_at.desc(), SourceRecord.id.desc()).limit(take + 1)
        page = _page_rows(list(session.execute(stmt).all()), take, lambda row: row[0].updated_at, lambda row: row[1].id)
        states = [_source_state_payload(state, source) for state, source in page["rows"]]
        return {"count": len(states), "hasNext": page["hasNext"], "nextCursor": page["nextCursor"], "sourceStates": states}


@router.get("/api/v1/internal/source-diagnostics", dependencies=HEALTH_READ)
def internal_source_diagnostics(
    request: Request,
    channel: str | None = None,
    q: str | None = None,
    source_group: str | None = Query(default=None, alias="sourceGroup"),
    collection_status: str | None = Query(default=None, alias="collectionStatus"),
    free_access: bool | None = Query(default=None, alias="freeAccess"),
    diagnostic_status: str | None = Query(default=None, alias="diagnosticStatus"),
    sort: str = "updated_desc",
    take: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=50, ge=1, le=200, alias="pageSize"),
) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = select(SourceRecord, SourceStateRecord).join(
            SourceStateRecord,
            SourceStateRecord.source_id == SourceRecord.id,
        )
        stmt = _apply_source_filters(
            stmt,
            channel=channel,
            q=q,
            source_group=source_group,
            collection_status=collection_status,
            free_access=free_access,
        )
        if page is not None:
            rows = list(session.execute(stmt.order_by(SourceStateRecord.updated_at.desc(), SourceRecord.id.desc())).all())
            diagnostics = [_source_diagnostic_payload(session, source, state) for source, state in rows]
            diagnostics = _filter_diagnostics(diagnostics, diagnostic_status)
            diagnostics = _sort_diagnostics(diagnostics, sort)
            page_data = _numbered_page(diagnostics, page=page, page_size=page_size)
            page_diagnostics = page_data["rows"]
            return {
                **_pagination_meta(page_data, len(page_diagnostics)),
                "nextCursor": None,
                "metrics": _diagnostic_list_metrics(diagnostics),
                "sourceDiagnostics": page_diagnostics,
            }
        stmt = _apply_cursor(stmt, SourceStateRecord.updated_at, SourceRecord.id, cursor)
        stmt = stmt.order_by(SourceStateRecord.updated_at.desc(), SourceRecord.id.desc()).limit(take + 1)
        page = _page_rows(list(session.execute(stmt).all()), take, lambda row: row[1].updated_at, lambda row: row[0].id)
        diagnostics = [_source_diagnostic_payload(session, source, state) for source, state in page["rows"]]
        return {
            "count": len(diagnostics),
            "hasNext": page["hasNext"],
            "nextCursor": page["nextCursor"],
            "metrics": _diagnostic_list_metrics(diagnostics),
            "sourceDiagnostics": diagnostics,
        }


@router.get("/api/v1/internal/jobs", dependencies=JOBS_READ)
def internal_jobs(
    request: Request,
    channel: str | None = None,
    status: str | None = None,
    take: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=50, ge=1, le=200, alias="pageSize"),
) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = select(FetchJobRecord)
        if channel:
            stmt = stmt.join(SourceRecord, SourceRecord.id == FetchJobRecord.source_id).where(SourceRecord.channel == channel)
        if status:
            stmt = stmt.where(FetchJobRecord.status == status)
        if page is not None:
            rows = list(session.scalars(stmt.order_by(FetchJobRecord.created_at.desc(), FetchJobRecord.id.desc())).all())
            page_data = _numbered_page(rows, page=page, page_size=page_size)
            jobs = [_job_payload(job) for job in page_data["rows"]]
            return {**_pagination_meta(page_data, len(jobs)), "nextCursor": None, "jobs": jobs}
        stmt = _apply_cursor(stmt, FetchJobRecord.created_at, FetchJobRecord.id, cursor)
        stmt = stmt.order_by(FetchJobRecord.created_at.desc(), FetchJobRecord.id.desc()).limit(take + 1)
        page = _page_rows(list(session.scalars(stmt).all()), take, lambda job: job.created_at, lambda job: job.id)
        jobs = [_job_payload(job) for job in page["rows"]]
        return {"count": len(jobs), "hasNext": page["hasNext"], "nextCursor": page["nextCursor"], "jobs": jobs}


@router.post("/api/v1/internal/jobs/{job_id}/retry", dependencies=JOBS_RETRY)
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
        audit_log(request, session, action="jobs.retry", target_type="job", target_id=job.id)
        session.commit()
        session.refresh(job)
        return {"job": _job_payload(job)}


@router.get("/api/v1/internal/strategy-versions", dependencies=STRATEGIES_READ)
def internal_strategy_versions(request: Request, channel: str | None = None) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = select(StrategyVersionRecord).order_by(StrategyVersionRecord.created_at.desc())
        if channel:
            stmt = stmt.where(StrategyVersionRecord.channel == channel)
        return {"strategyVersions": [_strategy_payload(strategy) for strategy in session.scalars(stmt).all()]}


@router.post("/api/v1/internal/strategy-versions", dependencies=STRATEGIES_WRITE)
def internal_create_strategy_version(request: Request, payload: StrategyVersionWrite) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        strategy = StrategyVersionRecord(**payload.model_dump())
        session.add(strategy)
        audit_log(request, session, action="strategies.create", target_type="strategy", target_id=strategy.id)
        session.commit()
        session.refresh(strategy)
        return {"strategyVersion": _strategy_payload(strategy)}


@router.post("/api/v1/internal/strategy-versions/{strategy_id}/activate", dependencies=STRATEGIES_ACTIVATE)
def internal_activate_strategy_version(request: Request, strategy_id: str) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        try:
            strategy = activate_strategy_version(session, strategy_id, now=datetime.now(timezone.utc))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        audit_log(request, session, action="strategies.activate", target_type="strategy", target_id=strategy.id)
        session.commit()
        session.refresh(strategy)
        return {"strategyVersion": _strategy_payload(strategy)}


@router.post("/api/v1/internal/feedback-events", dependencies=FEEDBACK_UPDATE)
def internal_create_feedback_event(request: Request, payload: FeedbackEventWrite) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        event = FeedbackEventRecord(**payload.model_dump())
        session.add(event)
        session.flush()
        audit_log(request, session, action="feedback.create", target_type="feedback", target_id=event.id)
        session.commit()
        session.refresh(event)
        return {"feedbackEvent": _feedback_payload(event)}


@router.get("/api/v1/internal/feedback-events", dependencies=FEEDBACK_READ)
def internal_feedback_events(
    request: Request,
    channel: str | None = None,
    feedback_type: str | None = Query(default=None, alias="feedbackType"),
    cluster_id: int | None = Query(default=None, alias="clusterId"),
    take: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=50, ge=1, le=200, alias="pageSize"),
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
        if page is not None:
            rows = list(session.scalars(stmt.order_by(FeedbackEventRecord.created_at.desc(), FeedbackEventRecord.id.desc())).all())
            page_data = _numbered_page(rows, page=page, page_size=page_size)
            events = [_feedback_payload(event) for event in page_data["rows"]]
            return {**_pagination_meta(page_data, len(events)), "nextCursor": None, "feedbackEvents": events}
        stmt = _apply_cursor(stmt, FeedbackEventRecord.created_at, FeedbackEventRecord.id, cursor)
        stmt = stmt.order_by(FeedbackEventRecord.created_at.desc(), FeedbackEventRecord.id.desc()).limit(take + 1)
        page = _page_rows(list(session.scalars(stmt).all()), take, lambda event: event.created_at, lambda event: event.id)
        events = [_feedback_payload(event) for event in page["rows"]]
        return {"count": len(events), "hasNext": page["hasNext"], "nextCursor": page["nextCursor"], "feedbackEvents": events}


@router.patch("/api/v1/internal/feedback-events/{feedback_id}", dependencies=FEEDBACK_UPDATE)
def internal_patch_feedback_event(request: Request, feedback_id: int, payload: dict[str, object]) -> dict[str, object]:
    status = payload.get("status")
    if status not in {"unread", "read", "accepted", "ignored"}:
        raise HTTPException(status_code=422, detail="invalid feedback status")
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        event = session.get(FeedbackEventRecord, feedback_id)
        if event is None:
            raise HTTPException(status_code=404, detail="feedback event not found")
        event.status = str(status)
        audit_log(request, session, action="feedback.update", target_type="feedback", target_id=event.id, metadata={"status": status})
        session.commit()
        session.refresh(event)
        return {"feedbackEvent": _feedback_payload(event)}


@router.post("/api/v1/internal/evaluation-runs", dependencies=EVALUATIONS_RUN)
def internal_create_evaluation_run(request: Request, payload: EvaluationRunWrite) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        run = EvaluationRunRecord(**payload.model_dump(), status="pending", metrics_json={})
        session.add(run)
        session.flush()
        audit_log(request, session, action="evaluations.create", target_type="evaluation", target_id=run.id)
        session.commit()
        session.refresh(run)
        return {"evaluationRun": _evaluation_run_payload(run)}


@router.get("/api/v1/internal/evaluation-runs", dependencies=EVALUATIONS_READ)
def internal_evaluation_runs(
    request: Request,
    channel: str | None = None,
    take: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=50, ge=1, le=200, alias="pageSize"),
) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = select(EvaluationRunRecord)
        if channel:
            stmt = stmt.where(EvaluationRunRecord.channel == channel)
        if page is not None:
            rows = list(session.scalars(stmt.order_by(EvaluationRunRecord.created_at.desc(), EvaluationRunRecord.id.desc())).all())
            page_data = _numbered_page(rows, page=page, page_size=page_size)
            runs = [_evaluation_run_payload(run) for run in page_data["rows"]]
            return {**_pagination_meta(page_data, len(runs)), "nextCursor": None, "evaluationRuns": runs}
        stmt = _apply_cursor(stmt, EvaluationRunRecord.created_at, EvaluationRunRecord.id, cursor)
        stmt = stmt.order_by(EvaluationRunRecord.created_at.desc(), EvaluationRunRecord.id.desc()).limit(take + 1)
        page = _page_rows(list(session.scalars(stmt).all()), take, lambda run: run.created_at, lambda run: run.id)
        runs = [_evaluation_run_payload(run) for run in page["rows"]]
        return {"count": len(runs), "hasNext": page["hasNext"], "nextCursor": page["nextCursor"], "evaluationRuns": runs}


@router.get("/api/v1/internal/evaluation-runs/{run_id}", dependencies=EVALUATIONS_READ)
def internal_evaluation_run_detail(request: Request, run_id: int) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        run = session.get(EvaluationRunRecord, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="evaluation run not found")
        return {"evaluationRun": _evaluation_run_payload(run)}


@router.post("/api/v1/internal/evaluation-runs/{run_id}/run", dependencies=EVALUATIONS_RUN)
def internal_run_evaluation(request: Request, run_id: int) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        try:
            run = run_evaluation(session, run_id, now=datetime.now(timezone.utc))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        audit_log(request, session, action="evaluations.run", target_type="evaluation", target_id=run.id)
        session.commit()
        session.refresh(run)
        return {"evaluationRun": _evaluation_run_payload(run)}


@router.get("/api/v1/internal/events", dependencies=EVENTS_READ)
def internal_events(
    request: Request,
    channel: str | None = None,
    review_status: str | None = Query(default=None, alias="reviewStatus"),
    category: str | None = None,
    q: str | None = None,
    take: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=50, ge=1, le=200, alias="pageSize"),
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
        if page is not None:
            rows = list(session.scalars(stmt.order_by(EventClusterRecord.last_seen_at.desc(), EventClusterRecord.id.desc())).all())
            page_data = _numbered_page(rows, page=page, page_size=page_size)
            events = [_internal_event_payload(session, event) for event in page_data["rows"]]
            return {**_pagination_meta(page_data, len(events)), "nextCursor": None, "events": events}
        stmt = _apply_cursor(stmt, EventClusterRecord.last_seen_at, EventClusterRecord.id, cursor)
        stmt = stmt.order_by(EventClusterRecord.last_seen_at.desc(), EventClusterRecord.id.desc()).limit(take + 1)
        page = _page_rows(list(session.scalars(stmt).all()), take, lambda event: event.last_seen_at, lambda event: event.id)
        events = [_internal_event_payload(session, event) for event in page["rows"]]
        return {"count": len(events), "hasNext": page["hasNext"], "nextCursor": page["nextCursor"], "events": events}


@router.get("/api/v1/internal/events/{event_id}", dependencies=EVENTS_READ)
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


@router.patch("/api/v1/internal/events/{event_id}/review", dependencies=EVENTS_REVIEW)
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
        audit_log(
            request,
            session,
            action="events.review",
            target_type="event",
            target_id=cluster.id,
            metadata={"reviewStatus": payload.review_status},
        )
        session.commit()
        session.refresh(cluster)
        return {"event": _internal_event_payload(session, cluster)}


@router.get("/api/v1/internal/daily-digests", dependencies=DAILY_READ)
def internal_daily_digests(
    request: Request,
    channel: str | None = None,
    digest_date: date_type | None = Query(default=None, alias="date"),
    take: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=50, ge=1, le=200, alias="pageSize"),
) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        stmt = select(DailyDigestRecord)
        if channel:
            stmt = stmt.where(DailyDigestRecord.channel == channel)
        if digest_date is not None:
            stmt = stmt.where(DailyDigestRecord.digest_date == digest_date)
        if page is not None:
            rows = list(session.scalars(stmt.order_by(DailyDigestRecord.generated_at.desc(), DailyDigestRecord.id.desc())).all())
            page_data = _numbered_page(rows, page=page, page_size=page_size)
            digests = [_daily_digest_payload(digest) for digest in page_data["rows"]]
            return {**_pagination_meta(page_data, len(digests)), "nextCursor": None, "dailyDigests": digests}
        stmt = _apply_cursor(stmt, DailyDigestRecord.generated_at, DailyDigestRecord.id, cursor)
        stmt = stmt.order_by(DailyDigestRecord.generated_at.desc(), DailyDigestRecord.id.desc()).limit(take + 1)
        page = _page_rows(list(session.scalars(stmt).all()), take, lambda digest: digest.generated_at, lambda digest: digest.id)
        digests = [_daily_digest_payload(digest) for digest in page["rows"]]
        return {"count": len(digests), "hasNext": page["hasNext"], "nextCursor": page["nextCursor"], "dailyDigests": digests}


@router.post("/api/v1/internal/daily-digests/generate", dependencies=DAILY_PUBLISH)
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
        audit_log(request, session, action="daily.generate", target_type="daily_digest", target_id=result.digest_id)
        session.commit()
        session.refresh(digest)
        return {
            "dailyDigest": _daily_digest_payload(digest),
            "created": result.created,
            "eventCount": result.event_count,
        }


@router.post("/api/v1/internal/daily-digests/{digest_id}/publish", dependencies=DAILY_PUBLISH)
def internal_publish_daily_digest(request: Request, digest_id: int, payload: ActorWrite) -> dict[str, object]:
    return _set_daily_digest_published(request, digest_id, published=True, actor=payload.actor)


@router.post("/api/v1/internal/daily-digests/{digest_id}/unpublish", dependencies=DAILY_PUBLISH)
def internal_unpublish_daily_digest(request: Request, digest_id: int, payload: ActorWrite) -> dict[str, object]:
    return _set_daily_digest_published(request, digest_id, published=False, actor=payload.actor)


@router.get("/api/v1/internal/pipeline-runs", dependencies=OPS_DASHBOARD)
def internal_pipeline_runs(
    request: Request,
    take: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=50, ge=1, le=200, alias="pageSize"),
) -> dict[str, object]:
    SessionLocal = _production_sessionmaker(request)
    with SessionLocal() as session:
        if page is not None:
            rows = list(session.scalars(select(PipelineRunRecord).order_by(PipelineRunRecord.started_at.desc(), PipelineRunRecord.id.desc())).all())
            page_data = _numbered_page(rows, page=page, page_size=page_size)
            runs = [_pipeline_run_payload(run) for run in page_data["rows"]]
            return {**_pagination_meta(page_data, len(runs)), "nextCursor": None, "pipelineRuns": runs}
        stmt = _apply_cursor(select(PipelineRunRecord), PipelineRunRecord.started_at, PipelineRunRecord.id, cursor)
        stmt = stmt.order_by(PipelineRunRecord.started_at.desc(), PipelineRunRecord.id.desc()).limit(take + 1)
        page = _page_rows(list(session.scalars(stmt).all()), take, lambda run: run.started_at, lambda run: run.id)
        runs = [_pipeline_run_payload(run) for run in page["rows"]]
        return {"count": len(runs), "hasNext": page["hasNext"], "nextCursor": page["nextCursor"], "pipelineRuns": runs}


@router.post("/api/v1/internal/pipeline-runs", dependencies=JOBS_RETRY)
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
        audit_log(request, session, action="pipeline.run", target_type="pipeline_run", target_id=run.id, result=status)
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


def _numbered_page(rows: list, *, page: int, page_size: int) -> dict[str, object]:
    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    total_pages = (total + page_size - 1) // page_size if total else 0
    return {
        "rows": rows[start:end],
        "page": page,
        "pageSize": page_size,
        "total": total,
        "totalPages": total_pages,
        "hasPrev": page > 1 and total > 0,
        "hasNext": total_pages > page,
    }


def _split_filter_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.replace("|", ",").split(",") if part.strip()]


def _apply_source_filters(
    stmt,
    *,
    channel: str | None = None,
    q: str | None = None,
    source_group: str | None = None,
    collection_status: str | None = None,
    enabled: bool | None = None,
    free_access: bool | None = None,
):
    if channel:
        stmt = stmt.where(SourceRecord.channel == channel)
    query_text = (q or "").strip()
    if query_text:
        pattern = f"%{query_text}%"
        stmt = stmt.where(or_(SourceRecord.name.ilike(pattern), SourceRecord.id.ilike(pattern), SourceRecord.url.ilike(pattern)))
    source_group_values = _split_filter_values(source_group)
    if source_group_values:
        stmt = stmt.where(SourceRecord.source_group.in_(source_group_values))
    collection_values = _split_filter_values(collection_status)
    if collection_values:
        stmt = stmt.where(SourceRecord.collection_status.in_(collection_values))
    if enabled is not None:
        stmt = stmt.where(SourceRecord.enabled.is_(enabled))
    if free_access is not None:
        stmt = stmt.where(SourceRecord.free_access.is_(free_access))
    return stmt


def _source_list_metrics(sources: list[SourceRecord]) -> dict[str, int]:
    return {
        "sourceCount": len(sources),
        "enabledSourceCount": sum(1 for source in sources if source.enabled),
        "highAuthorityCount": sum(1 for source in sources if source.authority_weight >= 90),
        "pendingSocialCount": sum(
            1
            for source in sources
            if source.source_group == "social" and source.collection_status != "collectable"
        ),
    }


def _clean_source_payload(payload: SourceWrite) -> SourceWrite:
    return payload.model_copy(update={"id": payload.id.strip(), "name": payload.name.strip(), "url": payload.url.strip()})


def _ensure_source_required_fields(payload: SourceWrite) -> None:
    missing: list[str] = []
    if not payload.id:
        missing.append("信源 ID")
    if not payload.name:
        missing.append("名称")
    if not payload.url:
        missing.append("URL")
    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_source",
                "message": f"{'、'.join(missing)}不能为空。",
            },
        )


def _ensure_source_not_duplicate(session, payload: SourceWrite) -> None:
    if session.get(SourceRecord, payload.id) is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "source_exists",
                "message": f"信源已存在：ID「{payload.id}」已被使用。",
            },
        )

    normalized_url = canonicalize_url(payload.url).lower()
    for source in session.scalars(select(SourceRecord)).all():
        if canonicalize_url(source.url).lower() == normalized_url:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "source_url_exists",
                    "message": f"信源已存在：URL 已被「{source.name or source.id}」使用。",
                },
            )


def _ensure_source_connectivity(request: Request, payload: SourceWrite) -> None:
    validator = getattr(request.app.state, "source_connectivity_validator", None)
    if validator is not None:
        result = validator(payload)
        ok = bool(result.get("ok")) if isinstance(result, dict) else bool(result)
        if ok:
            return
        message = str(result.get("message") if isinstance(result, dict) else "连通性测试失败。")
        _raise_source_connectivity_error(message)

    source = SourceRecord(
        id=payload.id,
        channel=payload.channel,
        source_type=payload.source_type,
        tier=payload.tier,
        name=payload.name,
        url=payload.url,
        language=payload.language,
        region=payload.region,
        marketplace=payload.marketplace,
        authority_weight=payload.authority_weight,
        noise_level=payload.noise_level,
        fetch_adapter=payload.fetch_adapter,
        parser_type=payload.parser_type,
        default_categories=list(payload.default_categories),
        fetch_interval_minutes=payload.fetch_interval_minutes,
        enabled=payload.enabled,
        visibility=payload.visibility,
        source_group=payload.source_group,
        contributor_no=payload.contributor_no,
        social_handle=payload.social_handle,
        collection_status=payload.collection_status,
        free_access=payload.free_access,
        notes=payload.notes,
    )
    try:
        adapter = get_fetch_adapter(payload.fetch_adapter)
        with httpx.Client(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "AIHOT Source Validator/1.0"},
        ) as client:
            result = adapter.fetch(source, client=client)
    except KeyError as exc:
        _raise_source_connectivity_error(f"不支持的采集方式：{payload.fetch_adapter}。")
    except httpx.HTTPError as exc:
        _raise_source_connectivity_error(f"连通性测试失败：{exc}")
    except Exception as exc:
        _raise_source_connectivity_error(f"连通性测试失败：{exc}")

    if result.status != "succeeded":
        _raise_source_connectivity_error(result.error_message or f"连通性测试失败：HTTP {result.http_status or '未知'}")
    if not result.documents:
        _raise_source_connectivity_error("连通性测试通过，但没有抓取到可用内容。请检查采集方式、页面结构或 RSS 是否有最近内容。")


def _raise_source_connectivity_error(message: str):
    raise HTTPException(
        status_code=422,
        detail={
            "code": "source_connectivity_failed",
            "message": message or "连通性测试失败，信源未保存。",
        },
    )


def _filter_diagnostics(diagnostics: list[dict[str, object]], diagnostic_status: str | None) -> list[dict[str, object]]:
    values = set(_split_filter_values(diagnostic_status))
    if not values:
        return diagnostics
    return [diagnostic for diagnostic in diagnostics if diagnostic["diagnosticStatus"] in values]


def _sort_diagnostics(diagnostics: list[dict[str, object]], sort: str) -> list[dict[str, object]]:
    if sort == "updated_desc":
        return diagnostics
    if sort == "health_asc":
        return sorted(diagnostics, key=lambda item: (float(item["healthScore"]), str(item["sourceId"])))
    if sort == "error_desc":
        return sorted(diagnostics, key=lambda item: (-int(item["errorStreak"]), str(item["sourceId"])))
    if sort == "next_fetch":
        return sorted(diagnostics, key=lambda item: (str(item["nextFetchAt"] or "9999"), str(item["sourceId"])))
    if sort == "last_error":
        return sorted(diagnostics, key=lambda item: (str(item["lastErrorAt"] or ""), str(item["sourceId"])), reverse=True)
    return sorted(diagnostics, key=lambda item: (str(item["diagnosticStatus"]), str(item["sourceId"])))


def _diagnostic_list_metrics(diagnostics: list[dict[str, object]]) -> dict[str, int]:
    warning_count = sum(1 for item in diagnostics if item["diagnosticStatus"] not in {"usable", "waiting"})
    if diagnostics:
        average = round(sum(float(item["healthScore"]) for item in diagnostics) / len(diagnostics))
    else:
        average = 0
    return {
        "sourceCount": len(diagnostics),
        "averageHealthScore": average,
        "usableCount": sum(1 for item in diagnostics if item["diagnosticStatus"] == "usable"),
        "warningCount": warning_count,
        "missingDateCount": sum(1 for item in diagnostics if item["diagnosticStatus"] == "missing_publish_time"),
        "waitingCount": sum(1 for item in diagnostics if item["diagnosticStatus"] == "waiting"),
    }


def _dashboard_channel_ids(session) -> list[str]:
    configured = [config.id for config in load_channel_configs()]
    stored = session.scalars(select(SourceRecord.channel).distinct().order_by(SourceRecord.channel)).all()
    return sorted(set(configured) | set(stored))


def _dashboard_metrics(session, channel: str | None = None) -> dict[str, int]:
    source_stmt = select(func.count()).select_from(SourceRecord)
    health_stmt = select(func.count()).select_from(SourceStateRecord).join(
        SourceRecord, SourceRecord.id == SourceStateRecord.source_id
    )
    pending_job_stmt = select(func.count()).select_from(FetchJobRecord).join(SourceRecord, SourceRecord.id == FetchJobRecord.source_id)
    failed_job_stmt = select(func.count()).select_from(FetchJobRecord).join(SourceRecord, SourceRecord.id == FetchJobRecord.source_id)
    pending_event_stmt = select(func.count()).select_from(EventClusterRecord)
    daily_stmt = select(func.count()).select_from(DailyDigestRecord)
    if channel:
        source_stmt = source_stmt.where(SourceRecord.channel == channel)
        health_stmt = health_stmt.where(SourceRecord.channel == channel)
        pending_job_stmt = pending_job_stmt.where(SourceRecord.channel == channel)
        failed_job_stmt = failed_job_stmt.where(SourceRecord.channel == channel)
        pending_event_stmt = pending_event_stmt.where(EventClusterRecord.channel == channel)
        daily_stmt = daily_stmt.where(DailyDigestRecord.channel == channel)
    return {
        "sourceCount": _count(session, source_stmt),
        "healthWarningCount": _count(
            session,
            health_stmt.where((SourceStateRecord.error_streak > 0) | (SourceStateRecord.health_score < 80)),
        ),
        "pendingJobCount": _count(session, pending_job_stmt.where(FetchJobRecord.status == "pending")),
        "failedJobCount": _count(
            session,
            failed_job_stmt.where(FetchJobRecord.status.in_(["failed", "dead", "pending"])).where(
                FetchJobRecord.last_error.is_not(None)
            ),
        ),
        "pendingReviewEventCount": _count(
            session, pending_event_stmt.where(EventClusterRecord.review_status == "pending")
        ),
        "publishedDailyCount": _count(session, daily_stmt.where(DailyDigestRecord.published.is_(True))),
    }


def _pagination_meta(page_data: dict[str, object], count: int) -> dict[str, object]:
    return {
        "count": count,
        "page": page_data["page"],
        "pageSize": page_data["pageSize"],
        "total": page_data["total"],
        "totalPages": page_data["totalPages"],
        "hasPrev": page_data["hasPrev"],
        "hasNext": page_data["hasNext"],
    }


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


def _encode_cursor(sort_at: datetime, row_id: int | str) -> str:
    payload = {"sortAt": sort_at.isoformat(), "id": row_id}
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("ascii")


def _decode_cursor(value: str) -> dict[str, object]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8"))
        sort_at = datetime.fromisoformat(str(payload["sortAt"]))
        row_id = payload["id"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="invalid cursor") from exc
    if not isinstance(row_id, (int, str)):
        raise HTTPException(status_code=422, detail="invalid cursor")
    if sort_at.tzinfo is None:
        sort_at = sort_at.replace(tzinfo=timezone.utc)
    return {"sortAt": sort_at, "id": row_id}


def _source_upsert(payload: SourceWrite) -> SourceUpsert:
    return SourceUpsert(**payload.model_dump())


def _principal_payload_for_user(session, user: UserRecord) -> Principal:
    roles = list(
        session.scalars(
            select(UserRoleRecord.role_id).where(UserRoleRecord.user_id == user.id).order_by(UserRoleRecord.role_id)
        ).all()
    )
    permissions = sorted(
        set(
            session.scalars(
                select(RolePermissionRecord.permission_id).where(RolePermissionRecord.role_id.in_(roles))
            ).all()
        )
    )
    prefs = session.get(UserPreferenceRecord, user.id)
    return Principal(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        roles=roles,
        permissions=permissions,
        preferences={
            "theme": prefs.theme if prefs else "system",
            "defaultChannel": prefs.default_channel if prefs else "ai",
            "compactMode": prefs.compact_mode if prefs else False,
        },
        authenticated=True,
        auth_type="session",
    )


def _user_payload(session, user: UserRecord) -> dict[str, object]:
    roles = list(
        session.scalars(
            select(UserRoleRecord.role_id).where(UserRoleRecord.user_id == user.id).order_by(UserRoleRecord.role_id)
        ).all()
    )
    prefs = session.get(UserPreferenceRecord, user.id)
    return {
        "id": str(user.id),
        "username": user.username,
        "displayName": user.display_name,
        "email": user.email,
        "status": user.status,
        "roles": roles,
        "preferences": {
            "theme": prefs.theme if prefs else "system",
            "defaultChannel": prefs.default_channel if prefs else "ai",
            "compactMode": prefs.compact_mode if prefs else False,
        },
        "lastLoginAt": _iso(user.last_login_at),
        "createdAt": _iso(user.created_at),
        "updatedAt": _iso(user.updated_at),
    }


def _role_payload(session, role: RoleRecord) -> dict[str, object]:
    permissions = list(
        session.scalars(
            select(RolePermissionRecord.permission_id)
            .where(RolePermissionRecord.role_id == role.id)
            .order_by(RolePermissionRecord.permission_id)
        ).all()
    )
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "locked": role.locked,
        "permissions": permissions,
        "createdAt": _iso(role.created_at),
        "updatedAt": _iso(role.updated_at),
    }


def _permission_payload(permission: PermissionRecord) -> dict[str, object]:
    return {
        "id": permission.id,
        "name": permission.name,
        "description": permission.description,
        "group": permission.group,
    }


def _audit_payload(log: AuditLogRecord) -> dict[str, object]:
    return {
        "id": str(log.id),
        "actorUserId": str(log.actor_user_id) if log.actor_user_id is not None else None,
        "actorUsername": log.actor_username,
        "action": log.action,
        "targetType": log.target_type,
        "targetId": log.target_id,
        "result": log.result,
        "metadata": log.metadata_json,
        "createdAt": _iso(log.created_at),
    }


def _ensure_roles_exist(session, role_ids: list[str]) -> None:
    existing = set(session.scalars(select(RoleRecord.id).where(RoleRecord.id.in_(role_ids))).all())
    missing = set(role_ids) - existing
    if missing:
        raise HTTPException(status_code=422, detail=f"unknown roles: {', '.join(sorted(missing))}")


def _ensure_permissions_exist(session, permission_ids: list[str]) -> None:
    existing = set(session.scalars(select(PermissionRecord.id).where(PermissionRecord.id.in_(permission_ids))).all())
    missing = set(permission_ids) - existing
    if missing:
        raise HTTPException(status_code=422, detail=f"unknown permissions: {', '.join(sorted(missing))}")


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
        "sourceGroup": source.source_group,
        "contributorNo": source.contributor_no,
        "socialHandle": source.social_handle,
        "collectionStatus": source.collection_status,
        "freeAccess": source.free_access,
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


def _source_diagnostic_payload(session, source: SourceRecord, state: SourceStateRecord) -> dict[str, object]:
    latest_run = _latest_fetch_run(session, source.id)
    latest_job = _latest_fetch_job(session, source.id)
    latest_screening = _latest_screening_result(session, source.id)
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    accepted_count = _screening_count(session, source.id, "accepted", since)
    rejected_count = _screening_count(session, source.id, "rejected", since)
    raw_count = _count(
        session,
        select(func.count())
        .select_from(RawDocumentRecord)
        .where(RawDocumentRecord.source_id == source.id, RawDocumentRecord.fetched_at >= since),
    )
    status = _diagnostic_status(source, state, latest_run, latest_screening)
    return {
        "sourceId": source.id,
        "sourceName": source.name,
        "channel": source.channel,
        "tier": source.tier,
        "enabled": source.enabled,
        "sourceGroup": source.source_group,
        "collectionStatus": source.collection_status,
        "freeAccess": source.free_access,
        "diagnosticStatus": status,
        "diagnosticLabel": _diagnostic_label(status),
        "healthScore": state.health_score,
        "errorStreak": state.error_streak,
        "duplicateRatio": state.duplicate_ratio,
        "noiseRatio": state.noise_ratio,
        "nextFetchAt": _iso(state.next_fetch_at),
        "lastSuccessAt": _iso(state.last_success_at),
        "lastErrorAt": _iso(state.last_error_at),
        "backoffUntil": _iso(state.backoff_until),
        "rawCount24h": raw_count,
        "lastRun": _fetch_run_payload(latest_run),
        "lastJob": _job_payload(latest_job) if latest_job else None,
        "screening": _screening_payload(latest_screening, accepted_count, rejected_count),
    }


def _latest_fetch_run(session, source_id: str) -> FetchRunRecord | None:
    return session.scalar(
        select(FetchRunRecord)
        .where(FetchRunRecord.source_id == source_id)
        .order_by(FetchRunRecord.started_at.desc(), FetchRunRecord.id.desc())
        .limit(1)
    )


def _latest_fetch_job(session, source_id: str) -> FetchJobRecord | None:
    return session.scalar(
        select(FetchJobRecord)
        .where(FetchJobRecord.source_id == source_id)
        .order_by(FetchJobRecord.updated_at.desc(), FetchJobRecord.id.desc())
        .limit(1)
    )


def _latest_screening_result(session, source_id: str) -> RawScreeningResultRecord | None:
    return session.scalar(
        select(RawScreeningResultRecord)
        .join(RawDocumentRecord, RawDocumentRecord.id == RawScreeningResultRecord.raw_document_id)
        .where(RawDocumentRecord.source_id == source_id)
        .order_by(RawScreeningResultRecord.created_at.desc(), RawScreeningResultRecord.id.desc())
        .limit(1)
    )


def _screening_count(session, source_id: str, status: str, since: datetime) -> int:
    return _count(
        session,
        select(func.count())
        .select_from(RawScreeningResultRecord)
        .join(RawDocumentRecord, RawDocumentRecord.id == RawScreeningResultRecord.raw_document_id)
        .where(
            RawDocumentRecord.source_id == source_id,
            RawScreeningResultRecord.screen_status == status,
            RawScreeningResultRecord.created_at >= since,
        ),
    )


def _fetch_run_payload(run: FetchRunRecord | None) -> dict[str, object] | None:
    if run is None:
        return None
    metadata = run.metadata_json or {}
    return {
        "id": str(run.id),
        "status": run.status,
        "startedAt": _iso(run.started_at),
        "finishedAt": _iso(run.finished_at),
        "httpStatus": run.http_status,
        "contentType": run.content_type,
        "bytesReceived": run.bytes_received,
        "itemCount": run.item_count,
        "candidateItems": _metadata_int(metadata, "candidate_items"),
        "acceptedItems": _metadata_int(metadata, "accepted_items"),
        "skippedOldItems": _metadata_int(metadata, "skipped_old_items"),
        "skippedMissingDate": _metadata_int(metadata, "skipped_missing_date"),
        "skippedInvalidOriginalUrl": _metadata_int(metadata, "skipped_invalid_original_url"),
        "errorMessage": run.error_message,
    }


def _screening_payload(
    screening: RawScreeningResultRecord | None,
    accepted_count: int,
    rejected_count: int,
) -> dict[str, object]:
    return {
        "latestStatus": screening.screen_status if screening else None,
        "latestBucket": screening.screen_bucket if screening else None,
        "latestReasonCode": screening.reason_code if screening else None,
        "latestReason": screening.reason_cn if screening else None,
        "latestAt": _iso(screening.created_at) if screening else None,
        "accepted24h": accepted_count,
        "rejected24h": rejected_count,
    }


def _diagnostic_status(
    source: SourceRecord,
    state: SourceStateRecord,
    latest_run: FetchRunRecord | None,
    latest_screening: RawScreeningResultRecord | None,
) -> str:
    now = datetime.now(timezone.utc)
    if source.collection_status != "collectable" and not source.enabled:
        return source.collection_status
    if not source.enabled:
        return "disabled"
    if state.backoff_until and _aware_utc(state.backoff_until) > now:
        return "backoff"
    if state.error_streak > 0:
        return "fetch_failed"
    if latest_screening:
        if latest_screening.screen_status == "accepted":
            return "usable"
        if latest_screening.reason_code in {"missing_publish_time", "invalid_original_url"}:
            return latest_screening.reason_code
    if latest_run:
        metadata = latest_run.metadata_json or {}
        if _metadata_int(metadata, "accepted_items") > 0:
            return "usable"
        if _metadata_int(metadata, "skipped_missing_date") > 0:
            return "missing_publish_time"
        if _metadata_int(metadata, "skipped_invalid_original_url") > 0:
            return "invalid_original_url"
        if _metadata_int(metadata, "skipped_old_items") > 0:
            return "no_current_items"
        if latest_run.status == "failed":
            return "fetch_failed"
        if state.duplicate_ratio >= 0.8:
            return "mostly_duplicates"
        return "no_accepted_items"
    return "waiting"


def _diagnostic_label(status: str) -> str:
    labels = {
        "usable": "可用",
        "waiting": "等待抓取",
        "backoff": "退避中",
        "fetch_failed": "抓取失败",
        "missing_publish_time": "缺少发布时间",
        "invalid_original_url": "原文链接无效",
        "no_current_items": "无最近 24 小时内容",
        "no_accepted_items": "无有效条目",
        "mostly_duplicates": "重复内容偏多",
        "disabled": "已停用",
        "pending_api": "待接入",
        "rate_limited": "限流",
        "unavailable": "不可用",
    }
    return labels.get(status, status)


def _metadata_int(metadata: dict[str, object], key: str) -> int:
    value = metadata.get(key, 0)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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
        "contact": event.contact,
        "status": event.status,
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


def _public_daily_payload(session, digest: DailyDigestRecord) -> dict[str, object]:
    document = _daily_document(session, digest)
    return {
        "id": str(digest.id),
        "channel": digest.channel,
        "date": digest.digest_date.isoformat(),
        "generatedAt": _iso(digest.generated_at),
        "title": digest.title,
        "lead": document["lead"],
        "sections": document["sections"],
        "archiveItem": document["archiveItem"],
        "stats": document["stats"],
        "sectionsJson": digest.sections_json,
        "published": digest.published,
        "windowLabel": PUBLIC_WINDOW_LABEL,
    }


def _daily_document(session, digest: DailyDigestRecord) -> dict[str, object]:
    raw = digest.sections_json or {}
    if isinstance(raw.get("sections"), list):
        sections = raw["sections"]
        lead = raw.get("lead") or _lead_from_sections(sections)
        stats = raw.get("stats") or {"storyCount": sum(len(section.get("items", [])) for section in sections if isinstance(section, dict))}
    else:
        highlights = raw.get("highlights", [])
        if not isinstance(highlights, list):
            highlights = []
        items = [_daily_item_from_highlight(session, item) for item in highlights if isinstance(item, dict)]
        sections = _daily_sections_from_items(digest.channel, items)
        lead = items[0] if items else None
        stats = {"storyCount": len(items)}
    archive_item = raw.get("archiveItem") if isinstance(raw.get("archiveItem"), dict) else None
    return {
        "lead": lead,
        "sections": sections,
        "stats": stats,
        "archiveItem": archive_item or _daily_archive_item(digest, lead=lead, story_count=int(stats.get("storyCount", 0))),
    }


def _daily_item_from_highlight(session, item: dict[str, object]) -> dict[str, object]:
    event_id = item.get("eventId")
    cluster = session.get(EventClusterRecord, int(event_id)) if event_id and str(event_id).isdigit() else None
    payload = _event_payload(session, cluster) if cluster else {}
    return {
        "eventId": str(event_id) if event_id is not None else None,
        "title": str(item.get("title") or payload.get("title") or ""),
        "summary": str(item.get("summary") or payload.get("summary") or ""),
        "entryReason": str(item.get("entryReason") or payload.get("entryReason") or ""),
        "category": str(item.get("category") or payload.get("category") or ""),
        "score": item.get("score") or payload.get("score") or 0,
        "sourceCount": item.get("sourceCount") or payload.get("sourceCount") or 0,
        "memberCount": item.get("memberCount") or payload.get("memberCount") or 0,
        "lastSeenAt": item.get("lastSeenAt") or payload.get("lastSeenAt"),
        "mainItem": payload.get("mainItem"),
    }


def _daily_sections_from_items(channel: str, items: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for item in items:
        grouped.setdefault(str(item.get("category") or "other"), []).append(item)
    sections = []
    for category in _daily_category_order(channel):
        if category in grouped:
            sections.append(
                {
                    "category": category,
                    "label": _category_label(category),
                    "items": grouped.pop(category),
                    "count": len(grouped.get(category, [])),
                }
            )
            sections[-1]["count"] = len(sections[-1]["items"])
    for category, category_items in grouped.items():
        sections.append({"category": category, "label": _category_label(category), "items": category_items, "count": len(category_items)})
    return sections


def _lead_from_sections(sections: list[object]) -> dict[str, object] | None:
    for section in sections:
        if isinstance(section, dict) and isinstance(section.get("items"), list) and section["items"]:
            first = section["items"][0]
            return first if isinstance(first, dict) else None
    return None


def _daily_archive_item(digest: DailyDigestRecord, *, lead: dict[str, object] | None = None, story_count: int | None = None) -> dict[str, object]:
    if lead is None:
        raw = digest.sections_json or {}
        lead = raw.get("lead") if isinstance(raw.get("lead"), dict) else None
        if lead is None and isinstance(raw.get("highlights"), list) and raw["highlights"]:
            first = raw["highlights"][0]
            lead = first if isinstance(first, dict) else None
    if story_count is None:
        raw = digest.sections_json or {}
        if isinstance(raw.get("stats"), dict):
            story_count = int(raw["stats"].get("storyCount") or 0)
        elif isinstance(raw.get("highlights"), list):
            story_count = len(raw["highlights"])
        else:
            story_count = 0
    return {
        "id": str(digest.id),
        "channel": digest.channel,
        "date": digest.digest_date.isoformat(),
        "title": digest.title,
        "leadTitle": str(lead.get("title")) if isinstance(lead, dict) and lead.get("title") else "",
        "storyCount": story_count,
        "published": digest.published,
        "generatedAt": _iso(digest.generated_at),
    }


def _daily_category_order(channel: str) -> list[str]:
    if channel == "amazon":
        return [
            "policy",
            "account_health",
            "fba_logistics",
            "ads_ppc",
            "listing_seo",
            "fees_margin",
            "product_research",
            "tools",
            "compliance_trade",
        ]
    return ["ai_models", "ai_products", "industry", "papers", "agent_tools", "monetization"]


def _category_label(category: str) -> str:
    labels = {
        "ai_models": "AI 模型",
        "ai_products": "AI 产品",
        "industry": "行业动态",
        "papers": "论文研究",
        "agent_tools": "Agent / 工具",
        "monetization": "商业化",
        "policy": "平台政策",
        "account_health": "账号健康",
        "fba_logistics": "FBA / 物流",
        "ads_ppc": "广告 / PPC",
        "listing_seo": "Listing / SEO",
        "fees_margin": "费用 / 利润",
        "product_research": "选品研究",
        "tools": "卖家工具",
        "compliance_trade": "合规 / 贸易",
    }
    return labels.get(category, category)


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
        "sourceGroup": source.source_group if source is not None else None,
        "sourceType": source.source_type if source is not None else None,
        "sourceTier": source.tier if source is not None else None,
        "socialHandle": source.social_handle if source is not None else None,
        "windowLabel": PUBLIC_WINDOW_LABEL,
        "sourceCount": cluster.source_count,
        "memberCount": cluster.member_count,
        "firstSeenAt": _iso(cluster.first_seen_at),
        "lastSeenAt": _iso(cluster.last_seen_at),
        "mainItem": _main_item_payload(session, main_item, source),
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
                **_item_image_payload(session, item),
                "sourceId": item.source_id,
                "sourceName": source.name if source else item.source_id,
                "sourceGroup": source.source_group if source else None,
                "sourceType": source.source_type if source else None,
                "sourceTier": source.tier if source else None,
                "socialHandle": source.social_handle if source else None,
                "publishedAt": _iso(item.published_at),
                "summary": _processed_summary(item),
                "isMain": member.is_main,
                "relationScore": member.relation_score,
                "rank": _ranked_payload(ranked),
                "modelScore": _model_score_payload(score),
            }
        )
    return members


def _main_item_payload(session, item: NormalizedItemRecord | None, source: SourceRecord | None) -> dict[str, object] | None:
    if item is None:
        return None
    return {
        "id": str(item.id),
        "title": item.title_cn or item.title_original,
        "url": _safe_item_url(item, source),
        **_item_image_payload(session, item),
        "sourceId": item.source_id,
        "sourceName": source.name if source else item.source_id,
        "sourceGroup": source.source_group if source else None,
        "sourceType": source.source_type if source else None,
        "sourceTier": source.tier if source else None,
        "socialHandle": source.social_handle if source else None,
        "publishedAt": _iso(item.published_at),
        "summary": _processed_summary(item),
    }


def _item_image_payload(session, item: NormalizedItemRecord) -> dict[str, object]:
    raw = session.get(RawDocumentRecord, item.raw_document_id) if session is not None else None
    headers = raw.response_headers_json if raw is not None else {}
    image_url = str(headers.get("x-intel-image-url") or "").strip()
    if not image_url.startswith(("http://", "https://")):
        image_url = ""
    return {
        "imageUrl": image_url or None,
        "imageAlt": str(headers.get("x-intel-image-alt") or item.title_cn or item.title_original),
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
        audit_log(
            request,
            session,
            action="daily.publish" if published else "daily.unpublish",
            target_type="daily_digest",
            target_id=digest.id,
        )
        session.commit()
        session.refresh(digest)
        return {"dailyDigest": _daily_digest_payload(digest)}


def _quality_channel_payload(session, *, channel: str, started_at: datetime) -> dict[str, object]:
    metrics = _quality_metrics(session, channel=channel, started_at=started_at)
    return {
        "channel": channel,
        "metrics": metrics,
        "conversion": {
            "fetchSuccessRate": _ratio(metrics["successfulFetchRuns"], metrics["fetchRuns"]),
            "screenAcceptRate": _ratio(metrics["acceptedScreenings"], metrics["screenedItems"]),
            "selectedRate": _ratio(metrics["selectedItems"], metrics["scoredItems"]),
            "approvedRate": _ratio(metrics["approvedEvents"], metrics["eventClusters"]),
        },
        "bottlenecks": _quality_bottlenecks(metrics),
        "rejectionReasons": _quality_rejection_reasons(session, channel=channel, started_at=started_at),
        "rejectionSamples": _quality_rejection_samples(session, channel=channel, started_at=started_at),
        "categoryBreakdown": _quality_category_breakdown(session, channel=channel, started_at=started_at),
        "sourceContributions": _quality_source_contributions(session, channel=channel, started_at=started_at),
    }


def _quality_metrics(session, *, channel: str, started_at: datetime) -> dict[str, int]:
    return {
        "sourceCount": _count(session, select(func.count()).select_from(SourceRecord).where(SourceRecord.channel == channel)),
        "enabledSourceCount": _count(
            session,
            select(func.count()).select_from(SourceRecord).where(SourceRecord.channel == channel, SourceRecord.enabled.is_(True)),
        ),
        "fetchRuns": _count(
            session,
            select(func.count())
            .select_from(FetchRunRecord)
            .join(SourceRecord, SourceRecord.id == FetchRunRecord.source_id)
            .where(SourceRecord.channel == channel, FetchRunRecord.started_at >= started_at),
        ),
        "successfulFetchRuns": _count(
            session,
            select(func.count())
            .select_from(FetchRunRecord)
            .join(SourceRecord, SourceRecord.id == FetchRunRecord.source_id)
            .where(
                SourceRecord.channel == channel,
                FetchRunRecord.started_at >= started_at,
                FetchRunRecord.status == "succeeded",
            ),
        ),
        "rawDocuments": _count(
            session,
            select(func.count())
            .select_from(RawDocumentRecord)
            .join(SourceRecord, SourceRecord.id == RawDocumentRecord.source_id)
            .where(SourceRecord.channel == channel, RawDocumentRecord.fetched_at >= started_at),
        ),
        "screenedItems": _count(
            session,
            _screening_count_stmt(channel=channel, started_at=started_at),
        ),
        "acceptedScreenings": _count(
            session,
            _screening_count_stmt(channel=channel, started_at=started_at).where(
                RawScreeningResultRecord.screen_status == "accepted"
            ),
        ),
        "rejectedScreenings": _count(
            session,
            _screening_count_stmt(channel=channel, started_at=started_at).where(
                RawScreeningResultRecord.screen_status == "rejected"
            ),
        ),
        "normalizedItems": _count(
            session,
            select(func.count())
            .select_from(NormalizedItemRecord)
            .where(NormalizedItemRecord.channel == channel, NormalizedItemRecord.fetched_at >= started_at),
        ),
        "scoredItems": _count(
            session,
            select(func.count())
            .select_from(ModelScoreRecord)
            .join(NormalizedItemRecord, NormalizedItemRecord.id == ModelScoreRecord.item_id)
            .where(NormalizedItemRecord.channel == channel, ModelScoreRecord.created_at >= started_at),
        ),
        "rankedItems": _count(
            session,
            select(func.count())
            .select_from(RankedItemRecord)
            .join(NormalizedItemRecord, NormalizedItemRecord.id == RankedItemRecord.item_id)
            .where(NormalizedItemRecord.channel == channel, RankedItemRecord.created_at >= started_at),
        ),
        "selectedItems": _count(
            session,
            select(func.count())
            .select_from(RankedItemRecord)
            .join(NormalizedItemRecord, NormalizedItemRecord.id == RankedItemRecord.item_id)
            .where(
                NormalizedItemRecord.channel == channel,
                RankedItemRecord.created_at >= started_at,
                RankedItemRecord.selected.is_(True),
            ),
        ),
        "eventClusters": _count(
            session,
            select(func.count())
            .select_from(EventClusterRecord)
            .where(EventClusterRecord.channel == channel, EventClusterRecord.last_seen_at >= started_at),
        ),
        "approvedEvents": _count(
            session,
            select(func.count())
            .select_from(EventClusterRecord)
            .where(
                EventClusterRecord.channel == channel,
                EventClusterRecord.last_seen_at >= started_at,
                EventClusterRecord.review_status == "approved",
            ),
        ),
        "publicSelectedEvents": _count(
            session,
            select(func.count())
            .select_from(EventClusterRecord)
            .where(
                EventClusterRecord.channel == channel,
                EventClusterRecord.last_seen_at >= started_at,
                EventClusterRecord.review_status == "approved",
            )
            .where(
                exists()
                .where(RankedItemRecord.item_id == EventClusterRecord.main_item_id)
                .where(RankedItemRecord.selected.is_(True))
            ),
        ),
    }


def _screening_count_stmt(*, channel: str, started_at: datetime):
    return (
        select(func.count())
        .select_from(RawScreeningResultRecord)
        .join(RawDocumentRecord, RawDocumentRecord.id == RawScreeningResultRecord.raw_document_id)
        .join(SourceRecord, SourceRecord.id == RawDocumentRecord.source_id)
        .where(SourceRecord.channel == channel, RawScreeningResultRecord.created_at >= started_at)
    )


def _quality_rejection_reasons(session, *, channel: str, started_at: datetime) -> list[dict[str, object]]:
    rows = session.execute(
        select(
            RawScreeningResultRecord.reason_code,
            RawScreeningResultRecord.screen_bucket,
            func.max(RawScreeningResultRecord.reason_cn),
            func.count(),
        )
        .join(RawDocumentRecord, RawDocumentRecord.id == RawScreeningResultRecord.raw_document_id)
        .join(SourceRecord, SourceRecord.id == RawDocumentRecord.source_id)
        .where(
            SourceRecord.channel == channel,
            RawScreeningResultRecord.created_at >= started_at,
            RawScreeningResultRecord.screen_status == "rejected",
        )
        .group_by(RawScreeningResultRecord.reason_code, RawScreeningResultRecord.screen_bucket)
        .order_by(func.count().desc(), RawScreeningResultRecord.reason_code)
        .limit(10)
    ).all()
    return [
        {"reasonCode": reason_code, "bucket": bucket, "reason": reason or "", "count": count}
        for reason_code, bucket, reason, count in rows
    ]


def _quality_rejection_samples(session, *, channel: str, started_at: datetime) -> list[dict[str, object]]:
    rows = session.execute(
        select(RawScreeningResultRecord, RawDocumentRecord, SourceRecord)
        .join(RawDocumentRecord, RawDocumentRecord.id == RawScreeningResultRecord.raw_document_id)
        .join(SourceRecord, SourceRecord.id == RawDocumentRecord.source_id)
        .where(
            SourceRecord.channel == channel,
            RawScreeningResultRecord.created_at >= started_at,
            RawScreeningResultRecord.screen_status == "rejected",
        )
        .order_by(RawScreeningResultRecord.created_at.desc(), RawScreeningResultRecord.id.desc())
        .limit(20)
    ).all()
    return [
        {
            "rawDocumentId": str(raw.id),
            "title": screening.title_cn,
            "summary": screening.summary_cn,
            "sourceId": source.id,
            "sourceName": source.name,
            "sourceGroup": source.source_group,
            "category": screening.category,
            "bucket": screening.screen_bucket,
            "reasonCode": screening.reason_code,
            "reason": screening.reason_cn,
            "confidenceScore": screening.confidence_score,
            "createdAt": _iso(screening.created_at),
            "url": raw.url or raw.canonical_url,
        }
        for screening, raw, source in rows
    ]


def _quality_category_breakdown(session, *, channel: str, started_at: datetime) -> list[dict[str, object]]:
    categories: dict[str, dict[str, object]] = {}
    scored_rows = session.execute(
        select(ModelScoreRecord.category, func.count())
        .join(NormalizedItemRecord, NormalizedItemRecord.id == ModelScoreRecord.item_id)
        .where(NormalizedItemRecord.channel == channel, ModelScoreRecord.created_at >= started_at)
        .group_by(ModelScoreRecord.category)
    ).all()
    for category, scored_count in scored_rows:
        categories[str(category)] = {
            "category": str(category),
            "scoredItems": scored_count,
            "selectedItems": 0,
            "approvedEvents": 0,
        }
    selected_rows = session.execute(
        select(ModelScoreRecord.category, func.count())
        .join(NormalizedItemRecord, NormalizedItemRecord.id == ModelScoreRecord.item_id)
        .join(RankedItemRecord, RankedItemRecord.item_id == NormalizedItemRecord.id)
        .where(
            NormalizedItemRecord.channel == channel,
            RankedItemRecord.created_at >= started_at,
            RankedItemRecord.selected.is_(True),
        )
        .group_by(ModelScoreRecord.category)
    ).all()
    for category, selected_count in selected_rows:
        row = categories.setdefault(
            str(category),
            {"category": str(category), "scoredItems": 0, "selectedItems": 0, "approvedEvents": 0},
        )
        row["selectedItems"] = selected_count
    approved_rows = session.execute(
        select(EventClusterRecord.category, func.count())
        .where(
            EventClusterRecord.channel == channel,
            EventClusterRecord.last_seen_at >= started_at,
            EventClusterRecord.review_status == "approved",
        )
        .group_by(EventClusterRecord.category)
    ).all()
    for category, approved_count in approved_rows:
        row = categories.setdefault(
            str(category),
            {"category": str(category), "scoredItems": 0, "selectedItems": 0, "approvedEvents": 0},
        )
        row["approvedEvents"] = approved_count
    return sorted(categories.values(), key=lambda item: (-int(item["scoredItems"]), str(item["category"])))


def _quality_source_contributions(session, *, channel: str, started_at: datetime) -> list[dict[str, object]]:
    sources = session.execute(
        select(SourceRecord, SourceStateRecord)
        .join(SourceStateRecord, SourceStateRecord.source_id == SourceRecord.id)
        .where(SourceRecord.channel == channel, SourceRecord.enabled.is_(True))
        .order_by(SourceRecord.authority_weight.desc(), SourceRecord.id)
    ).all()
    rows = []
    for source, state in sources:
        raw_count = _count(
            session,
            select(func.count())
            .select_from(RawDocumentRecord)
            .where(RawDocumentRecord.source_id == source.id, RawDocumentRecord.fetched_at >= started_at),
        )
        accepted_count = _count(
            session,
            select(func.count())
            .select_from(RawScreeningResultRecord)
            .join(RawDocumentRecord, RawDocumentRecord.id == RawScreeningResultRecord.raw_document_id)
            .where(
                RawDocumentRecord.source_id == source.id,
                RawScreeningResultRecord.created_at >= started_at,
                RawScreeningResultRecord.screen_status == "accepted",
            ),
        )
        selected_count = _count(
            session,
            select(func.count())
            .select_from(RankedItemRecord)
            .join(NormalizedItemRecord, NormalizedItemRecord.id == RankedItemRecord.item_id)
            .where(
                NormalizedItemRecord.source_id == source.id,
                RankedItemRecord.created_at >= started_at,
                RankedItemRecord.selected.is_(True),
            ),
        )
        rows.append(
            {
                "sourceId": source.id,
                "sourceName": source.name,
                "sourceGroup": source.source_group,
                "collectionStatus": source.collection_status,
                "tier": source.tier,
                "healthScore": state.health_score,
                "errorStreak": state.error_streak,
                "rawDocuments": raw_count,
                "acceptedScreenings": accepted_count,
                "selectedItems": selected_count,
            }
        )
    return sorted(rows, key=lambda item: (-int(item["rawDocuments"]), -int(item["acceptedScreenings"]), item["sourceId"]))[:12]


def _quality_bottlenecks(metrics: dict[str, int]) -> list[str]:
    if metrics["fetchRuns"] == 0:
        return ["最近窗口内没有抓取运行，先检查小时级定时任务和启用信源。"]
    if metrics["rawDocuments"] == 0:
        return ["抓取运行存在，但没有当天原始条目，优先扩充当天高频更新信源。"]
    if metrics["acceptedScreenings"] == 0:
        return ["已有原始条目，但 AI 初筛没有通过项，优先检查频道相关性规则和信源匹配度。"]
    if metrics["selectedItems"] == 0:
        return ["已有 AI 初筛通过项，但没有精选，优先校准精筛分数、置信度和精选阈值。"]
    if metrics["approvedEvents"] < metrics["eventClusters"]:
        return ["已有事件簇，但自动评审未全部通过，优先检查中文字段、推荐理由和 provider 约束。"]
    return ["抓取、初筛、精筛、精选和自动发布链路均有产出，继续扩充高质量信源。"]


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _count(session, stmt) -> int:
    return int(session.scalar(stmt) or 0)


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()
