"""add tv fields to stream_subscriptions

Revision ID: e5f6a7b8c9d0
Revises: d5e6f7a8b9c0
Create Date: 2026-05-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "e5f6a7b8c9d0"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stream_subscriptions",
        sa.Column("stream_type", sa.String(16), nullable=False, server_default="radio"),
    )
    op.add_column(
        "stream_subscriptions",
        sa.Column("url_refresh_url", sa.String(2048), nullable=True),
    )
    op.add_column(
        "stream_subscriptions",
        sa.Column("url_refresh_headers", JSONB, nullable=False, server_default="{}"),
    )
    op.add_column(
        "stream_subscriptions",
        sa.Column("url_refresh_field", sa.String(256), nullable=False, server_default="url"),
    )


def downgrade() -> None:
    op.drop_column("stream_subscriptions", "url_refresh_field")
    op.drop_column("stream_subscriptions", "url_refresh_headers")
    op.drop_column("stream_subscriptions", "url_refresh_url")
    op.drop_column("stream_subscriptions", "stream_type")
