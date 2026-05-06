"""Poll an org's RSS feeds and dispatch new items to the processing pipeline."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import logfire

from backend.domain import DomainConfig
from backend.repositories.protocols import DiscoveryRepository
from backend.services.discovery.feed_fetcher import FeedFetchError, RawFeedItem, fetch_feed
from backend.services.discovery.pipeline import process_item

# On the very first poll for a newly-added feed, only ingest this many of
# the most-recent entries. RSS feeds often expose 30+ historical items;
# pulling them all on day 1 floods Discovery with stale stories that the
# editor never wanted to see. Subsequent polls process whatever the feed
# returns — the dedup short-circuit in process_item handles repeats so
# new items get picked up cleanly.
FIRST_POLL_INITIAL_ITEMS = 5


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

    # Open baggage at org scope so every sub-event (auto-instrumented httpx
    # for feed fetches, pydantic-ai LLM spans inside process_item, stdlib
    # logging from feedparser, etc) inherits org_code without us having to
    # pass it as kwarg on every emission. Mirrors the article runner's
    # baggage pattern in agents/pipeline/runner.py.
    with logfire.set_baggage(org_code=org_code):
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
            parsed = urlparse(cfg.url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                await repo.record_feed_error(
                    feed_row.id, error_message=f"invalid feed URL scheme: {cfg.url[:200]}"
                )
                logfire.warn(
                    "discovery.feed.invalid_url",
                    feed_id=str(feed_row.id),
                    feed_url=cfg.url,
                )
                continue
            # Nested baggage for the per-feed scope — auto-instrumented httpx
            # span for the actual RSS fetch will inherit feed_id + feed_url.
            with logfire.set_baggage(feed_id=str(feed_row.id), feed_url=cfg.url):
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

                    is_first_poll = feed_row.last_fetched_at is None
                    await repo.record_feed_run(
                        feed_row.id,
                        last_etag=result.etag,
                        last_modified=result.last_modified,
                    )
                    feeds_polled += 1
                    if result.not_modified:
                        continue

                    items_to_process = result.items
                    if is_first_poll and len(items_to_process) > FIRST_POLL_INITIAL_ITEMS:
                        items_to_process = sorted(
                            items_to_process,
                            key=lambda r: r.published_at or datetime.min.replace(tzinfo=UTC),
                            reverse=True,
                        )[:FIRST_POLL_INITIAL_ITEMS]
                        logfire.info(
                            "discovery.feed.first_poll_truncated",
                            feed_id=str(feed_row.id),
                            feed_url=cfg.url,
                            total_items=len(result.items),
                            ingested=len(items_to_process),
                        )

                    for raw in items_to_process:
                        try:
                            await process_item(
                                raw=raw,
                                org_code=org_code,
                                domain=domain,
                                feed_id=feed_row.id,
                                repo=repo,
                            )
                            total_new += 1
                        except Exception as e:
                            logfire.warn(
                                "discovery.item.processing_failed",
                                feed_id=str(feed_row.id),
                                feed_url=cfg.url,
                                item_url=raw.url,
                                error_type=type(e).__name__,
                                error_message=str(e)[:500],
                            )
                            # Continue to next item; don't poison the rest of the feed.

        # Orphan recovery: items whose pipeline failed earlier (classifier crash,
        # matcher error, etc) sit with processed_at IS NULL. Give them another
        # shot each cycle. Bounded to last 24h + 50 items so a poison-pill item
        # doesn't block forever and the retry budget stays small.
        since = datetime.now(UTC) - timedelta(hours=24)
        orphans = await repo.list_unprocessed_items(org_code=org_code, since=since)
        orphans_retried = 0
        orphans_recovered = 0
        for orphan in orphans:
            try:
                raw = RawFeedItem(
                    title=orphan.title,
                    url=orphan.canonical_url,
                    guid=orphan.guid,
                    summary=orphan.summary,
                    published_at=orphan.published_at,
                )
                # Use the first runtime feed as a placeholder feed_id for baggage.
                # An orphan was created from at least one feed, so runtime_feeds
                # should not be empty, but guard defensively.
                if not runtime_feeds:
                    continue
                await process_item(
                    raw=raw,
                    org_code=org_code,
                    domain=domain,
                    feed_id=runtime_feeds[0].id,
                    repo=repo,
                )
                orphans_retried += 1
                orphans_recovered += 1
            except Exception as e:
                orphans_retried += 1
                logfire.warn(
                    "discovery.item.retry_failed",
                    org_code=org_code,
                    item_url=orphan.canonical_url,
                    error_type=type(e).__name__,
                    error_message=str(e)[:500],
                )

        logfire.info(
            "discovery.poll.completed",
            org_code=org_code,
            feeds_polled=feeds_polled,
            items_new=total_new,
            orphans_retried=orphans_retried,
            orphans_recovered=orphans_recovered,
            duration_ms=(time.perf_counter() - t0) * 1000,
        )
        return total_new
