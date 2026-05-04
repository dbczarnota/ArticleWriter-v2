"""add_article_pipeline_stage

Revision ID: e3f4a5b6c7d8
Revises: d2f3e4a5b6c7
Create Date: 2026-05-04 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e3f4a5b6c7d8'
down_revision: Union[str, None] = 'd2f3e4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('articles', sa.Column('pipeline_stage', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('articles', 'pipeline_stage')
