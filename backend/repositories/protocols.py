"""Repository protocols — application code talks to these, not to SQL.

Two implementations:
- Postgres (B4) — real persistence
- Null (B5) — no-op for `python run.py` without DB and for tests

The factory in `backend/repositories/__init__.py` (B6) chooses based on DB_BACKEND env.

Tenant isolation invariant: every read method takes `org_code` and the implementation
filters by it. Application code MUST NOT construct ad-hoc SQL queries that bypass this.
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol
from uuid import UUID

from backend.db.models import (
    Article,
    DiscoveryFeed,
    DiscoveryItem,
    DiscoveryTopic,
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
        additional_instructions: str | None = None,
        input_urls: list[str] | None = None,
        social_media_attachments: list[dict] | None = None,
    ) -> UUID:
        """Insert a new article in `running` state. Returns its UUID.

        Stores the editor's free-text steering and seed URLs verbatim so a
        failed article can still show what the editor asked for, without
        needing to consult logs.
        """
        ...

    async def complete(
        self,
        article_id: UUID,
        *,
        status: str = "done",
        html: str,
        alternative_titles: list[str],
        followup_topics: list[str],
        facebook_teasers: list[str],
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
        self,
        *,
        org_code: str,
        limit: int = 20,
        offset: int = 0,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
    ) -> list[Article]:
        """List articles for an org, newest first. Children NOT loaded (use get() for full).

        `created_after` / `created_before` are inclusive bounds on Article.created_at
        when supplied (used by the sidebar date filter). None means no bound on
        that side. Both naive and timezone-aware datetimes accepted; comparisons
        happen in UTC at the DB level.
        """
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

    async def count_running_for_org(self, org_code: str) -> int:
        """Number of articles currently in `running` status for this org.
        Used as a concurrent-run guard on write endpoints to cap LLM
        spend by a single tenant."""
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

    async def list_all(self) -> list[Org]:
        """Return every org. Used by the discovery scheduler at startup
        to register one polling job per org with discovery_enabled=True.
        Order: stable (by primary key), unspecified beyond that."""
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


class DiscoveryRepository(Protocol):
    """Persistence for the RSS discovery layer.

    Tenant-isolated: every read takes `org_code` and the implementation
    filters by it. Mirrors ArticleRepository / OrgRepository conventions.
    """

    # ── Feeds ────────────────────────────────────────────────────────────
    async def list_feeds_for_org(self, org_code: str) -> list[DiscoveryFeed]: ...
    async def upsert_feed(self, *, org_code: str, feed_url: str) -> DiscoveryFeed: ...
    async def record_feed_run(
        self,
        feed_id: UUID,
        *,
        last_etag: str | None,
        last_modified: str | None,
    ) -> None: ...
    async def record_feed_error(
        self,
        feed_id: UUID,
        *,
        error_message: str,
        disable_threshold: int = 10,
    ) -> None: ...
    async def reset_feed_errors(self, feed_id: UUID) -> None: ...
    async def count_items_for_feed_since(self, *, feed_id: UUID, since: datetime) -> int:
        """Count items linked to this feed via discovery_item_feed where the
        item's fetched_at >= since. Used by the feed-health endpoint."""
        ...

    async def get_min_published_at_for_feed(self, *, feed_id: UUID) -> datetime | None:
        """Lowest published_at across items linked to this feed. None when
        no items are linked yet, or when none of them carry a published_at.

        Used by the poller as a stale-item floor: after the first poll
        truncates to N newest items, the floor is the published_at of the
        oldest of those N. On every subsequent poll, items strictly older
        than this floor are dropped before they reach process_item — so the
        feed's historical backlog never gets backfilled."""
        ...

    # ── Items ────────────────────────────────────────────────────────────
    async def get_item_by_url(
        self, *, org_code: str, canonical_url: str
    ) -> DiscoveryItem | None: ...
    async def upsert_item(self, item: DiscoveryItem) -> DiscoveryItem: ...
    async def add_item_to_feed_link(self, *, item_id: UUID, feed_id: UUID) -> None: ...
    async def list_items_for_topic(
        self, *, topic_id: UUID, org_code: str
    ) -> list[DiscoveryItem]: ...
    async def list_unprocessed_items(
        self, *, org_code: str, since: datetime, limit: int = 50
    ) -> list[DiscoveryItem]:
        """Items with processed_at IS NULL fetched after `since`. Used by
        the poller's orphan-recovery scan: items whose pipeline failed
        (classifier crashed, etc) sit here until a future tick retries them."""
        ...

    async def list_feed_ids_for_item(self, *, item_id: UUID) -> list[UUID]:
        """Return every `feed_id` linked to this item via discovery_item_feed.
        Used by orphan recovery: when a previously-fetched item retries the
        full pipeline, we need to relink it to its ACTUAL originating feed,
        not a placeholder. Order: stable by primary key, unspecified beyond."""
        ...

    async def list_items_for_org(
        self,
        *,
        org_code: str,
        feed_id: UUID | None = None,
        categories: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DiscoveryItem]:
        """List items for the UI's raw-items view.

        Filters:
        - `feed_id`: items linked (via discovery_item_feed) to that feed.
        - `categories` (OR semantics): item.categories contains ANY of given.

        Order: fetched_at DESC. Pagination via limit/offset.
        Tenant-isolated by `org_code`."""
        ...

    # ── Topics ───────────────────────────────────────────────────────────
    async def list_active_topics(
        self, *, org_code: str, window_days: int, limit: int = 100
    ) -> list[DiscoveryTopic]:
        """Active topics within the matching window. Capped at `limit`
        (default 100) ordered by last_activity_at DESC — recent topics
        are more likely matcher candidates and the cap prevents the
        matcher prompt from ballooning beyond its token budget."""
        ...

    async def create_topic(
        self,
        *,
        org_code: str,
        title: str,
        blurb: str,
        categories: list[str],
    ) -> DiscoveryTopic: ...
    async def attach_item_to_topic(
        self,
        *,
        item_id: UUID,
        topic_id: UUID,
        item_categories: list[str],
    ) -> DiscoveryTopic:
        """Attaches item to topic, touches last_activity_at,
        and unions item_categories into topic.categories. Returns the
        updated topic."""
        ...

    async def mark_topic_consumed(
        self,
        *,
        topic_id: UUID,
        article_id: UUID,
        items_at_consume: int,
        org_code: str,
    ) -> None:
        """Mark a topic consumed by a successful article generation.
        Tenant-isolated: WHERE clause requires both topic_id AND org_code,
        so a forged topic_id from another org cannot mutate this one's
        topics."""
        ...

    async def check_resurface(
        self,
        *,
        topic_id: UUID,
        threshold: int,
    ) -> bool:
        """Counts items added after consumed_at; if >= threshold, flips
        topic.status to 'resurfaced'. Returns True if flipped."""
        ...

    async def get_topic(self, *, topic_id: UUID, org_code: str) -> DiscoveryTopic | None: ...
    async def list_topics_for_ui(
        self,
        *,
        org_code: str,
        categories: list[str] | None = None,
        statuses: list[str] | None = None,
        since: datetime | None = None,
        feed_id: UUID | None = None,
        subscription_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DiscoveryTopic]:
        """List topics for the UI.

        Filters:
        - `categories` (OR semantics): a topic matches if its categories list
          contains ANY of the given values. e.g. categories=["Polityka", "Sport"]
          returns topics tagged Polityka OR Sport, not both.
        - `statuses` (IN semantics): topic.status must equal one of the given.
        - `since`: topic.last_activity_at >= since.
        - `feed_id`: only topics that have at least one item attached to that feed.

        Order: last_activity_at DESC. Pagination via limit/offset."""
        ...

    async def dismiss_topic(self, *, topic_id: UUID, org_code: str) -> None: ...
    async def restore_topic(self, *, topic_id: UUID, org_code: str) -> None: ...

    def try_acquire_feed_lock(self, feed_url: str) -> AbstractAsyncContextManager[bool]:
        """Returns an async context manager that attempts a Postgres advisory
        transaction lock keyed on feed_url.

        Yields True if the lock was acquired (caller should proceed with
        polling), False otherwise (caller should skip — another replica is
        polling this feed right now). The lock is released automatically on
        exit (transaction end).

        Null implementation always yields True (single-process semantics)."""
        ...

