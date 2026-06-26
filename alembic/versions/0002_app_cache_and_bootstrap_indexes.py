"""app cache and bootstrap indexes

Revision ID: 0002_app_cache
Revises: 0001_initial_schema
Create Date: 2026-06-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_app_cache"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_cache",
        sa.Column("cache_key", sa.String(length=220), primary_key=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("etag", sa.String(length=96), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_app_cache_updated_at", "app_cache", ["updated_at"])

    op.execute("CREATE INDEX IF NOT EXISTS ix_topics_bootstrap_fast ON topics (status, deleted_at, order_index, slug)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_topic_source_links_topic_relevance ON topic_source_links (topic_id, relevance)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_groups_bootstrap_sort ON groups (sort_order, name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_domains_bootstrap_sort ON domains (sort_order, name)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_domains_bootstrap_sort")
    op.execute("DROP INDEX IF EXISTS ix_groups_bootstrap_sort")
    op.execute("DROP INDEX IF EXISTS ix_topic_source_links_topic_relevance")
    op.execute("DROP INDEX IF EXISTS ix_topics_bootstrap_fast")
    op.drop_index("ix_app_cache_updated_at", table_name="app_cache")
    op.drop_table("app_cache")
