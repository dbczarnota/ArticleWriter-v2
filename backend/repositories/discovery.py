"""PostgresDiscoveryRepository — DB-backed implementation of the
DiscoveryRepository protocol."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID

import logfire
from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.db.models import DiscoveryFeed, DiscoveryItem, DiscoveryItemFeed, DiscoveryTopic


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PostgresDiscoveryRepository:
    def __init__(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        self._session_maker = session_maker

    # ── Feeds ────────────────────────────────────────────────────────────
    async def list_feeds_for_org(self, org_code: str) -> list[DiscoveryFeed]:
        async with self._session_maker() as session:
            result = await session.execute(
                select(DiscoveryFeed).where(DiscoveryFeed.org_code == org_code)  # type: ignore[arg-type]
            )
            return list(result.scalars().all())

    async def upsert_feed(self, *, org_code: str, feed_url: str) -> DiscoveryFeed:
        async with self._session_maker() as session:
            existing = await session.execute(
                select(DiscoveryFeed).where(
                    DiscoveryFeed.org_code == org_code,  # type: ignore[arg-type]
                    DiscoveryFeed.feed_url == feed_url,  # type: ignore[arg-type]
                )
            )
            row = existing.scalar_one_or_none()
            if row is not None:
                return row
            new = DiscoveryFeed(org_code=org_code, feed_url=feed_url)
            session.add(new)
            await session.commit()
            await session.refresh(new)
            return new

    async def record_feed_run(
        self,
        feed_id: UUID,
        *,
        last_etag: str | None,
        last_modified: str | None,
    ) -> None:
        async with self._session_maker() as session:
            await session.execute(
                update(DiscoveryFeed)
                .where(DiscoveryFeed.id == feed_id)  # type: ignore[arg-type]
                .values(
                    last_fetched_at=_utcnow(),
                    last_etag=last_etag,
                    last_modified=last_modified,
                    error_count=0,
                    last_error=None,
                )
            )
            await session.commit()

    async def record_feed_error(
        self,
        feed_id: UUID,
        *,
        error_message: str,
        disable_threshold: int = 10,
    ) -> None:
        async with self._session_maker() as session:
            row = await session.get(DiscoveryFeed, feed_id)
            if row is None:
                return
            row.error_count += 1
            row.last_error = error_message[:2048]
            if row.error_count >= disable_threshold and not row.disabled:
                row.disabled = True
                logfire.warn(
                    "discovery.feed.disabled",
                    feed_id=str(feed_id),
                    feed_url=row.feed_url,
                    error_count=row.error_count,
                )
            await session.commit()

    async def reset_feed_errors(self, feed_id: UUID) -> None:
        async with self._session_maker() as session:
            await session.execute(
                update(DiscoveryFeed)
                .where(DiscoveryFeed.id == feed_id)  # type: ignore[arg-type]
                .values(error_count=0, last_error=None, disabled=False)
            )
            await session.commit()

    async def count_items_for_feed_since(
        self, *, feed_id: UUID, since: datetime
    ) -> int:
        async with self._session_maker() as session:
            result = await session.execute(
                select(func.count())
                .select_from(DiscoveryItem)
                .join(
                    DiscoveryItemFeed,
                    DiscoveryItemFeed.item_id == DiscoveryItem.id,  # type: ignore[arg-type]
                )
                .where(
                    DiscoveryItemFeed.feed_id == feed_id,  # type: ignore[arg-type]
                    DiscoveryItem.fetched_at >= since,  # type: ignore[arg-type]
                )
            )
            return int(result.scalar() or 0)

    async def get_min_published_at_for_feed(self, *, feed_id: UUID) -> datetime | None:
        async with self._session_maker() as session:
            result = await session.execute(
                select(func.min(DiscoveryItem.published_at))  # type: ignore[arg-type]
                .select_from(DiscoveryItem)
                .join(
                    DiscoveryItemFeed,
                    DiscoveryItemFeed.item_id == DiscoveryItem.id,  # type: ignore[arg-type]
                )
                .where(DiscoveryItemFeed.feed_id == feed_id)  # type: ignore[arg-type]
            )
            return result.scalar()

    # ── Items ────────────────────────────────────────────────────────────
    async def get_item_by_url(self, *, org_code: str, canonical_url: str) -> DiscoveryItem | None:
        async with self._session_maker() as session:
            result = await session.execute(
                select(DiscoveryItem).where(
                    DiscoveryItem.org_code == org_code,  # type: ignore[arg-type]
                    DiscoveryItem.canonical_url == canonical_url,  # type: ignore[arg-type]
                )
            )
            return result.scalar_one_or_none()

    async def upsert_item(self, item: DiscoveryItem) -> DiscoveryItem:
        async with self._session_maker() as session:
            existing = await session.execute(
                select(DiscoveryItem).where(
                    DiscoveryItem.org_code == item.org_code,  # type: ignore[arg-type]
                    DiscoveryItem.canonical_url == item.canonical_url,  # type: ignore[arg-type]
                )
            )
            row = existing.scalar_one_or_none()
            if row is None:
                session.add(item)
                await session.commit()
                await session.refresh(item)
                return item
            # Update mutable fields
            row.title = item.title
            row.summary = item.summary
            # Don't blank a known image with None — late polls may not parse
            # one out of every entry. Keep whatever we already had.
            if item.image_url is not None:
                row.image_url = item.image_url
            row.categories = list(item.categories)
            row.category_confidences = item.category_confidences
            row.topic_id = item.topic_id
            row.classifier_model = item.classifier_model
            row.classifier_input_tokens = item.classifier_input_tokens
            row.classifier_output_tokens = item.classifier_output_tokens
            row.matcher_model = item.matcher_model
            row.matcher_input_tokens = item.matcher_input_tokens
            row.matcher_output_tokens = item.matcher_output_tokens
            row.processed_at = item.processed_at
            await session.commit()
            await session.refresh(row)
            return row

    async def add_item_to_feed_link(self, *, item_id: UUID, feed_id: UUID) -> None:
        async with self._session_maker() as session:
            stmt = (
                pg_insert(DiscoveryItemFeed)
                .values(item_id=item_id, feed_id=feed_id)
                .on_conflict_do_nothing(index_elements=["item_id", "feed_id"])
            )
            await session.execute(stmt)
            await session.commit()

    async def list_items_for_topic(self, *, topic_id: UUID, org_code: str) -> list[DiscoveryItem]:
        async with self._session_maker() as session:
            result = await session.execute(
                select(DiscoveryItem)
                .where(
                    DiscoveryItem.topic_id == topic_id,  # type: ignore[arg-type]
                    DiscoveryItem.org_code == org_code,  # type: ignore[arg-type]
                )
                .order_by(DiscoveryItem.fetched_at)  # type: ignore[arg-type]
            )
            return list(result.scalars().all())

    async def list_unprocessed_items(
        self, *, org_code: str, since: datetime, limit: int = 50
    ) -> list[DiscoveryItem]:
        async with self._session_maker() as session:
            result = await session.execute(
                select(DiscoveryItem)
                .where(
                    DiscoveryItem.org_code == org_code,  # type: ignore[arg-type]
                    DiscoveryItem.processed_at.is_(None),  # type: ignore[union-attr]
                    DiscoveryItem.fetched_at >= since,  # type: ignore[arg-type]
                )
                .order_by(DiscoveryItem.fetched_at)  # type: ignore[arg-type]
                .limit(limit)
            )
            return list(result.scalars().all())

    async def list_items_for_org(
        self,
        *,
        org_code: str,
        feed_id: UUID | None = None,
        categories: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DiscoveryItem]:
        from sqlalchemy import cast, or_
        from sqlalchemy.dialects.postgresql import JSONB

        async with self._session_maker() as session:
            stmt = select(DiscoveryItem).where(DiscoveryItem.org_code == org_code)  # type: ignore[arg-type]
            if feed_id is not None:
                # Outer WHERE already constrains DiscoveryItem.org_code; the
                # IN-subquery on the link table inherits that constraint via
                # the join on DiscoveryItem.id, so foreign-org item_ids
                # cannot match any row the outer query considers.
                stmt = stmt.where(
                    DiscoveryItem.id.in_(  # type: ignore[arg-type]
                        select(DiscoveryItemFeed.item_id).where(  # type: ignore[arg-type]
                            DiscoveryItemFeed.feed_id == feed_id  # type: ignore[arg-type]
                        )
                    )
                )
            if categories:
                clauses = [
                    DiscoveryItem.categories.op("@>")(cast([c], JSONB))  # type: ignore[arg-type]
                    for c in categories
                ]
                stmt = stmt.where(or_(*clauses))
            stmt = (
                stmt.order_by(DiscoveryItem.fetched_at.desc())  # type: ignore[arg-type]
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # ── Topics ───────────────────────────────────────────────────────────
    async def list_active_topics(self, *, org_code: str, window_days: int) -> list[DiscoveryTopic]:
        cutoff = datetime.now(UTC) - timedelta(days=window_days)
        async with self._session_maker() as session:
            result = await session.execute(
                select(DiscoveryTopic).where(
                    DiscoveryTopic.org_code == org_code,  # type: ignore[arg-type]
                    DiscoveryTopic.last_activity_at >= cutoff,  # type: ignore[arg-type]
                )
            )
            return list(result.scalars().all())

    async def create_topic(
        self,
        *,
        org_code: str,
        title: str,
        blurb: str,
        categories: list[str],
    ) -> DiscoveryTopic:
        topic = DiscoveryTopic(
            org_code=org_code,
            title=title,
            blurb=blurb,
            categories=list(categories),
        )
        async with self._session_maker() as session:
            session.add(topic)
            await session.commit()
            await session.refresh(topic)
        logfire.info(
            "discovery.topic.created",
            topic_id=str(topic.id),
            title=title,
            blurb=blurb,
            categories=list(categories),
        )
        return topic

    async def attach_item_to_topic(
        self,
        *,
        item_id: UUID,
        topic_id: UUID,
        item_categories: list[str],
    ) -> DiscoveryTopic:
        async with self._session_maker() as session:
            topic = await session.get(DiscoveryTopic, topic_id)
            if topic is None:
                raise LookupError(f"Topic {topic_id} not found")
            new_tags = [c for c in item_categories if c not in topic.categories]
            if new_tags:
                topic.categories = list(topic.categories) + new_tags
            topic.last_activity_at = datetime.now(UTC)
            topic.updated_at = datetime.now(UTC)
            item = await session.get(DiscoveryItem, item_id)
            if item is not None:
                item.topic_id = topic_id
            await session.commit()
            await session.refresh(topic)
            return topic

    async def mark_topic_consumed(
        self,
        *,
        topic_id: UUID,
        article_id: UUID,
        items_at_consume: int,
        org_code: str,
    ) -> None:
        async with self._session_maker() as session:
            await session.execute(
                update(DiscoveryTopic)
                .where(
                    DiscoveryTopic.id == topic_id,  # type: ignore[arg-type]
                    DiscoveryTopic.org_code == org_code,  # type: ignore[arg-type]
                )
                .values(
                    status="consumed",
                    consumed_article_id=article_id,
                    consumed_at=datetime.now(UTC),
                    items_at_consume=items_at_consume,
                    updated_at=datetime.now(UTC),
                )
            )
            await session.commit()

    async def check_resurface(self, *, topic_id: UUID, threshold: int) -> bool:
        async with self._session_maker() as session:
            topic = await session.get(DiscoveryTopic, topic_id)
            if topic is None or topic.consumed_at is None:
                return False
            count_stmt = (
                select(func.count())
                .select_from(DiscoveryItem)
                .where(
                    DiscoveryItem.topic_id == topic_id,  # type: ignore[arg-type]
                    DiscoveryItem.fetched_at > topic.consumed_at,  # type: ignore[arg-type]
                )
            )
            new_count = (await session.execute(count_stmt)).scalar_one() or 0
            if new_count < threshold:
                return False
            topic.status = "resurfaced"
            topic.updated_at = datetime.now(UTC)
            await session.commit()
            logfire.info(
                "discovery.topic.resurfaced",
                topic_id=str(topic_id),
                consumed_at=topic.consumed_at.isoformat(),
                new_items_since=new_count,
                threshold=threshold,
            )
            return True

    async def get_topic(self, *, topic_id: UUID, org_code: str) -> DiscoveryTopic | None:
        async with self._session_maker() as session:
            topic = await session.get(DiscoveryTopic, topic_id)
            if topic is None or topic.org_code != org_code:
                return None
            return topic

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
        """List topics for the UI.

        Filters:
        - `categories` (OR semantics): a topic matches if its categories list
          contains ANY of the given values. e.g. categories=["Polityka", "Sport"]
          returns topics tagged Polityka OR Sport, not both.
        - `statuses` (IN semantics): topic.status must equal one of the given.
        - `since`: topic.last_activity_at >= since.
        - `feed_id`: only topics that have at least one item attached to that feed.

        Order: last_activity_at DESC. Pagination via limit/offset."""
        from sqlalchemy import cast, or_
        from sqlalchemy.dialects.postgresql import JSONB

        async with self._session_maker() as session:
            stmt = select(DiscoveryTopic).where(DiscoveryTopic.org_code == org_code)  # type: ignore[arg-type]
            if statuses:
                stmt = stmt.where(DiscoveryTopic.status.in_(statuses))  # type: ignore[arg-type]
            if since is not None:
                stmt = stmt.where(DiscoveryTopic.last_activity_at >= since)  # type: ignore[arg-type]
            if categories:
                # `categories` is JSONB list; OR semantics — any tag matches.
                # JSONB containment of a single-element array gives that.
                clauses = [
                    DiscoveryTopic.categories.op("@>")(cast([cat], JSONB))  # type: ignore[arg-type]
                    for cat in categories
                ]
                stmt = stmt.where(or_(*clauses))
            if feed_id is not None:
                # Defense-in-depth: also pin the subquery to org_code so a
                # caller passing a foreign-org feed_id cannot use response
                # cardinality as an enumeration oracle. UUID uniqueness alone
                # would prevent a real row leak via the outer org_code filter,
                # but we don't want this to depend on collision-free luck.
                stmt = stmt.where(
                    DiscoveryTopic.id.in_(  # type: ignore[arg-type]
                        select(DiscoveryItem.topic_id)  # type: ignore[arg-type]
                        .join(
                            DiscoveryItemFeed,
                            DiscoveryItemFeed.item_id == DiscoveryItem.id,  # type: ignore[arg-type]
                        )
                        .where(
                            DiscoveryItemFeed.feed_id == feed_id,  # type: ignore[arg-type]
                            DiscoveryItem.org_code == org_code,  # type: ignore[arg-type]
                        )
                    )
                )
            stmt = stmt.order_by(DiscoveryTopic.last_activity_at.desc()).limit(limit).offset(offset)  # type: ignore[arg-type]
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def dismiss_topic(self, *, topic_id: UUID, org_code: str) -> None:
        async with self._session_maker() as session:
            await session.execute(
                update(DiscoveryTopic)
                .where(
                    DiscoveryTopic.id == topic_id,  # type: ignore[arg-type]
                    DiscoveryTopic.org_code == org_code,  # type: ignore[arg-type]
                )
                .values(status="dismissed", updated_at=_utcnow())
            )
            await session.commit()

    async def restore_topic(self, *, topic_id: UUID, org_code: str) -> None:
        async with self._session_maker() as session:
            await session.execute(
                update(DiscoveryTopic)
                .where(
                    DiscoveryTopic.id == topic_id,  # type: ignore[arg-type]
                    DiscoveryTopic.org_code == org_code,  # type: ignore[arg-type]
                )
                .values(status="open", updated_at=_utcnow())
            )
            await session.commit()

    @asynccontextmanager
    async def try_acquire_feed_lock(self, feed_url: str):
        """Attempt a Postgres advisory transaction lock keyed on feed_url.

        Yields True if acquired (caller should poll the feed), False if another
        replica holds the lock (caller should skip). Lock releases automatically
        when the session transaction ends."""
        async with self._session_maker() as session:
            result = await session.execute(
                text("SELECT pg_try_advisory_xact_lock(hashtext(:url))"),
                {"url": feed_url},
            )
            acquired = bool(result.scalar())
            try:
                yield acquired
            finally:
                if acquired:
                    await session.commit()  # releases the xact lock
                else:
                    await session.rollback()
