"""add stream_digests table

Revision ID: fa2b3c4d5e6f
Revises: e4f5a6b7c8d9
Create Date: 2026-05-09 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "fa2b3c4d5e6f"
down_revision: str | Sequence[str] | None = "e4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stream_digests",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "subscription_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("stream_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("window_start_seconds", sa.Float(), nullable=False),
        sa.Column("window_end_seconds", sa.Float(), nullable=False),
        sa.Column("stories", JSONB(), nullable=False, server_default=text("'[]'")),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_stream_digests_sub", "stream_digests", ["subscription_id"])


def downgrade() -> None:
    op.drop_index("ix_stream_digests_sub", "stream_digests")
    op.drop_table("stream_digests")
