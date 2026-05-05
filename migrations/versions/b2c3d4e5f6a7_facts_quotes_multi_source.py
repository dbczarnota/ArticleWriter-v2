"""facts/quotes: source_url -> source_urls (multi-source)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-05 19:55:00.000000

Drops the legacy single source_url + source_title pair on facts and
the single source_url on quotes, replacing both with a JSONB
source_urls list. Existing rows are backfilled by wrapping the old
single URL in a single-element array.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── facts ────────────────────────────────────────────────────────────
    op.add_column(
        "facts",
        sa.Column("source_urls", JSONB(), nullable=False, server_default="[]"),
    )
    op.execute(
        "UPDATE facts SET source_urls = jsonb_build_array(source_url) "
        "WHERE source_url IS NOT NULL AND source_url <> ''"
    )
    op.drop_column("facts", "source_url")
    op.drop_column("facts", "source_title")

    # ── quotes ───────────────────────────────────────────────────────────
    op.add_column(
        "quotes",
        sa.Column("source_urls", JSONB(), nullable=False, server_default="[]"),
    )
    op.execute(
        "UPDATE quotes SET source_urls = jsonb_build_array(source_url) "
        "WHERE source_url IS NOT NULL AND source_url <> ''"
    )
    op.drop_column("quotes", "source_url")


def downgrade() -> None:
    # facts
    op.add_column(
        "facts",
        sa.Column("source_url", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "facts",
        sa.Column("source_title", sa.String(length=1024), nullable=True),
    )
    op.execute(
        "UPDATE facts SET source_url = source_urls->>0 "
        "WHERE jsonb_array_length(source_urls) > 0"
    )
    op.execute("UPDATE facts SET source_url = '' WHERE source_url IS NULL")
    op.execute("UPDATE facts SET source_title = '' WHERE source_title IS NULL")
    op.alter_column("facts", "source_url", nullable=False)
    op.alter_column("facts", "source_title", nullable=False)
    op.drop_column("facts", "source_urls")

    # quotes
    op.add_column(
        "quotes",
        sa.Column("source_url", sa.String(length=2048), nullable=True),
    )
    op.execute(
        "UPDATE quotes SET source_url = source_urls->>0 "
        "WHERE jsonb_array_length(source_urls) > 0"
    )
    op.execute("UPDATE quotes SET source_url = '' WHERE source_url IS NULL")
    op.alter_column("quotes", "source_url", nullable=False)
    op.drop_column("quotes", "source_urls")
