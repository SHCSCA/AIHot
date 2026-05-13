from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import DateTime, Float, Integer, String, Text, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from intel_engine.channel_config import PROJECT_ROOT
from intel_engine.normalizer import NormalizedItem


DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "intel_engine.sqlite3"


class Base(DeclarativeBase):
    pass


class ItemRecord(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(32), index=True)
    source_id: Mapped[str] = mapped_column(String(128), index=True)
    raw_title: Mapped[str] = mapped_column(Text)
    normalized_title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(String(255))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    raw_excerpt: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64), index=True)
    keywords: Mapped[str] = mapped_column(Text, default="")
    source_score: Mapped[float] = mapped_column(Float)
    relevance_score: Mapped[float] = mapped_column(Float)
    impact_score: Mapped[float] = mapped_column(Float)
    novelty_score: Mapped[float] = mapped_column(Float)
    actionability_score: Mapped[float] = mapped_column(Float)
    freshness_score: Mapped[float] = mapped_column(Float)
    final_score: Mapped[float] = mapped_column(Float, index=True)
    entry_reason: Mapped[str] = mapped_column(Text)
    suggested_action: Mapped[str] = mapped_column(Text)
    seller_action_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class UpsertResult:
    item_id: int
    created: bool


@dataclass(frozen=True)
class StoredItem:
    id: int
    channel: str
    source_id: str
    raw_title: str
    normalized_title: str
    url: str
    source_name: str
    published_at: datetime
    content_hash: str
    raw_excerpt: str
    summary: str
    category: str
    keywords: tuple[str, ...]
    source_score: float
    relevance_score: float
    impact_score: float
    novelty_score: float
    actionability_score: float
    freshness_score: float
    final_score: float
    entry_reason: str
    suggested_action: str
    seller_action_level: str | None


def create_engine_for_path(db_path: str | Path = DEFAULT_DB_PATH) -> Engine:
    path = Path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def _record_to_stored_item(record: ItemRecord) -> StoredItem:
    keywords = tuple(item for item in record.keywords.split(",") if item)
    return StoredItem(
        id=record.id,
        channel=record.channel,
        source_id=record.source_id,
        raw_title=record.raw_title,
        normalized_title=record.normalized_title,
        url=record.url,
        source_name=record.source_name,
        published_at=record.published_at,
        content_hash=record.content_hash,
        raw_excerpt=record.raw_excerpt,
        summary=record.summary,
        category=record.category,
        keywords=keywords,
        source_score=record.source_score,
        relevance_score=record.relevance_score,
        impact_score=record.impact_score,
        novelty_score=record.novelty_score,
        actionability_score=record.actionability_score,
        freshness_score=record.freshness_score,
        final_score=record.final_score,
        entry_reason=record.entry_reason,
        suggested_action=record.suggested_action,
        seller_action_level=record.seller_action_level,
    )


class ItemRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def upsert_item(self, item: NormalizedItem) -> UpsertResult:
        with Session(self.engine) as session:
            existing = session.scalar(select(ItemRecord).where(ItemRecord.content_hash == item.content_hash))
            if existing:
                return UpsertResult(item_id=existing.id, created=False)

            record = ItemRecord(
                channel=item.channel,
                source_id=item.source_id,
                raw_title=item.raw_title,
                normalized_title=item.normalized_title,
                url=item.url,
                source_name=item.source_name,
                published_at=item.published_at,
                content_hash=item.content_hash,
                raw_excerpt=item.raw_excerpt,
                summary=item.summary,
                category=item.category,
                keywords=",".join(item.keywords),
                source_score=item.source_score,
                relevance_score=item.relevance_score,
                impact_score=item.impact_score,
                novelty_score=item.novelty_score,
                actionability_score=item.actionability_score,
                freshness_score=item.freshness_score,
                final_score=item.final_score,
                entry_reason=item.entry_reason,
                suggested_action=item.suggested_action,
                seller_action_level=item.seller_action_level,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return UpsertResult(item_id=record.id, created=True)

    def list_items(
        self,
        channel: str | None = None,
        category: str | None = None,
        take: int = 20,
        mode: str = "all",
    ) -> list[StoredItem]:
        stmt = select(ItemRecord)
        if channel:
            stmt = stmt.where(ItemRecord.channel == channel)
        if category:
            stmt = stmt.where(ItemRecord.category == category)
        if mode == "selected":
            stmt = stmt.where(ItemRecord.final_score >= 70)
        stmt = stmt.order_by(ItemRecord.published_at.desc(), ItemRecord.id.desc()).limit(take)

        with Session(self.engine) as session:
            return [_record_to_stored_item(record) for record in session.scalars(stmt).all()]
