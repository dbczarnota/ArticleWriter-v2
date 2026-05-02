"""baseline empty

Revision ID: 0f95e46c36cd
Revises: 
Create Date: 2026-05-02 21:44:08.212806

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '0f95e46c36cd'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
