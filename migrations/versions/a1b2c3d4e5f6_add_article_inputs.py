"""add article inputs (additional_instructions, input_urls)

Revision ID: a1b2c3d4e5f6
Revises: d64d1189c097
Create Date: 2026-05-05 17:35:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "d64d1189c097"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column("additional_instructions", sa.String(), nullable=True),
    )
    op.add_column(
        "articles",
        sa.Column("input_urls", JSONB(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("articles", "input_urls")
    op.drop_column("articles", "additional_instructions")
