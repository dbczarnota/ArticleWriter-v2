"""No-op repository implementations.

Used when DB_BACKEND=null — keeps `python run.py` working without Docker / Postgres.
All write methods log briefly to stdout so the user knows persistence was skipped;
all read methods return None / empty list.

Also used in tests where pulling Postgres up is overkill.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

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

_log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


# Stable seed values used by run.py's NullAuthenticator path so a developer can
# rely on the same identifiers across runs.
LOCAL_DEV_ORG_CODE = "__local_dev__"
LOCAL_DEV_DOMAIN = "styl_fm"
LOCAL_DEV_USER_ID = "local-dev"


class NullArticleRepository:
    """ArticleRepository that doesn't persist. Returns synthetic UUIDs and logs writes."""

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
    ) -> UUID:
        article_id = uuid4()
        _log.info(
            "[null-repo] create_running article_id=%s org=%s user=%s email=%s name=%r topic=%r urls=%d instructions=%s",
            article_id,
            org_code,
            author_user_id,
            author_email,
            author_name,
            topic[:80],
            len(input_urls or []),
            "yes" if additional_instructions else "no",
        )
        return article_id

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
        _log.info(
            "[null-repo] complete article_id=%s status=%s html_len=%d facts=%d quotes=%d "
            "embeds=%d usage=%d fallbacks=%d duration_ms=%.0f",
            article_id,
            status,
            len(html),
            len(facts),
            len(quotes),
            len(embed_candidates),
            len(usage_events),
            len(fallback_events),
            total_duration_ms,
        )

    async def mark_failed(
        self,
        article_id: UUID,
        *,
        error_status: str,
        errors: list[dict[str, str]],
        insufficient_sources_detail: dict | None = None,
    ) -> None:
        _log.info(
            "[null-repo] mark_failed article_id=%s status=%s errors=%d insufficient=%s",
            article_id,
            error_status,
            len(errors),
            bool(insufficient_sources_detail),
        )

    async def get(self, article_id: UUID, *, org_code: str) -> Article | None:
        _log.debug("[null-repo] get article_id=%s org=%s -> None", article_id, org_code)
        return None

    async def list_by_org(
        self,
        *,
        org_code: str,
        limit: int = 20,
        offset: int = 0,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
    ) -> list[Article]:
        del created_after, created_before  # null repo has no rows to filter
        _log.debug(
            "[null-repo] list_by_org org=%s limit=%d offset=%d -> []", org_code, limit, offset
        )
        return []

    async def set_pipeline_stage(self, article_id: UUID, stage: str | None) -> None:
        pass  # no-op for null backend

    async def set_marked_done(
        self,
        article_id: UUID,
        *,
        org_code: str,
        marked_done: bool,
        marked_done_by_name: str | None = None,
    ) -> None:
        _log.debug(
            "[null-repo] set_marked_done article_id=%s org=%s done=%s (no-op)",
            article_id,
            org_code,
            marked_done,
        )


