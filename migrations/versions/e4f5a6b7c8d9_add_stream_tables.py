"""add stream_subscriptions and stream_chunks tables

Revision ID: e4f5a6b7c8d9
Revises: c4d5e6f7a8b9
Create Date: 2026-05-09 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

revision: str = "e4f5a6b7c8d9"
down_revision: str | Sequence[str] | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stream_subscriptions",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("org_code", sa.String(128), sa.ForeignKey("orgs.code"), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("stream_url", sa.String(2048), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default=text("'active'")),
        sa.Column("chunk_duration_seconds", sa.Integer(), nullable=False, server_default=text("30")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_stream_subs_org", "stream_subscriptions", ["org_code"])

    op.create_table(
        "stream_chunks",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "subscription_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("stream_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_start_seconds", sa.Float(), nullable=False),
        sa.Column("chunk_end_seconds", sa.Float(), nullable=False),
        sa.Column("raw_transcript", sa.Text(), nullable=False),
        sa.Column("speakers_detected", JSONB(), nullable=False, server_default=text("'[]'")),
        sa.Column("topics", JSONB(), nullable=False, server_default=text("'[]'")),
        sa.Column("facts", JSONB(), nullable=False, server_default=text("'[]'")),
        sa.Column("quotes", JSONB(), nullable=False, server_default=text("'[]'")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_stream_chunks_sub", "stream_chunks", ["subscription_id"])


def downgrade() -> None:
    op.drop_index("ix_stream_chunks_sub", "stream_chunks")
    op.drop_table("stream_chunks")
    op.drop_index("ix_stream_subs_org", "stream_subscriptions")
    op.drop_table("stream_subscriptions")
