from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agents.discovery.classifier.agent import CategoryDecision
from agents.discovery.topic_matcher.agent import MatchDecision
from agents.discovery.topic_writer.agent import TopicDescriptor
from backend.domain import CategoryConfig, DomainConfig
from backend.repositories.null import NullDiscoveryRepository
from backend.services.discovery.feed_fetcher import RawFeedItem
from backend.services.discovery.pipeline import process_item


def _domain():
    return DomainConfig(
        name="test",
        description="t",
        discovery_enabled=True,
        discovery_categories=[CategoryConfig(name="Sport", description="s")],
        discovery_topic_matching_window_days=3,
        discovery_followup_threshold=5,
    )


@pytest.mark.asyncio
async def test_new_item_no_match_creates_topic(monkeypatch):
    repo = NullDiscoveryRepository()
    feed = await repo.upsert_feed(org_code="org_t", feed_url="https://x/rss")

    classifier = AsyncMock(
        return_value=CategoryDecision(categories=["Sport"], confidences={}, reasoning="")
    )
    matcher = AsyncMock(return_value=MatchDecision(matched_topic_id=None, reasoning=""))
    writer = AsyncMock(return_value=TopicDescriptor(title="New story", blurb="A new event"))

    monkeypatch.setattr("backend.services.discovery.pipeline.run_classifier_agent", classifier)
    monkeypatch.setattr("backend.services.discovery.pipeline.run_topic_matcher_agent", matcher)
    monkeypatch.setattr("backend.services.discovery.pipeline.run_topic_writer_agent", writer)

    raw = RawFeedItem(
        title="X", url="https://x/a/1?utm_source=rss", guid="g1", summary="s", published_at=None
    )
    item = await process_item(
        raw=raw, org_code="org_t", domain=_domain(), feed_id=feed.id, repo=repo
    )

    assert item.canonical_url == "https://x/a/1"
    assert item.categories == ["Sport"]
    assert item.topic_id is not None
    topic = await repo.get_topic(topic_id=item.topic_id, org_code="org_t")
    assert topic is not None
    assert topic.title == "New story"
    writer.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_item_match_attaches_to_existing(monkeypatch):
    repo = NullDiscoveryRepository()
    feed = await repo.upsert_feed(org_code="org_t", feed_url="https://x/rss")
    existing = await repo.create_topic(
        org_code="org_t", title="Existing", blurb="b", categories=["Sport"]
    )

    classifier = AsyncMock(
        return_value=CategoryDecision(categories=["Lokalne"], confidences={}, reasoning="")
    )
    matcher = AsyncMock(return_value=MatchDecision(matched_topic_id=existing.id, reasoning=""))
    writer = AsyncMock()

    monkeypatch.setattr("backend.services.discovery.pipeline.run_classifier_agent", classifier)
    monkeypatch.setattr("backend.services.discovery.pipeline.run_topic_matcher_agent", matcher)
    monkeypatch.setattr("backend.services.discovery.pipeline.run_topic_writer_agent", writer)

    raw = RawFeedItem(title="X", url="https://x/a/1", guid="g1", summary="s", published_at=None)
    item = await process_item(
        raw=raw, org_code="org_t", domain=_domain(), feed_id=feed.id, repo=repo
    )

    assert item.topic_id == existing.id
    writer.assert_not_awaited()  # no new topic created
    updated = await repo.get_topic(topic_id=existing.id, org_code="org_t")
    assert updated is not None
    assert "Lokalne" in updated.categories


@pytest.mark.asyncio
async def test_duplicate_url_links_feed_no_reprocess(monkeypatch):
    repo = NullDiscoveryRepository()
    feed_a = await repo.upsert_feed(org_code="org_t", feed_url="https://a/rss")
    feed_b = await repo.upsert_feed(org_code="org_t", feed_url="https://b/rss")

    classifier = AsyncMock(
        return_value=CategoryDecision(categories=[], confidences={}, reasoning="")
    )
    matcher = AsyncMock(return_value=MatchDecision(matched_topic_id=None, reasoning=""))
    writer = AsyncMock(return_value=TopicDescriptor(title="t", blurb="b"))
    monkeypatch.setattr("backend.services.discovery.pipeline.run_classifier_agent", classifier)
    monkeypatch.setattr("backend.services.discovery.pipeline.run_topic_matcher_agent", matcher)
    monkeypatch.setattr("backend.services.discovery.pipeline.run_topic_writer_agent", writer)

    raw = RawFeedItem(title="X", url="https://x/a/1", guid="g1", summary="s", published_at=None)
    first = await process_item(
        raw=raw, org_code="org_t", domain=_domain(), feed_id=feed_a.id, repo=repo
    )
    second = await process_item(
        raw=raw, org_code="org_t", domain=_domain(), feed_id=feed_b.id, repo=repo
    )
    assert first.id == second.id
    assert classifier.await_count == 1  # second call short-circuited


@pytest.mark.asyncio
async def test_classifier_failure_does_not_create_orphan_item(monkeypatch):
    """If classifier crashes, no DiscoveryItem should be persisted (avoids
    orphan rows that block future retries via the get_item_by_url
    short-circuit)."""
    repo = NullDiscoveryRepository()
    feed = await repo.upsert_feed(org_code="org_t", feed_url="https://x/rss")

    classifier = AsyncMock(side_effect=RuntimeError("LLM down"))
    monkeypatch.setattr("backend.services.discovery.pipeline.run_classifier_agent", classifier)
    monkeypatch.setattr("backend.services.discovery.pipeline.run_topic_matcher_agent", AsyncMock())
    monkeypatch.setattr("backend.services.discovery.pipeline.run_topic_writer_agent", AsyncMock())

    raw = RawFeedItem(title="X", url="https://x/a/1", guid="g1", summary="s", published_at=None)
    with pytest.raises(RuntimeError):
        await process_item(raw=raw, org_code="org_t", domain=_domain(), feed_id=feed.id, repo=repo)

    # No item should have been persisted (no orphan to short-circuit future retries)
    assert await repo.get_item_by_url(org_code="org_t", canonical_url="https://x/a/1") is None


@pytest.mark.asyncio
async def test_classifier_returning_empty_lands_in_uncategorized(monkeypatch):
    repo = NullDiscoveryRepository()
    feed = await repo.upsert_feed(org_code="org_t", feed_url="https://x/rss")

    classifier = AsyncMock(
        return_value=CategoryDecision(categories=[], confidences={}, reasoning="")
    )
    matcher = AsyncMock(return_value=MatchDecision(matched_topic_id=None, reasoning=""))
    writer = AsyncMock(return_value=TopicDescriptor(title="t", blurb="b"))
    monkeypatch.setattr("backend.services.discovery.pipeline.run_classifier_agent", classifier)
    monkeypatch.setattr("backend.services.discovery.pipeline.run_topic_matcher_agent", matcher)
    monkeypatch.setattr("backend.services.discovery.pipeline.run_topic_writer_agent", writer)

    raw = RawFeedItem(title="X", url="https://x/a/1", guid="g1", summary="s", published_at=None)
    item = await process_item(
        raw=raw, org_code="org_t", domain=_domain(), feed_id=feed.id, repo=repo
    )
    assert item.categories == []
