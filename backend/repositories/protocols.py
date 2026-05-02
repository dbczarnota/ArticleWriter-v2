"""Repository protocols — application code talks to these, not to SQL.

Two implementations:
- Postgres (B4) — real persistence
- Null (B5) — no-op for `python run.py` without DB and for tests

The factory in `backend/repositories/__init__.py` (B6) chooses based on DB_BACKEND env.

Tenant isolation invariant: every read method takes `org_code` and the implementation
filters by it. Application code MUST NOT construct ad-hoc SQL queries that bypass this.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from backend.db.models import (
    Article,
    EmbedCandidate,
    Fact,
    FallbackEvent,
    Org,
    Quote,
    UsageEvent,
)


class ArticleRepository(Protocol):
    """CRUD for the Article aggregate root.

    Lifecycle:
    1. create_running()    — at pipeline start, returns the article_id
    2. complete()          — at pipeline success: html + child rows
       OR mark_failed()    — at pipeline failure: errors detail

    Reads are tenant-filtered by org_code at the repo layer.
    """

    async def create_running(
        self,
        *,
        org_code: str,
        author_user_id: str,
        domain_name: str,
        topic: str,
    ) -> UUID:
        """Insert a new article in `running` state. Returns its UUID."""
        ...

    async def complete(
        self,
        article_id: UUID,
        *,
        html: str,
        alternative_titles: list[str],
        followup_topics: list[str],
        sources: list[str],
        facts: list[Fact],
        quotes: list[Quote],
        embed_candidates: list[EmbedCandidate],
        usage_events: list[UsageEvent],
        fallback_events: list[FallbackEvent],
        pipeline_timing: dict[str, float],
        errors: list[dict[str, str]],
        total_duration_ms: float,
    ) -> None:
        """Mark article as `done` and attach all child rows.

        The Fact/Quote/etc. instances must NOT have article_id set; the repo
        injects it. The repo also sets each child's id (UUID) if not set.
        """
        ...

    async def mark_failed(
        self,
        article_id: UUID,
        *,
        error_status: str,
        errors: list[dict[str, str]],
        insufficient_sources_detail: dict | None = None,
    ) -> None:
        """Set status to `error_status` (e.g. 'failed' or 'insufficient_sources').

        Records errors and (when applicable) the insufficient_sources guardrail detail.
        Does NOT delete the article — preserved for diagnostics.
        """
        ...

    async def get(self, article_id: UUID, *, org_code: str) -> Article | None:
        """Fetch one article including children. Returns None when not found OR
        when the article exists but belongs to a different org (no leak)."""
        ...

    async def list_by_org(
        self, *, org_code: str, limit: int = 20, offset: int = 0
    ) -> list[Article]:
        """List articles for an org, newest first. Children NOT loaded (use get() for full)."""
        ...


class OrgRepository(Protocol):
    """Org CRUD. Synced from Kinde via Management API."""

    async def upsert_from_kinde(
        self,
        *,
        kinde_org_id: str,
        code: str,
        name: str,
        domain_name: str,
    ) -> Org:
        """Create or update an org row keyed by kinde_org_id.

        On insert: all fields populated. On update: name and domain_name refreshed.
        Returns the persisted Org instance.
        """
        ...

    async def get(self, code: str) -> Org | None:
        """Fetch by primary key (code). Returns None when absent."""
        ...

    async def list_for_user(self, user_org_codes: list[str]) -> list[Org]:
        """Fetch all orgs whose code appears in the user's JWT org_codes claim.
        Used for `GET /v2/orgs`. Order: by name."""
        ...
