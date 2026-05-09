from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.domain import DomainConfig, FeedConfig
from backend.repositories.null import NullDiscoveryRepository
from backend.services.discovery.feed_fetcher import FeedFetchError, FetchResult, RawFeedItem
from backend.services.discovery.poller import poll_org_feeds


def _domain(feeds: list[FeedConfig]):
    return DomainConfig(
        name="test",
        description="t",
        discovery_enabled=True,
        discovery_feeds=feeds,
    )


@pytest.mark.asyncio
async def test_disabled_returns_zero_no_calls(monkeypatch):
    repo = NullDiscoveryRepository()
    fetcher = AsyncMock()
    proc = AsyncMock()
    monkeypatch.setattr("backend.services.discovery.poller.fetch_feed", fetcher)
    monkeypatch.setattr("backend.services.discovery.poller.process_item", proc)
    domain = DomainConfig(name="t", description="t", discovery_enabled=False)
    n = await poll_org_feeds(org_code="org_t", domain=domain, repo=repo)
    assert n == 0
    fetcher.assert_not_awaited()


@pytest.mark.asyncio
async def test_first_poll_truncates_to_five_most_recent(monkeypatch):
    """A brand new feed (last_fetched_at IS NULL) shouldn't ingest its
    entire backlog — RSS feeds typically expose 30+ historical items.
    Only the 5 most recent (by published_at) reach process_item."""
    from datetime import UTC, datetime, timedelta

    repo = NullDiscoveryRepository()
    base = datetime(2026, 5, 6, 12, 0, 0, tzinfo=UTC)
    items = [
        RawFeedItem(
            title=f"item-{i}",
            url=f"https://x/{i}",
            guid=f"g{i}",
            summary="s",
            published_at=base - timedelta(hours=i),
        )
        for i in range(10)
    ]
    fetcher = AsyncMock(
        return_value=FetchResult(items=items, etag='"a"', last_modified=None, not_modified=False)
    )
    proc = AsyncMock()
    monkeypatch.setattr("backend.services.discovery.poller.fetch_feed", fetcher)
    monkeypatch.setattr("backend.services.discovery.poller.process_item", proc)
    domain = _domain([FeedConfig(url="https://x/rss")])

    n = await poll_org_feeds(org_code="org_t", domain=domain, repo=repo)

    assert n == 5
    assert proc.await_count == 5
    # The 5 picked must be the most recent — items 0..4 (i=0 is newest).
    processed_urls = {call.kwargs["raw"].url for call in proc.await_args_list}
    assert processed_urls == {f"https://x/{i}" for i in range(5)}


