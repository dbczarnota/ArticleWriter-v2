"""add discovery tables (feeds, items, m2m, topics)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-05 21:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # discovery_topics first — discovery_items has FK to it
    op.create_table(
        "discovery_topics",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("org_code", sa.String(128), sa.ForeignKey("orgs.code"), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("blurb", sa.String(1024), nullable=False),
        sa.Column("categories", JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("consumed_article_id", PG_UUID(as_uuid=True), sa.ForeignKey("articles.id"), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_at_consume", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_discovery_topics_org_activity", "discovery_topics", ["org_code", "last_activity_at"])
    op.create_index(
        "ix_discovery_topics_categories",
        "discovery_topics",
        ["categories"],
        postgresql_using="gin",
    )

    op.create_table(
        "discovery_feeds",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("org_code", sa.String(128), sa.ForeignKey("orgs.code"), nullable=False),
        sa.Column("feed_url", sa.String(2048), nullable=False),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_etag", sa.String(256), nullable=True),
        sa.Column("last_modified", sa.String(64), nullable=True),
        sa.Column("last_error", sa.String(2048), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("org_code", "feed_url", name="uq_discovery_feeds_org_url"),
    )
    op.create_index("ix_discovery_feeds_org", "discovery_feeds", ["org_code"])

    op.create_table(
        "discovery_items",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("org_code", sa.String(128), sa.ForeignKey("orgs.code"), nullable=False),
        sa.Column("canonical_url", sa.String(2048), nullable=False),
        sa.Column("guid", sa.String(512), nullable=True),
        sa.Column("title", sa.String(1024), nullable=False),
        sa.Column("summary", sa.String(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("categories", JSONB(), nullable=False, server_default="[]"),
        sa.Column("category_confidences", JSONB(), nullable=True),
        sa.Column(
            "topic_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("discovery_topics.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("classifier_model", sa.String(128), nullable=True),
        sa.Column("classifier_input_tokens", sa.Integer(), nullable=True),
        sa.Column("classifier_output_tokens", sa.Integer(), nullable=True),
        sa.Column("matcher_model", sa.String(128), nullable=True),
        sa.Column("matcher_input_tokens", sa.Integer(), nullable=True),
        sa.Column("matcher_output_tokens", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("org_code", "canonical_url", name="uq_discovery_items_org_url"),
    )
    op.create_index("ix_discovery_items_org_fetched", "discovery_items", ["org_code", "fetched_at"])
    op.create_index("ix_discovery_items_topic", "discovery_items", ["topic_id"])
    op.create_index(
        "ix_discovery_items_categories",
        "discovery_items",
        ["categories"],
        postgresql_using="gin",
    )

    op.create_table(
        "discovery_item_feeds",
        sa.Column(
            "item_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("discovery_items.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "feed_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("discovery_feeds.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("discovery_item_feeds")
    op.drop_index("ix_discovery_items_categories", table_name="discovery_items")
    op.drop_index("ix_discovery_items_topic", table_name="discovery_items")
    op.drop_index("ix_discovery_items_org_fetched", table_name="discovery_items")
    op.drop_table("discovery_items")
    op.drop_index("ix_discovery_feeds_org", table_name="discovery_feeds")
    op.drop_table("discovery_feeds")
    op.drop_index("ix_discovery_topics_categories", table_name="discovery_topics")
    op.drop_index("ix_discovery_topics_org_activity", table_name="discovery_topics")
    op.drop_table("discovery_topics")
