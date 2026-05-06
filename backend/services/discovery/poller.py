"""Poll an org's RSS feeds and dispatch new items to the processing pipeline."""

from __future__ import annotations

import time

import logfire

from backend.domain import DomainConfig
from backend.repositories.protocols import DiscoveryRepository
from backend.services.discovery.feed_fetcher import FeedFetchError, fetch_feed
from backend.services.discovery.pipeline import process_item


async def poll_org_feeds(
    *,
    org_code: str,
    domain: DomainConfig,
    repo: DiscoveryRepository,
) -> int:
    """Poll all enabled feeds for the org. Returns number of new items processed."""
    if not domain.discovery_enabled:
        logfire.info("discovery.poll.skipped", org_code=org_code, reason="disabled")
        return 0
    if not domain.discovery_feeds:
        logfire.info("discovery.poll.skipped", org_code=org_code, reason="no_feeds")
        return 0

    logfire.info(
        "discovery.poll.started",
        org_code=org_code,
        feeds_count=len(domain.discovery_feeds),
    )
    t0 = time.perf_counter()
    total_new = 0
    feeds_polled = 0

    # Ensure runtime rows exist for every config feed.
    for cfg in domain.discovery_feeds:
        await repo.upsert_feed(org_code=org_code, feed_url=cfg.url)

    runtime_feeds = await repo.list_feeds_for_org(org_code)
    runtime_by_url = {f.feed_url: f for f in runtime_feeds}

    for cfg in domain.discovery_feeds:
        feed_row = runtime_by_url.get(cfg.url)
        if feed_row is None or feed_row.disabled:
            continue
        async with repo.try_acquire_feed_lock(cfg.url) as acquired:
            if not acquired:
                logfire.info(
                    "discovery.feed.skipped_locked",
                    feed_id=str(feed_row.id),
                    feed_url=cfg.url,
                    reason="another_replica_polling",
                )
                continue
            try:
                result = await fetch_feed(
                    cfg.url,
                    etag=feed_row.last_etag,
                    last_modified=feed_row.last_modified,
                )
            except FeedFetchError as e:
                await repo.record_feed_error(feed_row.id, error_message=str(e))
                logfire.warn(
                    "discovery.feed.error",
                    feed_id=str(feed_row.id),
                    feed_url=cfg.url,
                    error_type="FeedFetchError",
                    error_message=str(e),
                    consecutive_errors=feed_row.error_count + 1,
                )
                continue

            await repo.record_feed_run(
                feed_row.id,
                last_etag=result.etag,
                last_modified=result.last_modified,
            )
            feeds_polled += 1
            if result.not_modified:
                continue

            for raw in result.items:
                await process_item(
                    raw=raw,
                    org_code=org_code,
                    domain=domain,
                    feed_id=feed_row.id,
                    repo=repo,
                )
                total_new += 1

    logfire.info(
        "discovery.poll.completed",
        org_code=org_code,
        feeds_polled=feeds_polled,
        items_new=total_new,
        duration_ms=(time.perf_counter() - t0) * 1000,
    )
    return total_new