@pytest.mark.asyncio
async def test_second_poll_drops_items_below_first_poll_floor(monkeypatch):
    """After the first poll keeps top-5, the published_at of the oldest of
    those 5 becomes the floor. On the next poll, RSS items strictly older
    than that floor get dropped — the historical backlog never gets
    backfilled."""
    from datetime import UTC, datetime, timedelta

    base = datetime(2026, 5, 6, 12, 0, 0, tzinfo=UTC)
    # 10 RSS items, item 0 newest, item 9 oldest (1 hour apart).
    items = [
        RawFeedItem(
            title=f"item-{i}",
            url=f"https://x/{i}",
            guid=f"g{i}",
            summary="s",
            published_at=base - timedelta(hours=i),
        )
        for i in range(10)
    ]
    fetcher = AsyncMock(
        return_value=FetchResult(items=items, etag='"a"', last_modified=None, not_modified=False)
    )

    # The Null repo's process_item mock won't actually link items, so we
    # write through the real process_item for the floor query to work.
    repo = NullDiscoveryRepository()

    async def real_process(*, raw, org_code, domain, feed_id, repo):
        from datetime import UTC, datetime

        from backend.db.models import DiscoveryItem

        # Real process_item stamps processed_at at the end so the orphan
        # recovery loop doesn't re-process completed items. Mirror that
        # here, otherwise the second pass through orphans inflates the
        # await count.
        item = await repo.upsert_item(
            DiscoveryItem(
                org_code=org_code,
                canonical_url=raw.url,
                title=raw.title,
                published_at=raw.published_at,
                processed_at=datetime.now(UTC),
            )
        )
        await repo.add_item_to_feed_link(item_id=item.id, feed_id=feed_id)
        return item

    proc = AsyncMock(side_effect=real_process)
    monkeypatch.setattr("backend.services.discovery.poller.fetch_feed", fetcher)
    monkeypatch.setattr("backend.services.discovery.poller.process_item", proc)
    domain = _domain([FeedConfig(url="https://x/rss")])

    # First poll: takes items 0..4 (newest 5). Floor = item 4's published_at
    # = base - 4h.
    await poll_org_feeds(org_code="org_t", domain=domain, repo=repo)
    assert proc.await_count == 5
    proc.reset_mock()

    # Second poll: same RSS items 0..9 returned. Items 0..4 still at/above
    # floor (dedup will catch them inside the real pipeline; here process_item
    # is invoked but our fake just re-upserts). Items 5..9 are below floor
    # and should be dropped before reaching process_item.
    await poll_org_feeds(org_code="org_t", domain=domain, repo=repo)
    processed_urls = {call.kwargs["raw"].url for call in proc.await_args_list}
    assert processed_urls == {f"https://x/{i}" for i in range(5)}
    # Items 5..9 must NOT have been called.
    for i in range(5, 10):
        assert f"https://x/{i}" not in processed_urls


@pytest.mark.asyncio
async def test_second_poll_no_floor_when_no_published_dates(monkeypatch):
    """If first-poll items have no published_at, the floor stays None and
    the second poll processes all items (we can't tell which are stale)."""
    repo = NullDiscoveryRepository()
    items = [
        RawFeedItem(
            title=f"item-{i}", url=f"https://x/{i}", guid=f"g{i}", summary="s", published_at=None
        )
        for i in range(8)
    ]
    fetcher = AsyncMock(
        return_value=FetchResult(items=items, etag='"a"', last_modified=None, not_modified=False)
    )
    proc = AsyncMock()
    monkeypatch.setattr("backend.services.discovery.poller.fetch_feed", fetcher)
    monkeypatch.setattr("backend.services.discovery.poller.process_item", proc)
    domain = _domain([FeedConfig(url="https://x/rss")])

    await poll_org_feeds(org_code="org_t", domain=domain, repo=repo)
    proc.reset_mock()

    n = await poll_org_feeds(org_code="org_t", domain=domain, repo=repo)
    assert n == 8
    assert proc.await_count == 8


@pytest.mark.asyncio
async def test_iterates_feeds_and_processes_new_items(monkeypatch):
    repo = NullDiscoveryRepository()
    fetcher = AsyncMock(
        return_value=FetchResult(
            items=[
                RawFeedItem(title="X", url="https://x/1", guid="g1", summary="s", published_at=None)
            ],
            etag='"a"',
            last_modified=None,
            not_modified=False,
        )
    )
    proc = AsyncMock()
    monkeypatch.setattr("backend.services.discovery.poller.fetch_feed", fetcher)
    monkeypatch.setattr("backend.services.discovery.poller.process_item", proc)
    domain = _domain([FeedConfig(url="https://x/rss")])
    n = await poll_org_feeds(org_code="org_t", domain=domain, repo=repo)
    assert n == 1
    proc.assert_awaited_once()


@pytest.mark.asyncio
async def test_304_no_processing(monkeypatch):
    repo = NullDiscoveryRepository()
    fetcher = AsyncMock(
        return_value=FetchResult(items=[], etag='"a"', last_modified=None, not_modified=True)
    )
    proc = AsyncMock()
    monkeypatch.setattr("backend.services.discovery.poller.fetch_feed", fetcher)
    monkeypatch.setattr("backend.services.discovery.poller.process_item", proc)
    domain = _domain([FeedConfig(url="https://x/rss")])
    n = await poll_org_feeds(org_code="org_t", domain=domain, repo=repo)
    assert n == 0
    proc.assert_not_awaited()


