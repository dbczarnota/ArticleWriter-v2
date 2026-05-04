"""add_article_marked_done_by_name

Revision ID: c1e8f2a3b4d5
Revises: a3989b3817e8
Create Date: 2026-05-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'c1e8f2a3b4d5'
down_revision: Union[str, None] = 'a3989b3817e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('articles', sa.Column('marked_done_by_name', sa.String(length=256), nullable=True))


def downgrade() -> None:
    op.drop_column('articles', 'marked_done_by_name')
