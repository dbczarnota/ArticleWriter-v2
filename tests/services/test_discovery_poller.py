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
                RawFeedItem(title="bad", url="https://x/1", guid="g1", summary=None, published_at=None),
                RawFeedItem(title="good", url="https://x/2", guid="g2", summary=None, published_at=None),
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
