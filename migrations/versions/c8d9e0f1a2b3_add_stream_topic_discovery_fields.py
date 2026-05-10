"""add discovery fields to stream_topics

Revision ID: c8d9e0f1a2b3
Revises: f6a7b8c9d0e1
Create Date: 2026-05-10 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "c8d9e0f1a2b3"
down_revision: str | Sequence[str] | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stream_topics",
        sa.Column("categories", JSONB(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "stream_topics",
        sa.Column(
            "topic_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("discovery_topics.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "stream_topics",
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "stream_topics",
        sa.Column("windows", JSONB(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.create_index(
        "ix_stream_topics_topic_id",
        "stream_topics",
        ["topic_id"],
        postgresql_where=sa.text("topic_id IS NOT NULL"),
    )
    op.create_index(
        "ix_stream_topics_unclassified",
        "stream_topics",
        ["subscription_id", "classified_at"],
        postgresql_where=sa.text("classified_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_stream_topics_unclassified", table_name="stream_topics")
    op.drop_index("ix_stream_topics_topic_id", table_name="stream_topics")
    op.drop_column("stream_topics", "windows")
    op.drop_column("stream_topics", "classified_at")
    op.drop_column("stream_topics", "topic_id")
    op.drop_column("stream_topics", "categories")
