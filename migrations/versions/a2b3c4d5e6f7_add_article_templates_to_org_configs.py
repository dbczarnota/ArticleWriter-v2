"""add_article_templates_to_org_configs

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-05-08 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "org_configs",
        sa.Column(
            "article_templates",
            JSONB(),
            nullable=False,
            server_default=text("'[]'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("org_configs", "article_templates")
