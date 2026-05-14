from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260514_0005"
down_revision = "20260513_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_feedback_events_feedback_type", "feedback_events", type_="check")
    op.add_column("feedback_events", sa.Column("contact", sa.String(length=255), nullable=True))
    op.add_column("feedback_events", sa.Column("status", sa.String(length=32), nullable=False, server_default="unread"))
    op.create_check_constraint(
        "ck_feedback_events_feedback_type",
        "feedback_events",
        "feedback_type in ('general', 'false_positive', 'false_negative', 'promote', 'demote', 'category_fix')",
    )
    op.create_check_constraint(
        "ck_feedback_events_status",
        "feedback_events",
        "status in ('unread', 'read', 'accepted', 'ignored')",
    )
    op.alter_column("feedback_events", "status", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_feedback_events_status", "feedback_events", type_="check")
    op.drop_constraint("ck_feedback_events_feedback_type", "feedback_events", type_="check")
    op.drop_column("feedback_events", "status")
    op.drop_column("feedback_events", "contact")
    op.create_check_constraint(
        "ck_feedback_events_feedback_type",
        "feedback_events",
        "feedback_type in ('false_positive', 'false_negative', 'promote', 'demote', 'category_fix')",
    )
