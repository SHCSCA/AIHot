from __future__ import annotations

from alembic import op


revision = "20260514_0006"
down_revision = "20260514_0005"
branch_labels = None
depends_on = None


NEW_FETCH_ADAPTERS = "'rss', 'http_article', 'github', 'api', 'playwright', 'aihot_api', 'html_list'"
OLD_FETCH_ADAPTERS = "'rss', 'http_article', 'github', 'api', 'playwright'"


def upgrade() -> None:
    op.drop_constraint("ck_sources_fetch_adapter", "sources", type_="check")
    op.create_check_constraint(
        "ck_sources_fetch_adapter",
        "sources",
        f"fetch_adapter in ({NEW_FETCH_ADAPTERS})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_sources_fetch_adapter", "sources", type_="check")
    op.create_check_constraint(
        "ck_sources_fetch_adapter",
        "sources",
        f"fetch_adapter in ({OLD_FETCH_ADAPTERS})",
    )
