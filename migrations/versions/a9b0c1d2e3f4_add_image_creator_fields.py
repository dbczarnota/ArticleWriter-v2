"""add image creator fields

Revision ID: a9b0c1d2e3f4
Revises: e1f2a3b4c5d6
Create Date: 2026-05-15
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "a9b0c1d2e3f4"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "org_configs",
        sa.Column("image_templates", JSONB, nullable=False, server_default="'[]'"),
    )
    op.add_column(
        "articles",
        sa.Column("generated_images", JSONB, nullable=False, server_default="'[]'"),
    )


def downgrade() -> None:
    op.drop_column("org_configs", "image_templates")
    op.drop_column("articles", "generated_images")
