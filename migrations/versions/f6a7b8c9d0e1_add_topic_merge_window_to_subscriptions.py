"""add topic_merge_window_hours to stream_subscriptions

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-10 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stream_subscriptions",
        sa.Column(
            "topic_merge_window_hours",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("6"),
        ),
    )


def downgrade() -> None:
    op.drop_column("stream_subscriptions", "topic_merge_window_hours")
