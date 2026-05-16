"""add webhook fields

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-05-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

revision = "c1d2e3f4a5b6"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "org_configs",
        sa.Column("webhook_url", sa.String(2048), nullable=True),
    )
    op.add_column(
        "org_configs",
        sa.Column("webhook_secret", sa.String(256), nullable=True),
    )
    op.add_column(
        "articles",
        sa.Column(
            "webhook_deliveries",
            JSONB(),
            nullable=False,
            server_default=text("'[]'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("articles", "webhook_deliveries")
    op.drop_column("org_configs", "webhook_secret")
    op.drop_column("org_configs", "webhook_url")
