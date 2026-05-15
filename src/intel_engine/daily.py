from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from intel_engine.models import DailyDigestRecord, EventClusterRecord, ModelScoreRecord, NormalizedItemRecord, RankedItemRecord, utc_now
from intel_engine.review import ROLLING_WINDOW_HOURS


@dataclass(frozen=True)
class DailyDigestResult:
    digest_id: int | None
    created: bool
    event_count: int


def generate_daily_digest(
    session: Session,
    *,
    channel: str,
    digest_date: date,
    strategy_version: str,
    now: datetime | None = None,
    auto_publish: bool = True,
) -> DailyDigestResult:
    if now is None:
        start = datetime.combine(digest_date, time.min, tzinfo=timezone.utc)
        end = datetime.combine(digest_date, time.max, tzinfo=timezone.utc)
    else:
        end = now
        start = now - timedelta(hours=ROLLING_WINDOW_HOURS)
    clusters = list(
        session.scalars(
            select(EventClusterRecord)
            .join(RankedItemRecord, RankedItemRecord.item_id == EventClusterRecord.main_item_id)
            .where(EventClusterRecord.channel == channel)
            .where(EventClusterRecord.review_status == "approved")
            .where(RankedItemRecord.selected.is_(True))
            .where(EventClusterRecord.last_seen_at >= start)
            .where(EventClusterRecord.last_seen_at <= end)
            .order_by(EventClusterRecord.cluster_score.desc(), EventClusterRecord.last_seen_at.desc())
        ).all()
    )
    highlights = [
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
    section_list = _sections_for_channel(channel, highlights)
    lead = highlights[0] if highlights else None
    sections = {
        "highlights": highlights,
        "lead": lead,
        "sections": section_list,
        "archiveItem": {
            "date": digest_date.isoformat(),
            "leadTitle": str(lead.get("title")) if lead else "",
            "storyCount": len(highlights),
        },
        "stats": {"storyCount": len(highlights), "sectionCount": len(section_list)},
    }
    existing = session.scalar(
        select(DailyDigestRecord)
        .where(DailyDigestRecord.channel == channel)
        .where(DailyDigestRecord.digest_date == digest_date)
        .where(DailyDigestRecord.strategy_version == strategy_version)
        .limit(1)
    )
    if not clusters:
        if existing is not None:
            existing.sections_json = {"highlights": []}
            existing.published = False
            existing.published_by = None
            existing.published_at = None
            existing.generated_at = utc_now()
            session.flush()
            return DailyDigestResult(digest_id=existing.id, created=False, event_count=0)
        return DailyDigestResult(digest_id=None, created=False, event_count=0)
    created = existing is None
    digest = existing or DailyDigestRecord(
        channel=channel,
        digest_date=digest_date,
        strategy_version=strategy_version,
        title=f"{channel.upper()} 日报",
        sections_json=sections,
        published=auto_publish,
    )
    digest.generated_at = utc_now()
    digest.title = f"{channel.upper()} 日报"
    digest.sections_json = sections
    digest.published = auto_publish
    digest.published_by = "ai-publisher" if auto_publish else None
    digest.published_at = utc_now() if auto_publish else None
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


def _sections_for_channel(channel: str, highlights: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for item in highlights:
        grouped.setdefault(str(item.get("category") or "other"), []).append(item)
    sections: list[dict[str, object]] = []
    for category in _category_order(channel):
        items = grouped.pop(category, [])
        if items:
            sections.append({"category": category, "label": _category_label(category), "count": len(items), "items": items})
    for category, items in grouped.items():
        sections.append({"category": category, "label": _category_label(category), "count": len(items), "items": items})
    return sections


def _category_order(channel: str) -> list[str]:
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
