"""add publisher identity and event evidence assessments

Revision ID: 20260728_0008
Revises: 20260515_0007
Create Date: 2026-07-28 11:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260728_0008"
down_revision = "20260515_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("publisher_key", sa.String(length=255), nullable=True),
    )
    op.execute(
        """
        UPDATE sources
        SET publisher_key = CASE
            WHEN source_group IS NOT NULL AND source_group <> '' THEN source_group || ':' || id
            ELSE id
        END
        WHERE publisher_key IS NULL
        """
    )
    op.alter_column("sources", "publisher_key", nullable=False)
    op.create_index("ix_sources_publisher_key", "sources", ["publisher_key"])

    op.create_table(
        "event_evidence_assessments",
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column("independent_source_count", sa.Integer(), nullable=False),
        sa.Column("authoritative_source_count", sa.Integer(), nullable=False),
        sa.Column("evidence_score", sa.Float(), nullable=False),
        sa.Column("supported_facts_json", sa.JSON(), nullable=False),
        sa.Column("supported_claims_json", sa.JSON(), nullable=False),
        sa.Column("conflicting_claims_json", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column(
            "analyzed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "verification_status in ('single_source', 'corroborated', 'conflicted', 'insufficient')",
            name="ck_event_evidence_assessments_status",
        ),
        sa.CheckConstraint(
            "independent_source_count >= 0",
            name="ck_event_evidence_assessments_independent_sources",
        ),
        sa.CheckConstraint(
            "authoritative_source_count >= 0",
            name="ck_event_evidence_assessments_authoritative_sources",
        ),
        sa.CheckConstraint(
            "evidence_score >= 0 and evidence_score <= 100",
            name="ck_event_evidence_assessments_score",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"], ["event_clusters.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_event_evidence_assessments_status",
        "event_evidence_assessments",
        ["verification_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_event_evidence_assessments_status",
        table_name="event_evidence_assessments",
    )
    op.drop_table("event_evidence_assessments")
    op.drop_index("ix_sources_publisher_key", table_name="sources")
    op.drop_column("sources", "publisher_key")