class NullOrgRepository:
    """OrgRepository that returns a hardcoded local-dev org, so run.py + NullAuth still works."""

    def __init__(self) -> None:
        self._local_dev = Org(
            code=LOCAL_DEV_ORG_CODE,
            domain_name=LOCAL_DEV_DOMAIN,
            name="Local Dev",
            kinde_org_id=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    async def create_from_jwt(self, *, code: str, name: str) -> Org:
        _log.info("[null-repo] create_from_jwt code=%s name=%r", code, name)
        return Org(
            code=code,
            domain_name=code,
            name=name,
            kinde_org_id=code,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    async def get(self, code: str) -> Org | None:
        if code == LOCAL_DEV_ORG_CODE:
            return self._local_dev
        return None

    async def set_domain_name(self, code: str, domain_name: str) -> None:
        if code == LOCAL_DEV_ORG_CODE:
            self._local_dev.domain_name = domain_name
            self._local_dev.updated_at = datetime.now(UTC)

    async def list_for_user(self, user_org_codes: list[str]) -> list[Org]:
        if LOCAL_DEV_ORG_CODE in user_org_codes:
            return [self._local_dev]
        return []

    async def list_all(self) -> list[Org]:
        return [self._local_dev]


class NullOrgConfigRepository:
    """Returns hardcoded styl_fm defaults for offline run.py path.

    Text fields (guidelines, html_format, reflection_stance) are empty because
    offline runs don't need them — the pipeline produces output with bare defaults.
    """

    async def get(self, org_code: str) -> OrgConfig | None:
        return OrgConfig(
            org_code=org_code,
            description="Polski portal lifestyle/celebryci. Clickbait, emocje, krótkie artykuły.",
            language="pl",
            target_word_count=600,
            max_facts=8,
            max_quotes=3,
            search_freshness="qdr:w",
            num_queries=3,
            max_results=5,
            min_source_signals=4,
            max_pages_to_scrape=10,
            youtube_search=True,
            twitter_search=True,
            facebook_search=False,
            news_search=True,
            tiktok_search=True,
            instagram_search=True,
            reddit_search=True,
            media_search_languages=["en", "pl"],
            media_search_num=5,
            media_search_max_query_tiers=2,
            youtube_sort_by_date=True,
            reflection_context_articles=2,
            guidelines="",
            html_format="",
            reflection_stance="",
            reflection_rounds=1,
            example_articles=[],
            example_titles=[],
            agent_models={},
            agent_fallback_models={},
        )

    async def upsert(self, config: OrgConfig) -> OrgConfig:
        return config

    async def create_default(self, org_code: str) -> OrgConfig:
        return OrgConfig(org_code=org_code)


class NullDiscoveryRepository:
    """No-op DiscoveryRepository for local-dev and tests. Keeps an
    in-memory store so test harnesses that read after write get
    deterministic data, but emits no Logfire events."""

    def __init__(self) -> None:
        self._feeds: dict[UUID, DiscoveryFeed] = {}
        self._items: dict[UUID, DiscoveryItem] = {}
        self._topics: dict[UUID, DiscoveryTopic] = {}
        self._item_feeds: list[tuple[UUID, UUID]] = []

    # ── Feeds ────────────────────────────────────────────────────────────
    async def list_feeds_for_org(self, org_code: str) -> list[DiscoveryFeed]:
        return [f for f in self._feeds.values() if f.org_code == org_code]

    async def upsert_feed(self, *, org_code: str, feed_url: str) -> DiscoveryFeed:
        for f in self._feeds.values():
            if f.org_code == org_code and f.feed_url == feed_url:
                return f
        f = DiscoveryFeed(org_code=org_code, feed_url=feed_url)
        self._feeds[f.id] = f
        return f

    async def record_feed_run(
        self,
        feed_id: UUID,
        *,
        last_etag: str | None,
        last_modified: str | None,
    ) -> None:
        f = self._feeds.get(feed_id)
        if f is None:
            return
        f.last_fetched_at = _utcnow()
        f.last_etag = last_etag
        f.last_modified = last_modified
        f.error_count = 0
        f.last_error = None

    async def record_feed_error(
        self,
        feed_id: UUID,
        *,
        error_message: str,
        disable_threshold: int = 10,
    ) -> None:
        f = self._feeds.get(feed_id)
        if f is None:
            return
        f.error_count += 1
        f.last_error = error_message
        if f.error_count >= disable_threshold and not f.disabled:
            f.disabled = True

    async def reset_feed_errors(self, feed_id: UUID) -> None:
        f = self._feeds.get(feed_id)
        if f is None:
            return
        f.error_count = 0
        f.last_error = None
        f.disabled = False

    async def count_items_for_feed_since(
        self, *, feed_id: UUID, since: datetime
    ) -> int:
        item_ids = {item_id for (item_id, fid) in self._item_feeds if fid == feed_id}
        return sum(
            1
            for it in self._items.values()
            if it.id in item_ids and it.fetched_at >= since
        )

    async def get_min_published_at_for_feed(self, *, feed_id: UUID) -> datetime | None:
        item_ids = {item_id for (item_id, fid) in self._item_feeds if fid == feed_id}
        pubs = [
            it.published_at
            for it in self._items.values()
            if it.id in item_ids and it.published_at is not None
        ]
        return min(pubs) if pubs else None

    # ── Items ────────────────────────────────────────────────────────────
    async def get_item_by_url(self, *, org_code: str, canonical_url: str) -> DiscoveryItem | None:
        for it in self._items.values():
            if it.org_code == org_code and it.canonical_url == canonical_url:
                return it
        return None

    async def upsert_item(self, item: DiscoveryItem) -> DiscoveryItem:
        self._items[item.id] = item
        return item

    async def add_item_to_feed_link(self, *, item_id: UUID, feed_id: UUID) -> None:
        if (item_id, feed_id) not in self._item_feeds:
            self._item_feeds.append((item_id, feed_id))

    async def list_items_for_topic(self, *, topic_id: UUID, org_code: str) -> list[DiscoveryItem]:
        return [
            it for it in self._items.values() if it.topic_id == topic_id and it.org_code == org_code
        ]

    async def list_unprocessed_items(
        self, *, org_code: str, since: datetime, limit: int = 50
    ) -> list[DiscoveryItem]:
        rows = [
            it
            for it in self._items.values()
            if it.org_code == org_code and it.processed_at is None and it.fetched_at >= since
        ]
        rows.sort(key=lambda it: it.fetched_at)
        return rows[:limit]

    async def list_items_for_org(
        self,
        *,
        org_code: str,
        feed_id: UUID | None = None,
        categories: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DiscoveryItem]:
        rows = [it for it in self._items.values() if it.org_code == org_code]
        if feed_id is not None:
            item_ids_in_feed = {iid for (iid, fid) in self._item_feeds if fid == feed_id}
            rows = [it for it in rows if it.id in item_ids_in_feed]
        if categories:
            rows = [it for it in rows if any(c in it.categories for c in categories)]
        rows.sort(key=lambda it: it.fetched_at, reverse=True)
        return rows[offset : offset + limit]

    # ── Topics ───────────────────────────────────────────────────────────
    async def list_active_topics(self, *, org_code: str, window_days: int) -> list[DiscoveryTopic]:
        cutoff = _utcnow() - timedelta(days=window_days)
        return [
            t
            for t in self._topics.values()
            if t.org_code == org_code and t.last_activity_at >= cutoff
        ]

    async def create_topic(
        self,
        *,
        org_code: str,
        title: str,
        blurb: str,
        categories: list[str],
    ) -> DiscoveryTopic:
        t = DiscoveryTopic(org_code=org_code, title=title, blurb=blurb, categories=list(categories))
        self._topics[t.id] = t
        return t

    async def attach_item_to_topic(
        self,
        *,
        item_id: UUID,
        topic_id: UUID,
        item_categories: list[str],
    ) -> DiscoveryTopic:
        topic = self._topics[topic_id]
        topic.categories = list(dict.fromkeys(topic.categories + item_categories))
        topic.last_activity_at = _utcnow()
        item = self._items.get(item_id)
        if item is not None:
            item.topic_id = topic_id
        return topic

    async def mark_topic_consumed(
        self,
        *,
        topic_id: UUID,
        article_id: UUID,
        items_at_consume: int,
    ) -> None:
        t = self._topics[topic_id]
        t.status = "consumed"
        t.consumed_article_id = article_id
        t.consumed_at = _utcnow()
        t.items_at_consume = items_at_consume

    async def check_resurface(self, *, topic_id: UUID, threshold: int) -> bool:
        t = self._topics[topic_id]
        if t.consumed_at is None:
            return False
        new_count = sum(
            1
            for it in self._items.values()
            if it.topic_id == topic_id and it.fetched_at > t.consumed_at
        )
        if new_count >= threshold:
            t.status = "resurfaced"
            return True
        return False

    async def get_topic(self, *, topic_id: UUID, org_code: str) -> DiscoveryTopic | None:
        t = self._topics.get(topic_id)
        if t is None or t.org_code != org_code:
            return None
        return t

    async def list_topics_for_ui(
        self,
        *,
        org_code: str,
        categories: list[str] | None = None,
        statuses: list[str] | None = None,
        since: datetime | None = None,
        feed_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DiscoveryTopic]:
        rows = [t for t in self._topics.values() if t.org_code == org_code]
        if categories:
            cat_set = set(categories)
            rows = [t for t in rows if cat_set & set(t.categories)]
        if statuses:
            rows = [t for t in rows if t.status in set(statuses)]
        if since is not None:
            rows = [t for t in rows if t.last_activity_at >= since]
        if feed_id is not None:
            items_in_feed = {iid for (iid, fid) in self._item_feeds if fid == feed_id}
            topic_ids_in_feed = {
                it.topic_id
                for it in self._items.values()
                if it.id in items_in_feed and it.topic_id is not None
            }
            rows = [t for t in rows if t.id in topic_ids_in_feed]
        rows.sort(key=lambda t: t.last_activity_at, reverse=True)
        return rows[offset : offset + limit]

    async def dismiss_topic(self, *, topic_id: UUID, org_code: str) -> None:
        t = self._topics.get(topic_id)
        if t is not None and t.org_code == org_code:
            t.status = "dismissed"

    async def restore_topic(self, *, topic_id: UUID, org_code: str) -> None:
        t = self._topics.get(topic_id)
        if t is not None and t.org_code == org_code:
            t.status = "open"

    @asynccontextmanager
    async def try_acquire_feed_lock(self, feed_url: str):
        """No DB → no lock needed; single-process semantics always yields True."""
        del feed_url
        yield True
