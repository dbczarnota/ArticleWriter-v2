"""add source_whitelist and source_blacklist to org_configs

Revision ID: f5e6d7c8b9a0
Revises: c1d2e3f4a5b6
Create Date: 2026-05-17 07:42:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f5e6d7c8b9a0"
down_revision: str | Sequence[str] | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "org_configs",
        sa.Column(
            "source_whitelist",
            postgresql.ARRAY(sa.String()),
            server_default=sa.text("ARRAY[]::text[]"),
            nullable=False,
        ),
    )
    op.add_column(
        "org_configs",
        sa.Column(
            "source_blacklist",
            postgresql.ARRAY(sa.String()),
            server_default=sa.text("ARRAY[]::text[]"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("org_configs", "source_blacklist")
    op.drop_column("org_configs", "source_whitelist")
