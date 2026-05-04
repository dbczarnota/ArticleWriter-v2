"""SQLModel domain models — Postgres schema for ArticleWriter persistence.

Schema design notes:

- Article is the agregat root. Each pipeline run = one Article row + N child rows.
- Facts, Quotes, EmbedCandidates, UsageEvents, FallbackEvents are SEPARATE TABLES
  (not embedded JSONB) because we want to query them independently later: "facts
  mentioning X", "usage_events grouped by agent_name per org", etc. Pgvector indexes
  are also easier on dedicated tables than on jsonb subfields.
- Lists that are pure attached payload (alternative_titles, followup_topics, sources,
  pipeline_timing dict, errors list) stay as JSONB on Article — opaque, no nested queries.
- Article id is UUID4 (avoid enumeration attacks; future shardable).
- Tenant filter invariant: every read goes through repository methods that ALWAYS
  filter by org_code. Application code must never construct ad-hoc queries.

Status values for Article:
  running                — pipeline started, not yet finished
  done                   — pipeline succeeded; html populated
  failed                 — pipeline crashed at some stage; errors populated
  insufficient_sources   — guardrail tripped; insufficient_sources_detail populated
"""

# NOTE: do NOT add `from __future__ import annotations` — it stringifies all annotations
# and SQLModel/SQLAlchemy 2.0 can't resolve the Relationship target classes from strings.

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, Relationship, SQLModel

from backend.db.orgconfig_defaults import (
    DEFAULT_DESCRIPTION,
    DEFAULT_GUIDELINES,
    DEFAULT_HTML_FORMAT,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Org(SQLModel, table=True):
    __tablename__ = "orgs"  # type: ignore[assignment]

    code: str = Field(primary_key=True, max_length=128)
    """Stable org identifier used in API headers (X-Org-Code) and JWT claims."""

    domain_name: str = Field(max_length=64, index=True)
    """Editorial brand. Strict 1:1 — one org has exactly one domain."""

    name: str = Field(max_length=256)
    """Human-readable org name (synced from Kinde)."""

    kinde_org_id: str | None = Field(
        default=None, sa_column=Column(String(128), unique=True, index=True, nullable=True)
    )
    """Kinde-side org identifier; nullable for the local-dev seed."""

    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
        ),
    )


class Article(SQLModel, table=True):
    __tablename__ = "articles"  # type: ignore[assignment]
    __table_args__ = (
        Index("ix_articles_org_created", "org_code", "created_at"),
        Index("ix_articles_author", "author_user_id"),
        Index("ix_articles_status", "status"),
    )

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )

    org_code: str = Field(
        sa_column=Column(String(128), ForeignKey("orgs.code"), nullable=False, index=True)
    )
    author_user_id: str = Field(max_length=128)
    """Kinde user.sub from JWT — opaque string, no FK to a users table (Kinde is source of truth)."""

    author_email: str | None = Field(default=None, sa_column=Column(String(256), nullable=True))
    """Kinde user email at write time — denormalized for display; may be None for older rows."""

    author_name: str | None = Field(default=None, sa_column=Column(String(256), nullable=True))
    """Display name (given + family name from Kinde, or email fallback). Frontend
    sends it with the create request — same pattern as marked_done_by_name."""

    domain_name: str = Field(max_length=64)
    """Snapshot of org.domain_name at write time. Cheap denormalization for reporting."""

    topic: str = Field(max_length=1024)
    status: str = Field(max_length=32, default="running")
    """One of: running, done, failed, insufficient_sources."""

    pipeline_stage: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    """Current pipeline stage while status='running'. Cleared on completion."""

    marked_done: bool = Field(default=False)
    """Editorial flag — set by a user to mark the article as reviewed/published."""

    marked_done_by_name: str | None = Field(
        default=None, sa_column=Column(String(256), nullable=True)
    )
    """Full name of the user who last toggled marked_done. Denormalized for display."""

    # Output payload (populated by repo.complete()):
    html: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    alternative_titles: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    followup_topics: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    sources: list[str] = Field(default_factory=list, sa_column=Column(JSONB))

    # Operational metadata:
    pipeline_timing: dict[str, float] = Field(default_factory=dict, sa_column=Column(JSONB))
    errors: list[dict[str, str]] = Field(default_factory=list, sa_column=Column(JSONB))
    total_duration_ms: float | None = None
    insufficient_sources_detail: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )

    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )
    completed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    # Children (1:N, lazy-loaded via repository methods).
    # String forward refs are required because the child classes are defined below;
    # SQLAlchemy resolves them at mapper-configure time via the SQLModel class registry.
    facts: list["Fact"] = Relationship(back_populates="article", cascade_delete=True)
    quotes: list["Quote"] = Relationship(back_populates="article", cascade_delete=True)
    embed_candidates: list["EmbedCandidate"] = Relationship(
        back_populates="article", cascade_delete=True
    )
    usage_events: list["UsageEvent"] = Relationship(back_populates="article", cascade_delete=True)
    fallback_events: list["FallbackEvent"] = Relationship(
        back_populates="article", cascade_delete=True
    )


