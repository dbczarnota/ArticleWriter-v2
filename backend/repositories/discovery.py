"""PostgresDiscoveryRepository — DB-backed implementation of the
DiscoveryRepository protocol."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import logfire
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.db.models import DiscoveryFeed


def _utcnow() -> datetime:
    # Column is TIMESTAMP WITHOUT TIME ZONE — store naive UTC.
    return datetime.now(UTC).replace(tzinfo=None)


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
