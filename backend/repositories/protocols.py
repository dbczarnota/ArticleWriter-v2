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
    OrgConfig,
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
        author_email: str | None = None,
        author_name: str | None = None,
        domain_name: str,
        topic: str,
    ) -> UUID:
        """Insert a new article in `running` state. Returns its UUID."""
        ...

    async def complete(
        self,
        article_id: UUID,
        *,
        status: str = "done",
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
        """Persist the full article + child rows; set status (default 'done').

        Pass status='failed' when stages reported errors but the pipeline still
        produced output; status='done' when fully clean. The Fact/Quote/etc.
        instances must NOT have article_id set; the repo injects it.
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

    async def set_pipeline_stage(self, article_id: UUID, stage: str | None) -> None:
        """Update the current pipeline stage label (no org filter — called internally by runner)."""
        ...

    async def set_marked_done(
        self,
        article_id: UUID,
        *,
        org_code: str,
        marked_done: bool,
        marked_done_by_name: str | None = None,
    ) -> None:
        """Toggle editorial done flag. Stores who made the change. No-op when article not found (idempotent)."""
        ...


class OrgRepository(Protocol):
    """Org CRUD. Rows are bootstrapped from JWT claims at first request."""

    async def create_from_jwt(self, *, code: str, name: str) -> Org:
        """Insert an org bootstrapped from JWT claims if absent. Idempotent.

        Returns the existing row when one already exists (no name overwrite —
        the user owns the field via Settings UI). On insert, `kinde_org_id` and
        `domain_name` both default to `code` so a single Kinde org code is
        sufficient bootstrap input — no Management API call needed.
        """
        ...

    async def get(self, code: str) -> Org | None:
        """Fetch by primary key (code). Returns None when absent."""
        ...

    async def set_domain_name(self, code: str, domain_name: str) -> None:
        """Update orgs.domain_name for a given org. No-op when org not found."""
        ...

    async def list_for_user(self, user_org_codes: list[str]) -> list[Org]:
        """Fetch all orgs whose code appears in the user's JWT org_codes claim.
        Used for `GET /v2/orgs`. Order: by name."""
        ...


class OrgConfigRepository(Protocol):
    """Domain config per org. One row per org, upserted via Settings UI."""

    async def get(self, org_code: str) -> OrgConfig | None:
        """Return config row for this org, or None if not yet configured."""
        ...

    async def upsert(self, config: OrgConfig) -> OrgConfig:
        """Insert or replace the config row; sets updated_at to now. Returns saved row."""
        ...

    async def create_default(self, org_code: str) -> OrgConfig:
        """Create an OrgConfig with model defaults for `org_code` if none exists.

        Idempotent: returns the existing row if one is already present, otherwise
        inserts a fresh row populated entirely from SQLModel field defaults.
        Used by `get_current_org` during first-request bootstrap of a new tenant.
        """
        ...
