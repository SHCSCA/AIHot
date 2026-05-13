"""create production intelligence schema

Revision ID: 20260511_0001
Revises:
Create Date: 2026-05-11 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260511_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("region", sa.String(length=64), nullable=False),
        sa.Column("marketplace", sa.String(length=32), nullable=True),
        sa.Column("authority_weight", sa.Float(), nullable=False),
        sa.Column("noise_level", sa.Float(), nullable=False),
        sa.Column("fetch_adapter", sa.String(length=64), nullable=False),
        sa.Column("parser_type", sa.String(length=64), nullable=False),
        sa.Column("default_categories", sa.JSON(), nullable=False),
        sa.Column("fetch_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("visibility", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("authority_weight >= 0 and authority_weight <= 100", name="ck_sources_authority_weight"),
        sa.CheckConstraint(
            "fetch_adapter in ('rss', 'http_article', 'github', 'api', 'playwright')",
            name="ck_sources_fetch_adapter",
        ),
        sa.CheckConstraint("fetch_interval_minutes > 0", name="ck_sources_fetch_interval"),
        sa.CheckConstraint("noise_level >= 0 and noise_level <= 1", name="ck_sources_noise_level"),
        sa.CheckConstraint(
            "source_type in ('rss', 'html', 'api', 'github', 'docs', 'social', 'forum')",
            name="ck_sources_source_type",
        ),
        sa.CheckConstraint("tier in ('T1', 'T1.5', 'T2', 'T3')", name="ck_sources_tier"),
        sa.CheckConstraint("visibility in ('public', 'internal', 'hidden')", name="ck_sources_visibility"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sources_channel", "sources", ["channel"])
    op.create_index("ix_sources_channel_enabled", "sources", ["channel", "enabled"])
    op.create_index("ix_sources_tier", "sources", ["tier"])

    op.create_table(
        "strategy_versions",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("prefilter_prompt_version", sa.String(length=128), nullable=False),
        sa.Column("score_prompt_version", sa.String(length=128), nullable=False),
        sa.Column("rank_formula_version", sa.String(length=128), nullable=False),
        sa.Column("thresholds_json", sa.JSON(), nullable=False),
        sa.Column("model_config_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('draft', 'active', 'retired')", name="ck_strategy_versions_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_strategy_versions_channel_status", "strategy_versions", ["channel", "status"])

    op.create_table(
        "source_states",
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_streak", sa.Integer(), nullable=False),
        sa.Column("next_fetch_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("backoff_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("avg_latency_ms", sa.Float(), nullable=True),
        sa.Column("items_per_run", sa.Float(), nullable=True),
        sa.Column("duplicate_ratio", sa.Float(), nullable=False),
        sa.Column("noise_ratio", sa.Float(), nullable=False),
        sa.Column("health_score", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("duplicate_ratio >= 0 and duplicate_ratio <= 1", name="ck_source_states_duplicate_ratio"),
        sa.CheckConstraint("health_score >= 0 and health_score <= 100", name="ck_source_states_health_score"),
        sa.CheckConstraint("noise_ratio >= 0 and noise_ratio <= 1", name="ck_source_states_noise_ratio"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.create_index("ix_source_states_next_fetch_at", "source_states", ["next_fetch_at"])

    op.create_table(
        "fetch_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("run_after", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("attempt_count >= 0", name="ck_fetch_jobs_attempt_count"),
        sa.CheckConstraint("priority >= 0", name="ck_fetch_jobs_priority"),
        sa.CheckConstraint(
            "status in ('pending', 'locked', 'running', 'succeeded', 'failed', 'cancelled', 'dead')",
            name="ck_fetch_jobs_status",
        ),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fetch_jobs_claim", "fetch_jobs", ["status", "run_after", "priority"])
    op.create_index("ix_fetch_jobs_source_id", "fetch_jobs", ["source_id"])

    op.create_table(
        "fetch_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("bytes_received", sa.Integer(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.CheckConstraint("bytes_received >= 0", name="ck_fetch_runs_bytes_received"),
        sa.CheckConstraint("item_count >= 0", name="ck_fetch_runs_item_count"),
        sa.CheckConstraint("status in ('started', 'succeeded', 'failed', 'partial')", name="ck_fetch_runs_status"),
        sa.ForeignKeyConstraint(["job_id"], ["fetch_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fetch_runs_source_started", "fetch_runs", ["source_id", "started_at"])

    op.create_table(
        "raw_documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("fetch_run_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("response_headers_json", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["fetch_run_id"], ["fetch_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "content_hash", name="uq_raw_documents_source_hash"),
    )
    op.create_index("ix_raw_documents_canonical_url", "raw_documents", ["canonical_url"])
    op.create_index("ix_raw_documents_source_fetched", "raw_documents", ["source_id", "fetched_at"])

    op.create_table(
        "normalized_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("raw_document_id", sa.Integer(), nullable=False),
        sa.Column("title_original", sa.Text(), nullable=False),
        sa.Column("title_cn", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("summary_original", sa.Text(), nullable=False),
        sa.Column("summary_cn", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["raw_document_id"], ["raw_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel", "content_hash", name="uq_normalized_items_channel_hash"),
    )
    op.create_index("ix_normalized_items_canonical_url", "normalized_items", ["canonical_url"])
    op.create_index("ix_normalized_items_channel", "normalized_items", ["channel"])
    op.create_index("ix_normalized_items_channel_published", "normalized_items", ["channel", "published_at"])
    op.create_index("ix_normalized_items_source_id", "normalized_items", ["source_id"])

    op.create_table(
        "prefilter_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("strategy_version", sa.String(length=128), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("bucket", sa.String(length=32), nullable=False),
        sa.Column("is_relevant", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("bucket in ('relevant', 'maybe', 'irrelevant')", name="ck_prefilter_results_bucket"),
        sa.ForeignKeyConstraint(["item_id"], ["normalized_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["strategy_version"], ["strategy_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prefilter_results_item_strategy", "prefilter_results", ["item_id", "strategy_version"])

    op.create_table(
        "model_scores",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("strategy_version", sa.String(length=128), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("impact_score", sa.Float(), nullable=False),
        sa.Column("novelty_score", sa.Float(), nullable=False),
        sa.Column("actionability_score", sa.Float(), nullable=False),
        sa.Column("credibility_score", sa.Float(), nullable=False),
        sa.Column("seller_action_level", sa.String(length=32), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("actionability_score >= 0 and actionability_score <= 100", name="ck_model_scores_actionability"),
        sa.CheckConstraint("credibility_score >= 0 and credibility_score <= 100", name="ck_model_scores_credibility"),
        sa.CheckConstraint("impact_score >= 0 and impact_score <= 100", name="ck_model_scores_impact"),
        sa.CheckConstraint("novelty_score >= 0 and novelty_score <= 100", name="ck_model_scores_novelty"),
        sa.CheckConstraint("relevance_score >= 0 and relevance_score <= 100", name="ck_model_scores_relevance"),
        sa.ForeignKeyConstraint(["item_id"], ["normalized_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["strategy_version"], ["strategy_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_scores_item_strategy", "model_scores", ["item_id", "strategy_version"])

    op.create_table(
        "ranked_items",
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("strategy_version", sa.String(length=128), nullable=False),
        sa.Column("source_weight", sa.Float(), nullable=False),
        sa.Column("category_weight", sa.Float(), nullable=False),
        sa.Column("freshness_weight", sa.Float(), nullable=False),
        sa.Column("duplicate_penalty", sa.Float(), nullable=False),
        sa.Column("channel_impact_weight", sa.Float(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("threshold_used", sa.Float(), nullable=False),
        sa.Column("selection_reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("category_weight >= 0 and category_weight <= 100", name="ck_ranked_items_category_weight"),
        sa.CheckConstraint(
            "channel_impact_weight >= 0 and channel_impact_weight <= 100",
            name="ck_ranked_items_channel_impact",
        ),
        sa.CheckConstraint("duplicate_penalty >= 0 and duplicate_penalty <= 100", name="ck_ranked_items_duplicate_penalty"),
        sa.CheckConstraint("final_score >= 0 and final_score <= 100", name="ck_ranked_items_final_score"),
        sa.CheckConstraint("freshness_weight >= 0 and freshness_weight <= 100", name="ck_ranked_items_freshness_weight"),
        sa.CheckConstraint("source_weight >= 0 and source_weight <= 100", name="ck_ranked_items_source_weight"),
        sa.CheckConstraint("threshold_used >= 0 and threshold_used <= 100", name="ck_ranked_items_threshold"),
        sa.ForeignKeyConstraint(["item_id"], ["normalized_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["strategy_version"], ["strategy_versions.id"]),
        sa.PrimaryKeyConstraint("item_id", "strategy_version"),
    )
    op.create_index("ix_ranked_items_selected_score", "ranked_items", ["selected", "final_score"])

    op.create_table(
        "event_clusters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("canonical_title", sa.Text(), nullable=False),
        sa.Column("main_item_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("member_count", sa.Integer(), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("cluster_score", sa.Float(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("cluster_score >= 0 and cluster_score <= 100", name="ck_event_clusters_cluster_score"),
        sa.CheckConstraint("member_count >= 0", name="ck_event_clusters_member_count"),
        sa.CheckConstraint("source_count >= 0", name="ck_event_clusters_source_count"),
        sa.ForeignKeyConstraint(["main_item_id"], ["normalized_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_event_clusters_channel", "event_clusters", ["channel"])
    op.create_index("ix_event_clusters_channel_score", "event_clusters", ["channel", "cluster_score"])
    op.create_index("ix_event_clusters_last_seen", "event_clusters", ["last_seen_at"])

    op.create_table(
        "cluster_members",
        sa.Column("cluster_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("relation_score", sa.Float(), nullable=False),
        sa.Column("is_main", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("relation_score >= 0 and relation_score <= 100", name="ck_cluster_members_relation_score"),
        sa.ForeignKeyConstraint(["cluster_id"], ["event_clusters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["normalized_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("cluster_id", "item_id"),
    )
    op.create_index("ix_cluster_members_source_id", "cluster_members", ["source_id"])

    op.create_table(
        "feedback_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("cluster_id", sa.Integer(), nullable=True),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("feedback_type", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "feedback_type in ('false_positive', 'false_negative', 'promote', 'demote', 'category_fix')",
            name="ck_feedback_events_feedback_type",
        ),
        sa.ForeignKeyConstraint(["cluster_id"], ["event_clusters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["item_id"], ["normalized_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feedback_events_channel_created", "feedback_events", ["channel", "created_at"])

    op.create_table(
        "daily_digests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("digest_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("strategy_version", sa.String(length=128), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("sections_json", sa.JSON(), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["strategy_version"], ["strategy_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel", "digest_date", "strategy_version", name="uq_daily_digests_channel_date_strategy"),
    )
    op.create_index("ix_daily_digests_channel_date", "daily_digests", ["channel", "digest_date"])

    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("strategy_version", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('pending', 'running', 'succeeded', 'failed')", name="ck_evaluation_runs_status"),
        sa.ForeignKeyConstraint(["strategy_version"], ["strategy_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_runs_channel_created", "evaluation_runs", ["channel", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_runs_channel_created", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
    op.drop_index("ix_daily_digests_channel_date", table_name="daily_digests")
    op.drop_table("daily_digests")
    op.drop_index("ix_feedback_events_channel_created", table_name="feedback_events")
    op.drop_table("feedback_events")
    op.drop_index("ix_cluster_members_source_id", table_name="cluster_members")
    op.drop_table("cluster_members")
    op.drop_index("ix_event_clusters_last_seen", table_name="event_clusters")
    op.drop_index("ix_event_clusters_channel_score", table_name="event_clusters")
    op.drop_index("ix_event_clusters_channel", table_name="event_clusters")
    op.drop_table("event_clusters")
    op.drop_index("ix_ranked_items_selected_score", table_name="ranked_items")
    op.drop_table("ranked_items")
    op.drop_index("ix_model_scores_item_strategy", table_name="model_scores")
    op.drop_table("model_scores")
    op.drop_index("ix_prefilter_results_item_strategy", table_name="prefilter_results")
    op.drop_table("prefilter_results")
    op.drop_index("ix_normalized_items_source_id", table_name="normalized_items")
    op.drop_index("ix_normalized_items_channel_published", table_name="normalized_items")
    op.drop_index("ix_normalized_items_channel", table_name="normalized_items")
    op.drop_index("ix_normalized_items_canonical_url", table_name="normalized_items")
    op.drop_table("normalized_items")
    op.drop_index("ix_raw_documents_source_fetched", table_name="raw_documents")
    op.drop_index("ix_raw_documents_canonical_url", table_name="raw_documents")
    op.drop_table("raw_documents")
    op.drop_index("ix_fetch_runs_source_started", table_name="fetch_runs")
    op.drop_table("fetch_runs")
    op.drop_index("ix_fetch_jobs_source_id", table_name="fetch_jobs")
    op.drop_index("ix_fetch_jobs_claim", table_name="fetch_jobs")
    op.drop_table("fetch_jobs")
    op.drop_index("ix_source_states_next_fetch_at", table_name="source_states")
    op.drop_table("source_states")
    op.drop_index("ix_strategy_versions_channel_status", table_name="strategy_versions")
    op.drop_table("strategy_versions")
    op.drop_index("ix_sources_tier", table_name="sources")
    op.drop_index("ix_sources_channel_enabled", table_name="sources")
    op.drop_index("ix_sources_channel", table_name="sources")
    op.drop_table("sources")
