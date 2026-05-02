import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from agents._base.types import EmbedCandidate
from agents.media_search.agent import run_media_search
from domains._base.config import DomainConfig

_DOMAIN_ALL = DomainConfig(
    name="test",
    description="t",
    youtube_search=True,
    twitter_search=True,
    tiktok_search=True,
    instagram_search=True,
    facebook_search=True,
    reddit_search=True,
)
_DOMAIN_NONE = DomainConfig(name="test", description="t")

_YT = EmbedCandidate(url="https://youtube.com/watch?v=1", title="YT", source="youtube")
_TW = EmbedCandidate(url="https://x.com/u/status/1", title="Tweet", source="twitter")
_IG = EmbedCandidate(
    url="https://instagram.com/reel/abc/",
    title="Reel",
    source="instagram",
    thumbnail_url="https://cdn.ig.com/thumb.jpg",
)
_RD = EmbedCandidate(url="https://reddit.com/r/news/abc", title="Reddit post", source="reddit")


def test_returns_empty_when_all_flags_off():
    candidates, errors = asyncio.run(
        run_media_search("topic", domain=_DOMAIN_NONE, serper_api_key="k")
    )
    assert candidates == []
    assert errors == {}


@pytest.mark.asyncio
async def test_aggregates_results_from_enabled_sources():
    with (
        patch(
            "agents.media_search.agent._formulate_queries",
            new_callable=AsyncMock,
            return_value=['"Melania Trump"'],
        ),
        patch(
            "agents.media_search.agent.search_videos", new_callable=AsyncMock, return_value=[_YT]
        ),
        patch("agents.media_search.agent.search_site", new_callable=AsyncMock, return_value=[_TW]),
        patch("agents.media_search.agent.search_images", new_callable=AsyncMock, return_value=[]),
        patch("agents.media_search.agent.search_reddit", new_callable=AsyncMock, return_value=[]),
    ):
        domain = DomainConfig(name="t", description="t", youtube_search=True, twitter_search=True)
        candidates, errors = await run_media_search("topic", domain=domain, serper_api_key="k")

    assert len(candidates) == 2
    sources = {r.source for r in candidates}
    assert "youtube" in sources
    assert "twitter" in sources
    assert errors == {}


@pytest.mark.asyncio
async def test_reddit_included_when_flag_on():
    with (
        patch(
            "agents.media_search.agent._formulate_queries",
            new_callable=AsyncMock,
            return_value=['"keyword"'],
        ),
        patch("agents.media_search.agent.search_videos", new_callable=AsyncMock, return_value=[]),
        patch("agents.media_search.agent.search_site", new_callable=AsyncMock, return_value=[]),
        patch("agents.media_search.agent.search_images", new_callable=AsyncMock, return_value=[]),
        patch(
            "agents.media_search.agent.search_reddit", new_callable=AsyncMock, return_value=[_RD]
        ),
    ):
        domain = DomainConfig(name="t", description="t", youtube_search=True, reddit_search=True)
        candidates, _errors = await run_media_search("topic", domain=domain, serper_api_key="k")

    assert any(c.source == "reddit" for c in candidates)


@pytest.mark.asyncio
async def test_deduplicates_urls():
    dup = EmbedCandidate(url="https://youtube.com/watch?v=1", title="dup", source="youtube")
    with (
        patch(
            "agents.media_search.agent._formulate_queries",
            new_callable=AsyncMock,
            return_value=['"kw"'],
        ),
        patch(
            "agents.media_search.agent.search_videos",
            new_callable=AsyncMock,
            return_value=[_YT, dup],
        ),
        patch("agents.media_search.agent.search_site", new_callable=AsyncMock, return_value=[]),
        patch("agents.media_search.agent.search_images", new_callable=AsyncMock, return_value=[]),
        patch("agents.media_search.agent.search_reddit", new_callable=AsyncMock, return_value=[]),
    ):
        domain = DomainConfig(name="t", description="t", youtube_search=True)
        candidates, _ = await run_media_search("topic", domain=domain, serper_api_key="k")

    assert len(candidates) == 1


@pytest.mark.asyncio
async def test_skips_failed_source_silently():
    with (
        patch(
            "agents.media_search.agent._formulate_queries",
            new_callable=AsyncMock,
            return_value=['"kw"'],
        ),
        patch(
            "agents.media_search.agent.search_videos",
            new_callable=AsyncMock,
            side_effect=Exception("network error"),
        ),
        patch("agents.media_search.agent.search_site", new_callable=AsyncMock, return_value=[_TW]),
        patch("agents.media_search.agent.search_images", new_callable=AsyncMock, return_value=[]),
        patch("agents.media_search.agent.search_reddit", new_callable=AsyncMock, return_value=[]),
    ):
        domain = DomainConfig(name="t", description="t", youtube_search=True, twitter_search=True)
        candidates, errors = await run_media_search("topic", domain=domain, serper_api_key="k")

    assert len(candidates) == 1
    assert candidates[0].source == "twitter"
    assert "youtube" in errors
    assert "network error" in errors["youtube"]
