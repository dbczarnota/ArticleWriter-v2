"""add stream_topics table

Revision ID: d5e6f7a8b9c0
Revises: a1b2c3d4e5f6
Create Date: 2026-05-10 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "d5e6f7a8b9c0"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stream_topics",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "subscription_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("stream_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("is_news", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("summary", sa.String(), nullable=False, server_default=""),
        sa.Column("speakers", JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("facts", JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("quotes", JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("window_start_seconds", sa.Float(), nullable=False),
        sa.Column("window_end_seconds", sa.Float(), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_stream_topics_sub_last_seen",
        "stream_topics",
        ["subscription_id", "last_seen_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_stream_topics_sub_last_seen", table_name="stream_topics")
    op.drop_table("stream_topics")
