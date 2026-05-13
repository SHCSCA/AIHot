"""productize admin operations

Revision ID: 20260512_0002
Revises: 20260511_0001
Create Date: 2026-05-12 10:10:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260512_0002"
down_revision = "20260511_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "event_clusters",
        sa.Column("review_status", sa.String(length=32), server_default="pending", nullable=False),
    )
    op.add_column("event_clusters", sa.Column("review_note", sa.Text(), nullable=True))
    op.add_column("event_clusters", sa.Column("reviewed_by", sa.String(length=128), nullable=True))
    op.add_column("event_clusters", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_event_clusters_review_status",
        "event_clusters",
        "review_status in ('pending', 'approved', 'rejected')",
    )
    op.create_index("ix_event_clusters_review_status", "event_clusters", ["review_status"])

    op.add_column("daily_digests", sa.Column("published_by", sa.String(length=128), nullable=True))
    op.add_column("daily_digests", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column("limit", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("scheduled", sa.Integer(), nullable=False),
        sa.Column("claimed", sa.Integer(), nullable=False),
        sa.Column("succeeded", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("raw_documents_inserted", sa.Integer(), nullable=False),
        sa.Column("normalized_items", sa.Integer(), nullable=False),
        sa.Column("ranked_items", sa.Integer(), nullable=False),
        sa.Column("clusters", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('running', 'succeeded', 'failed')", name="ck_pipeline_runs_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pipeline_runs_started_at", "pipeline_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_pipeline_runs_started_at", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")
    op.drop_column("daily_digests", "published_at")
    op.drop_column("daily_digests", "published_by")
    op.drop_index("ix_event_clusters_review_status", table_name="event_clusters")
    op.drop_constraint("ck_event_clusters_review_status", "event_clusters", type_="check")
    op.drop_column("event_clusters", "reviewed_at")
    op.drop_column("event_clusters", "reviewed_by")
    op.drop_column("event_clusters", "review_note")
    op.drop_column("event_clusters", "review_status")
