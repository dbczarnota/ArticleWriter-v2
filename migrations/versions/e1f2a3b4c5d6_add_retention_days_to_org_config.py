"""add retention_days fields to org_config

Revision ID: e1f2a3b4c5d6
Revises: c8d9e0f1a2b3
Create Date: 2026-05-10 18:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: str | Sequence[str] | None = "c8d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "org_configs",
        sa.Column(
            "discovery_retention_days",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("14"),
        ),
    )
    op.add_column(
        "org_configs",
        sa.Column(
            "stream_retention_days",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("7"),
        ),
    )


def downgrade() -> None:
    op.drop_column("org_configs", "stream_retention_days")
    op.drop_column("org_configs", "discovery_retention_days")
