"""add the global AI analysis switch

Revision ID: 20260825_0009
Revises: 20260728_0008
Create Date: 2026-08-25 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260825_0009"
down_revision = "20260728_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column(
            "ai_analysis_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("updated_by", sa.String(length=128), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO system_settings "
            "(id, ai_analysis_enabled, updated_at) "
            "VALUES ('global', TRUE, CURRENT_TIMESTAMP)"
        )
    )


def downgrade() -> None:
    op.drop_table("system_settings")
