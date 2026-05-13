from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from intel_engine.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UtcDateTime(TypeDecorator[datetime]):
    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(DateTime(timezone=True))

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class SourceRecord(TimestampMixin, Base):
    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint("tier in ('T1', 'T1.5', 'T2', 'T3')", name="ck_sources_tier"),
        CheckConstraint(
            "source_type in ('rss', 'html', 'api', 'github', 'docs', 'social', 'forum')",
            name="ck_sources_source_type",
        ),
        CheckConstraint(
            "fetch_adapter in ('rss', 'http_article', 'github', 'api', 'playwright')",
            name="ck_sources_fetch_adapter",
        ),
        CheckConstraint("visibility in ('public', 'internal', 'hidden')", name="ck_sources_visibility"),
        CheckConstraint("authority_weight >= 0 and authority_weight <= 100", name="ck_sources_authority_weight"),
        CheckConstraint("noise_level >= 0 and noise_level <= 1", name="ck_sources_noise_level"),
        CheckConstraint("fetch_interval_minutes > 0", name="ck_sources_fetch_interval"),
        Index("ix_sources_channel_enabled", "channel", "enabled"),
        Index("ix_sources_tier", "tier"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    channel: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    tier: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    region: Mapped[str] = mapped_column(String(64), nullable=False)
    marketplace: Mapped[str | None] = mapped_column(String(32), nullable=True)
    authority_weight: Mapped[float] = mapped_column(Float, nullable=False)
    noise_level: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fetch_adapter: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_type: Mapped[str] = mapped_column(String(64), nullable=False)
    default_categories: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    fetch_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    visibility: Mapped[str] = mapped_column(String(32), default="public", nullable=False)
    source_group: Mapped[str] = mapped_column(String(32), default="media", nullable=False)
    contributor_no: Mapped[str | None] = mapped_column(String(32), nullable=True)
    social_handle: Mapped[str | None] = mapped_column(String(128), nullable=True)
    collection_status: Mapped[str] = mapped_column(String(32), default="collectable", nullable=False)
    free_access: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SourceStateRecord(Base):
    __tablename__ = "source_states"
    __table_args__ = (
        CheckConstraint("duplicate_ratio >= 0 and duplicate_ratio <= 1", name="ck_source_states_duplicate_ratio"),
        CheckConstraint("noise_ratio >= 0 and noise_ratio <= 1", name="ck_source_states_noise_ratio"),
        CheckConstraint("health_score >= 0 and health_score <= 100", name="ck_source_states_health_score"),
    )

    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True)
    last_success_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    error_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_fetch_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, index=True, nullable=False)
    backoff_until: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    avg_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    items_per_run: Mapped[float | None] = mapped_column(Float, nullable=True)
    duplicate_ratio: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    noise_ratio: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    health_score: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, onupdate=utc_now, nullable=False)


