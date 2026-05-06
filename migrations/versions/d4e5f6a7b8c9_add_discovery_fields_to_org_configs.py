"""add discovery fields to org_configs

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-06 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FALLBACK_DEFAULT = text("'[\"groq:openai/gpt-oss-120b\"]'")


def upgrade() -> None:
    op.add_column(
        "org_configs",
        sa.Column("discovery_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "org_configs",
        sa.Column("discovery_feeds", JSONB(), nullable=False, server_default=text("'[]'")),
    )
    op.add_column(
        "org_configs",
        sa.Column("discovery_categories", JSONB(), nullable=False, server_default=text("'[]'")),
    )
    op.add_column(
        "org_configs",
        sa.Column(
            "discovery_topic_matching_window_days",
            sa.Integer(),
            nullable=False,
            server_default="3",
        ),
    )
    op.add_column(
        "org_configs",
        sa.Column(
            "discovery_followup_threshold", sa.Integer(), nullable=False, server_default="5"
        ),
    )
    op.add_column(
        "org_configs",
        sa.Column(
            "discovery_classifier_model",
            sa.String(128),
            nullable=False,
            server_default="google-gla:gemini-flash-lite-latest",
        ),
    )
    op.add_column(
        "org_configs",
        sa.Column(
            "discovery_matcher_model",
            sa.String(128),
            nullable=False,
            server_default="google-gla:gemini-flash-lite-latest",
        ),
    )
    op.add_column(
        "org_configs",
        sa.Column(
            "discovery_topic_writer_model",
            sa.String(128),
            nullable=False,
            server_default="google-gla:gemini-flash-lite-latest",
        ),
    )
    op.add_column(
        "org_configs",
        sa.Column(
            "discovery_classifier_fallback_models",
            JSONB(),
            nullable=False,
            server_default=_FALLBACK_DEFAULT,
        ),
    )
    op.add_column(
        "org_configs",
        sa.Column(
            "discovery_matcher_fallback_models",
            JSONB(),
            nullable=False,
            server_default=_FALLBACK_DEFAULT,
        ),
    )
    op.add_column(
        "org_configs",
        sa.Column(
            "discovery_topic_writer_fallback_models",
            JSONB(),
            nullable=False,
            server_default=_FALLBACK_DEFAULT,
        ),
    )


def downgrade() -> None:
    op.drop_column("org_configs", "discovery_topic_writer_fallback_models")
    op.drop_column("org_configs", "discovery_matcher_fallback_models")
    op.drop_column("org_configs", "discovery_classifier_fallback_models")
    op.drop_column("org_configs", "discovery_topic_writer_model")
    op.drop_column("org_configs", "discovery_matcher_model")
    op.drop_column("org_configs", "discovery_classifier_model")
    op.drop_column("org_configs", "discovery_followup_threshold")
    op.drop_column("org_configs", "discovery_topic_matching_window_days")
    op.drop_column("org_configs", "discovery_categories")
    op.drop_column("org_configs", "discovery_feeds")
    op.drop_column("org_configs", "discovery_enabled")
