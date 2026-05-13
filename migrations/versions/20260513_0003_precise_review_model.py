"""add precise review screening results

Revision ID: 20260513_0003
Revises: 20260512_0002
Create Date: 2026-05-13 10:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260513_0003"
down_revision = "20260512_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "raw_screening_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("raw_document_id", sa.Integer(), nullable=False),
        sa.Column("strategy_version", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("screen_status", sa.String(length=32), nullable=False),
        sa.Column("screen_bucket", sa.String(length=32), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("title_cn", sa.Text(), nullable=False),
        sa.Column("summary_cn", sa.Text(), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("reason_cn", sa.Text(), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "screen_status in ('accepted', 'rejected', 'failed')",
            name="ck_raw_screening_results_status",
        ),
        sa.CheckConstraint(
            "screen_bucket in ('core', 'related', 'watch', 'irrelevant', 'invalid')",
            name="ck_raw_screening_results_bucket",
        ),
        sa.CheckConstraint(
            "relevance_score >= 0 and relevance_score <= 100",
            name="ck_raw_screening_results_relevance",
        ),
        sa.CheckConstraint(
            "confidence_score >= 0 and confidence_score <= 100",
            name="ck_raw_screening_results_confidence",
        ),
        sa.ForeignKeyConstraint(["raw_document_id"], ["raw_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["strategy_version"], ["strategy_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("raw_document_id", "strategy_version", name="uq_raw_screening_results_raw_strategy"),
    )
    op.create_index(
        "ix_raw_screening_results_status_created",
        "raw_screening_results",
        ["screen_status", "created_at"],
    )
    op.create_index("ix_raw_screening_results_raw_document", "raw_screening_results", ["raw_document_id"])


def downgrade() -> None:
    op.drop_index("ix_raw_screening_results_raw_document", table_name="raw_screening_results")
    op.drop_index("ix_raw_screening_results_status_created", table_name="raw_screening_results")
    op.drop_table("raw_screening_results")