class FetchJobRecord(TimestampMixin, Base):
    __tablename__ = "fetch_jobs"
    __table_args__ = (
        CheckConstraint(
            "status in ('pending', 'locked', 'running', 'succeeded', 'failed', 'cancelled', 'dead')",
            name="ck_fetch_jobs_status",
        ),
        CheckConstraint("priority >= 0", name="ck_fetch_jobs_priority"),
        CheckConstraint("attempt_count >= 0", name="ck_fetch_jobs_attempt_count"),
        Index("ix_fetch_jobs_claim", "status", "run_after", "priority"),
        Index("ix_fetch_jobs_source_id", "source_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    run_after: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class FetchRunRecord(Base):
    __tablename__ = "fetch_runs"
    __table_args__ = (
        CheckConstraint("status in ('started', 'succeeded', 'failed', 'partial')", name="ck_fetch_runs_status"),
        CheckConstraint("bytes_received >= 0", name="ck_fetch_runs_bytes_received"),
        CheckConstraint("item_count >= 0", name="ck_fetch_runs_item_count"),
        Index("ix_fetch_runs_source_started", "source_id", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("fetch_jobs.id", ondelete="SET NULL"), nullable=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="started", nullable=False)
    started_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bytes_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class RawDocumentRecord(Base):
    __tablename__ = "raw_documents"
    __table_args__ = (
        UniqueConstraint("source_id", "content_hash", name="uq_raw_documents_source_hash"),
        Index("ix_raw_documents_source_fetched", "source_id", "fetched_at"),
        Index("ix_raw_documents_canonical_url", "canonical_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fetch_run_id: Mapped[int] = mapped_column(ForeignKey("fetch_runs.id", ondelete="CASCADE"), nullable=False)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_headers_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)


class RawScreeningResultRecord(Base):
    __tablename__ = "raw_screening_results"
    __table_args__ = (
        UniqueConstraint("raw_document_id", "strategy_version", name="uq_raw_screening_results_raw_strategy"),
        CheckConstraint(
            "screen_status in ('accepted', 'rejected', 'failed')",
            name="ck_raw_screening_results_status",
        ),
        CheckConstraint(
            "screen_bucket in ('core', 'related', 'watch', 'irrelevant', 'invalid')",
            name="ck_raw_screening_results_bucket",
        ),
        CheckConstraint("relevance_score >= 0 and relevance_score <= 100", name="ck_raw_screening_results_relevance"),
        CheckConstraint("confidence_score >= 0 and confidence_score <= 100", name="ck_raw_screening_results_confidence"),
        Index("ix_raw_screening_results_status_created", "screen_status", "created_at"),
        Index("ix_raw_screening_results_raw_document", "raw_document_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_document_id: Mapped[int] = mapped_column(ForeignKey("raw_documents.id", ondelete="CASCADE"), nullable=False)
    strategy_version: Mapped[str] = mapped_column(ForeignKey("strategy_versions.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    screen_status: Mapped[str] = mapped_column(String(32), nullable=False)
    screen_bucket: Mapped[str] = mapped_column(String(32), nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    title_cn: Mapped[str] = mapped_column(Text, nullable=False)
    summary_cn: Mapped[str] = mapped_column(Text, nullable=False)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_cn: Mapped[str] = mapped_column(Text, default="", nullable=False)
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)


class NormalizedItemRecord(TimestampMixin, Base):
    __tablename__ = "normalized_items"
    __table_args__ = (
        UniqueConstraint("channel", "content_hash", name="uq_normalized_items_channel_hash"),
        Index("ix_normalized_items_channel_published", "channel", "published_at"),
        Index("ix_normalized_items_source_id", "source_id"),
        Index("ix_normalized_items_canonical_url", "canonical_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    raw_document_id: Mapped[int] = mapped_column(ForeignKey("raw_documents.id", ondelete="CASCADE"), nullable=False)
    title_original: Mapped[str] = mapped_column(Text, nullable=False)
    title_cn: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    summary_original: Mapped[str] = mapped_column(Text, default="", nullable=False)
    summary_cn: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class StrategyVersionRecord(Base):
    __tablename__ = "strategy_versions"
    __table_args__ = (
        CheckConstraint("status in ('draft', 'active', 'retired')", name="ck_strategy_versions_status"),
        Index("ix_strategy_versions_channel_status", "channel", "status"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    prefilter_prompt_version: Mapped[str] = mapped_column(String(128), nullable=False)
    score_prompt_version: Mapped[str] = mapped_column(String(128), nullable=False)
    rank_formula_version: Mapped[str] = mapped_column(String(128), nullable=False)
    thresholds_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    model_config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


class PrefilterResultRecord(Base):
    __tablename__ = "prefilter_results"
    __table_args__ = (
        CheckConstraint("bucket in ('relevant', 'maybe', 'irrelevant')", name="ck_prefilter_results_bucket"),
        Index("ix_prefilter_results_item_strategy", "item_id", "strategy_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("normalized_items.id", ondelete="CASCADE"), nullable=False)
    strategy_version: Mapped[str] = mapped_column(ForeignKey("strategy_versions.id"), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    bucket: Mapped[str] = mapped_column(String(32), nullable=False)
    is_relevant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)


class ModelScoreRecord(Base):
    __tablename__ = "model_scores"
    __table_args__ = (
        CheckConstraint("relevance_score >= 0 and relevance_score <= 100", name="ck_model_scores_relevance"),
        CheckConstraint("impact_score >= 0 and impact_score <= 100", name="ck_model_scores_impact"),
        CheckConstraint("novelty_score >= 0 and novelty_score <= 100", name="ck_model_scores_novelty"),
        CheckConstraint("actionability_score >= 0 and actionability_score <= 100", name="ck_model_scores_actionability"),
        CheckConstraint("credibility_score >= 0 and credibility_score <= 100", name="ck_model_scores_credibility"),
        Index("ix_model_scores_item_strategy", "item_id", "strategy_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("normalized_items.id", ondelete="CASCADE"), nullable=False)
    strategy_version: Mapped[str] = mapped_column(ForeignKey("strategy_versions.id"), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    impact_score: Mapped[float] = mapped_column(Float, nullable=False)
    novelty_score: Mapped[float] = mapped_column(Float, nullable=False)
    actionability_score: Mapped[float] = mapped_column(Float, nullable=False)
    credibility_score: Mapped[float] = mapped_column(Float, nullable=False)
    seller_action_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)


class RankedItemRecord(Base):
    __tablename__ = "ranked_items"
    __table_args__ = (
        CheckConstraint("source_weight >= 0 and source_weight <= 100", name="ck_ranked_items_source_weight"),
        CheckConstraint("category_weight >= 0 and category_weight <= 100", name="ck_ranked_items_category_weight"),
        CheckConstraint("freshness_weight >= 0 and freshness_weight <= 100", name="ck_ranked_items_freshness_weight"),
        CheckConstraint("duplicate_penalty >= 0 and duplicate_penalty <= 100", name="ck_ranked_items_duplicate_penalty"),
        CheckConstraint(
            "channel_impact_weight >= 0 and channel_impact_weight <= 100",
            name="ck_ranked_items_channel_impact",
        ),
        CheckConstraint("final_score >= 0 and final_score <= 100", name="ck_ranked_items_final_score"),
        CheckConstraint("threshold_used >= 0 and threshold_used <= 100", name="ck_ranked_items_threshold"),
        Index("ix_ranked_items_selected_score", "selected", "final_score"),
    )

    item_id: Mapped[int] = mapped_column(ForeignKey("normalized_items.id", ondelete="CASCADE"), primary_key=True)
    strategy_version: Mapped[str] = mapped_column(ForeignKey("strategy_versions.id"), primary_key=True)
    source_weight: Mapped[float] = mapped_column(Float, nullable=False)
    category_weight: Mapped[float] = mapped_column(Float, nullable=False)
    freshness_weight: Mapped[float] = mapped_column(Float, nullable=False)
    duplicate_penalty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    channel_impact_weight: Mapped[float] = mapped_column(Float, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    threshold_used: Mapped[float] = mapped_column(Float, nullable=False)
    selection_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)


class EventClusterRecord(TimestampMixin, Base):
    __tablename__ = "event_clusters"
    __table_args__ = (
        CheckConstraint("member_count >= 0", name="ck_event_clusters_member_count"),
        CheckConstraint("source_count >= 0", name="ck_event_clusters_source_count"),
        CheckConstraint("cluster_score >= 0 and cluster_score <= 100", name="ck_event_clusters_cluster_score"),
        CheckConstraint(
            "review_status in ('pending', 'approved', 'rejected')",
            name="ck_event_clusters_review_status",
        ),
        Index("ix_event_clusters_channel_score", "channel", "cluster_score"),
        Index("ix_event_clusters_last_seen", "last_seen_at"),
        Index("ix_event_clusters_review_status", "review_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    canonical_title: Mapped[str] = mapped_column(Text, nullable=False)
    main_item_id: Mapped[int | None] = mapped_column(ForeignKey("normalized_items.id", ondelete="SET NULL"), nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    member_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cluster_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


class ClusterMemberRecord(Base):
    __tablename__ = "cluster_members"
    __table_args__ = (
        CheckConstraint("relation_score >= 0 and relation_score <= 100", name="ck_cluster_members_relation_score"),
        Index("ix_cluster_members_source_id", "source_id"),
    )

    cluster_id: Mapped[int] = mapped_column(ForeignKey("event_clusters.id", ondelete="CASCADE"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("normalized_items.id", ondelete="CASCADE"), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    relation_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_main: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)


class FeedbackEventRecord(Base):
    __tablename__ = "feedback_events"
    __table_args__ = (
        CheckConstraint(
            "feedback_type in ('false_positive', 'false_negative', 'promote', 'demote', 'category_fix')",
            name="ck_feedback_events_feedback_type",
        ),
        Index("ix_feedback_events_channel_created", "channel", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("normalized_items.id", ondelete="SET NULL"), nullable=True)
    cluster_id: Mapped[int | None] = mapped_column(ForeignKey("event_clusters.id", ondelete="SET NULL"), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    feedback_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    actor: Mapped[str] = mapped_column(String(128), default="system", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)


class DailyDigestRecord(Base):
    __tablename__ = "daily_digests"
    __table_args__ = (
        UniqueConstraint("channel", "digest_date", "strategy_version", name="uq_daily_digests_channel_date_strategy"),
        Index("ix_daily_digests_channel_date", "channel", "digest_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    digest_date: Mapped[date] = mapped_column(Date, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)
    strategy_version: Mapped[str] = mapped_column(ForeignKey("strategy_versions.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    sections_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)


class EvaluationRunRecord(Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (
        CheckConstraint("status in ('pending', 'running', 'succeeded', 'failed')", name="ck_evaluation_runs_status"),
        Index("ix_evaluation_runs_channel_created", "channel", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    strategy_version: Mapped[str] = mapped_column(ForeignKey("strategy_versions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    request_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


class PipelineRunRecord(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (
        CheckConstraint("status in ('running', 'succeeded', 'failed')", name="ck_pipeline_runs_status"),
        Index("ix_pipeline_runs_started_at", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    worker_id: Mapped[str] = mapped_column(String(128), nullable=False)
    limit: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    scheduled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    claimed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    succeeded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    raw_documents_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    normalized_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ranked_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clusters: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
