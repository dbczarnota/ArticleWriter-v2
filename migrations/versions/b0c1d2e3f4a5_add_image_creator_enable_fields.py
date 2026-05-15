"""add image creator enable fields to org_configs

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-05-15
"""

import sqlalchemy as sa
from alembic import op

revision = "b0c1d2e3f4a5"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "org_configs",
        sa.Column("image_creator_enabled", sa.Boolean, nullable=False, server_default="false"),
    )
    op.add_column(
        "org_configs",
        sa.Column("image_creator_api_key", sa.String(256), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("org_configs", "image_creator_api_key")
    op.drop_column("org_configs", "image_creator_enabled")