class Fact(SQLModel, table=True):
    __tablename__ = "facts"  # type: ignore[assignment]
    __table_args__ = (Index("ix_facts_article", "article_id"),)

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    article_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
        )
    )
    text: str = Field(sa_column=Column(String, nullable=False))
    context: str = Field(sa_column=Column(String, nullable=False))
    """Rich event-anchoring context (date, location, occasion, participants).
    Critical for downstream agents to keep facts from different events separate."""

    source_url: str = Field(max_length=2048)
    source_title: str = Field(max_length=1024)
    was_used: bool = Field(default=False)
    """True if this fact appears in the final article (set at repo.complete time)."""

    article: Article = Relationship(back_populates="facts")


class Quote(SQLModel, table=True):
    __tablename__ = "quotes"  # type: ignore[assignment]
    __table_args__ = (Index("ix_quotes_article", "article_id"),)

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    article_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
        )
    )
    text: str = Field(sa_column=Column(String, nullable=False))
    speaker: str = Field(max_length=512)
    context: str = Field(sa_column=Column(String, nullable=False))
    source_url: str = Field(max_length=2048)
    was_used: bool = Field(default=False)

    article: Article = Relationship(back_populates="quotes")


class EmbedCandidate(SQLModel, table=True):
    __tablename__ = "embed_candidates"  # type: ignore[assignment]
    __table_args__ = (Index("ix_embeds_article", "article_id"),)

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    article_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
        )
    )
    url: str = Field(max_length=2048)
    title: str = Field(max_length=1024)
    source: str = Field(max_length=32)
    """One of: youtube, twitter, tiktok, instagram, facebook, reddit."""

    thumbnail_url: str | None = Field(default=None, max_length=2048)
    description: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    channel: str | None = Field(default=None, max_length=512)
    competitor_source_url: str | None = Field(default=None, max_length=2048)
    """URL of the competitor article this embed was discovered in."""

    article: Article = Relationship(back_populates="embed_candidates")


class UsageEvent(SQLModel, table=True):
    __tablename__ = "usage_events"  # type: ignore[assignment]
    __table_args__ = (
        Index("ix_usage_article_agent", "article_id", "agent_name"),
        Index("ix_usage_occurred", "occurred_at"),
    )

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    article_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
        )
    )
    agent_name: str = Field(max_length=64)
    """One of: search, scraping_filter, parsing, extraction, adaptive_search,
    instructions, writer, reflection, followup, usage_tracking, media_search_formulate."""

    model: str = Field(max_length=128)
    """The actual model used for this LLM call (after fallback resolution)."""

    input_tokens: int
    output_tokens: int
    duration_ms: float
    occurred_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )

    article: Article = Relationship(back_populates="usage_events")


class FallbackEvent(SQLModel, table=True):
    __tablename__ = "fallback_events"  # type: ignore[assignment]
    __table_args__ = (Index("ix_fallback_article", "article_id"),)

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    article_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
        )
    )
    agent_name: str = Field(max_length=64)
    failed_model: str = Field(max_length=128)
    error_type: str = Field(max_length=128)
    error_message: str = Field(sa_column=Column(String, nullable=False))
    occurred_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )

    article: Article = Relationship(back_populates="fallback_events")


class OrgConfig(SQLModel, table=True):
    __tablename__ = "org_configs"  # type: ignore[assignment]

    org_code: str = Field(
        sa_column=Column(
            String(128),
            ForeignKey("orgs.code", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    description: str = Field(default=DEFAULT_DESCRIPTION)
    language: str = Field(default="pl", max_length=16)
    target_word_count: int = Field(default=600)
    max_facts: int = Field(default=8)
    max_quotes: int = Field(default=3)
    search_freshness: str = Field(default="qdr:w", max_length=32)
    num_queries: int = Field(default=3)
    max_results: int = Field(default=5)
    min_source_signals: int = Field(default=1)
    max_pages_to_scrape: int = Field(default=10)
    youtube_search: bool = Field(default=False)
    twitter_search: bool = Field(default=False)
    facebook_search: bool = Field(default=False)
    news_search: bool = Field(default=False)
    tiktok_search: bool = Field(default=False)
    instagram_search: bool = Field(default=False)
    reddit_search: bool = Field(default=False)
    media_search_languages: list[str] = Field(
        default_factory=lambda: ["en"],
        sa_column=Column(
            ARRAY(String()),
            nullable=False,
            server_default=text("ARRAY['en'::text]"),
        ),
    )
    media_search_num: int = Field(default=5)
    media_search_max_query_tiers: int = Field(default=2)
    youtube_sort_by_date: bool = Field(default=True)
    reflection_context_articles: int = Field(default=2)
    guidelines: str = Field(default=DEFAULT_GUIDELINES)
    html_format: str = Field(default=DEFAULT_HTML_FORMAT)
    reflection_stance: str = Field(default="")
    reflection_rounds: int = Field(default=1)
    example_articles: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            ARRAY(String()),
            nullable=False,
            server_default=text("ARRAY[]::text[]"),
        ),
    )
    example_titles: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            ARRAY(String()),
            nullable=False,
            server_default=text("ARRAY[]::text[]"),
        ),
    )
    agent_models: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'")),
    )
    """Per-agent primary model overrides: {agent_key: model_id}."""

    agent_fallback_models: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'")),
    )
    """Per-agent fallback model lists: {agent_key: [fallback1, fallback2]}."""

    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=text("now()")),
    )