@pytest.mark.asyncio
async def test_one_failing_item_does_not_kill_the_loop(monkeypatch):
    """A bad item raises but the next item still gets processed."""
    repo = NullDiscoveryRepository()
    fetcher = AsyncMock(
        return_value=FetchResult(
            items=[
                RawFeedItem(
                    title="bad", url="https://x/1", guid="g1", summary=None, published_at=None
                ),
                RawFeedItem(
                    title="good", url="https://x/2", guid="g2", summary=None, published_at=None
                ),
            ],
            etag=None,
            last_modified=None,
            not_modified=False,
        )
    )

    proc_calls: list[str] = []

    async def proc(*, raw, **_):
        proc_calls.append(raw.url)
        if raw.url == "https://x/1":
            raise RuntimeError("LLM down")

    monkeypatch.setattr("backend.services.discovery.poller.fetch_feed", fetcher)
    monkeypatch.setattr("backend.services.discovery.poller.process_item", proc)

    domain = _domain([FeedConfig(url="https://x/rss")])
    await poll_org_feeds(org_code="org_t", domain=domain, repo=repo)
    # Both items attempted; loop continued past the failure.
    assert proc_calls == ["https://x/1", "https://x/2"]


@pytest.mark.asyncio
async def test_orphan_retry_uses_original_feed_id(monkeypatch):
    """An orphan item that originally came from feed B must be re-linked to
    feed B on retry, not to whatever runtime_feeds[0] happens to be."""
    from backend.db.models import DiscoveryItem

    repo = NullDiscoveryRepository()
    feed_a = await repo.upsert_feed(org_code="org_t", feed_url="https://a/rss")
    feed_b = await repo.upsert_feed(org_code="org_t", feed_url="https://b/rss")

    # Pre-seed an orphan from feed B, processed_at=None.
    orphan = DiscoveryItem(
        org_code="org_t", canonical_url="https://b/1", title="T", processed_at=None
    )
    orphan = await repo.upsert_item(orphan)
    await repo.add_item_to_feed_link(item_id=orphan.id, feed_id=feed_b.id)

    fetcher = AsyncMock(
        return_value=FetchResult(items=[], etag=None, last_modified=None, not_modified=False)
    )
    captured_feed_ids: list = []

    async def _capture(*, raw, org_code, domain, feed_id, repo):
        captured_feed_ids.append(feed_id)

    monkeypatch.setattr("backend.services.discovery.poller.fetch_feed", fetcher)
    monkeypatch.setattr("backend.services.discovery.poller.process_item", _capture)
    domain = _domain([FeedConfig(url="https://a/rss"), FeedConfig(url="https://b/rss")])

    await poll_org_feeds(org_code="org_t", domain=domain, repo=repo)

    # Orphan should be retried with feed B (its origin), not feed A.
    assert feed_b.id in captured_feed_ids, f"Expected feed_b.id={feed_b.id} in {captured_feed_ids}"
    assert feed_a.id not in captured_feed_ids, f"feed_a.id={feed_a.id} should not appear"


@pytest.mark.asyncio
async def test_fetch_error_increments_error_count(monkeypatch):
    repo = NullDiscoveryRepository()
    fetcher = AsyncMock(side_effect=FeedFetchError("boom"))
    monkeypatch.setattr("backend.services.discovery.poller.fetch_feed", fetcher)
    monkeypatch.setattr("backend.services.discovery.poller.process_item", AsyncMock())
    domain = _domain([FeedConfig(url="https://x/rss")])
    await poll_org_feeds(org_code="org_t", domain=domain, repo=repo)
    feeds = await repo.list_feeds_for_org("org_t")
    assert feeds[0].error_count == 1
    assert feeds[0].last_error == "boom"
