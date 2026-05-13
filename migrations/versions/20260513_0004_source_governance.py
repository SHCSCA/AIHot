"""add source governance metadata

Revision ID: 20260513_0004
Revises: 20260513_0003
Create Date: 2026-05-13 15:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260513_0004"
down_revision = "20260513_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("source_group", sa.String(length=32), server_default="media", nullable=False))
    op.add_column("sources", sa.Column("contributor_no", sa.String(length=32), nullable=True))
    op.add_column("sources", sa.Column("social_handle", sa.String(length=128), nullable=True))
    op.add_column(
        "sources",
        sa.Column("collection_status", sa.String(length=32), server_default="collectable", nullable=False),
    )
    op.add_column("sources", sa.Column("free_access", sa.Boolean(), server_default=sa.true(), nullable=False))


def downgrade() -> None:
    op.drop_column("sources", "free_access")
    op.drop_column("sources", "collection_status")
    op.drop_column("sources", "social_handle")
    op.drop_column("sources", "contributor_no")
    op.drop_column("sources", "source_group")
