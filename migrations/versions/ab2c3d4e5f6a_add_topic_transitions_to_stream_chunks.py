"""add topic_transitions to stream_chunks

Revision ID: ab2c3d4e5f6a
Revises: fa2b3c4d5e6f
Create Date: 2026-05-09 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "ab2c3d4e5f6a"
down_revision: str | Sequence[str] | None = "fa2b3c4d5e6f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stream_chunks",
        sa.Column("topic_transitions", JSONB(), nullable=False, server_default=text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("stream_chunks", "topic_transitions")
