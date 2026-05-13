from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from intel_engine.models import DailyDigestRecord, EventClusterRecord, ModelScoreRecord, NormalizedItemRecord, utc_now


@dataclass(frozen=True)
class DailyDigestResult:
    digest_id: int
    created: bool
    event_count: int


def generate_daily_digest(
    session: Session,
    *,
    channel: str,
    digest_date: date,
    strategy_version: str,
) -> DailyDigestResult:
    start = datetime.combine(digest_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(digest_date, time.max, tzinfo=timezone.utc)
    clusters = list(
        session.scalars(
            select(EventClusterRecord)
            .where(EventClusterRecord.channel == channel)
            .where(EventClusterRecord.cluster_score >= 70)
            .where(EventClusterRecord.last_seen_at >= start)
            .where(EventClusterRecord.last_seen_at <= end)
            .order_by(EventClusterRecord.cluster_score.desc(), EventClusterRecord.last_seen_at.desc())
        ).all()
    )
    sections = {
        "highlights": [
            {
                "eventId": str(cluster.id),
                "title": _cluster_title(session, cluster),
                "summary": _cluster_summary(session, cluster),
                "entryReason": _cluster_reason(session, cluster),
                "category": _cluster_category(session, cluster),
                "score": cluster.cluster_score,
                "sourceCount": cluster.source_count,
                "memberCount": cluster.member_count,
                "lastSeenAt": cluster.last_seen_at.isoformat(),
            }
            for cluster in clusters
        ]
    }
    existing = session.scalar(
        select(DailyDigestRecord)
        .where(DailyDigestRecord.channel == channel)
        .where(DailyDigestRecord.digest_date == digest_date)
        .where(DailyDigestRecord.strategy_version == strategy_version)
        .limit(1)
    )
    created = existing is None
    digest = existing or DailyDigestRecord(
        channel=channel,
        digest_date=digest_date,
        strategy_version=strategy_version,
        title=f"{channel.upper()} 日报",
        sections_json=sections,
        published=True,
    )
    digest.generated_at = utc_now()
    digest.title = f"{channel.upper()} 日报"
    digest.sections_json = sections
    digest.published = True
    if existing is None:
        session.add(digest)
    session.flush()
    return DailyDigestResult(digest_id=digest.id, created=created, event_count=len(clusters))


def _cluster_main_item(session: Session, cluster: EventClusterRecord) -> NormalizedItemRecord | None:
    if cluster.main_item_id is None:
        return None
    return session.get(NormalizedItemRecord, cluster.main_item_id)


def _cluster_score(session: Session, cluster: EventClusterRecord) -> ModelScoreRecord | None:
    item = _cluster_main_item(session, cluster)
    if item is None:
        return None
    return session.scalar(select(ModelScoreRecord).where(ModelScoreRecord.item_id == item.id).limit(1))


def _cluster_title(session: Session, cluster: EventClusterRecord) -> str:
    item = _cluster_main_item(session, cluster)
    if item is not None and item.title_cn:
        return item.title_cn
    return cluster.canonical_title


def _cluster_summary(session: Session, cluster: EventClusterRecord) -> str:
    item = _cluster_main_item(session, cluster)
    if item is not None and item.summary_cn:
        return item.summary_cn
    return "待 AI 处理后生成中文摘要。"


def _cluster_reason(session: Session, cluster: EventClusterRecord) -> str:
    score = _cluster_score(session, cluster)
    if score is not None and score.reason:
        return score.reason
    return "待 AI 处理后生成推荐理由。"


def _cluster_category(session: Session, cluster: EventClusterRecord) -> str:
    score = _cluster_score(session, cluster)
    if score is not None and score.category:
        return score.category
    return cluster.category
