"""add_discovery_item_image_url

Revision ID: f1a2b3c4d5e6
Revises: d4e5f6a7b8c9
Create Date: 2026-05-06 20:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401  (kept for autogenerate consistency)


revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "discovery_items",
        sa.Column("image_url", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("discovery_items", "image_url")
