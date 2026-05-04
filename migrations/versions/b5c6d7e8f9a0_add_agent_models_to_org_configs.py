"""add_agent_models_to_org_configs

Revision ID: b5c6d7e8f9a0
Revises: 12b602ab7ab5
Create Date: 2026-05-04 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b5c6d7e8f9a0"
down_revision: Union[str, Sequence[str], None] = "12b602ab7ab5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "org_configs",
        sa.Column(
            "agent_models",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "org_configs",
        sa.Column(
            "agent_fallback_models",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("org_configs", "agent_fallback_models")
    op.drop_column("org_configs", "agent_models")
