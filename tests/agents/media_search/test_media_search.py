import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from agents._base.types import EmbedCandidate
from domains._base.config import DomainConfig
from agents.media_search.agent import run_media_search

_DOMAIN_ALL = DomainConfig(
    name="test", description="t",
    youtube_search=True, twitter_search=True,
    tiktok_search=True, instagram_search=True, facebook_search=True,
)
_DOMAIN_NONE = DomainConfig(name="test", description="t")

_YT = EmbedCandidate(url="https://youtube.com/watch?v=1", title="YT", source="youtube")
_TW = EmbedCandidate(url="https://x.com/u/status/1", title="Tweet", source="twitter")


def test_returns_empty_when_all_flags_off():
    result = asyncio.run(run_media_search("topic", domain=_DOMAIN_NONE, serper_api_key="k"))
    assert result == []


@pytest.mark.asyncio
async def test_aggregates_results_from_enabled_sources():
    with (
        patch("agents.media_search.agent.search_videos", new_callable=AsyncMock) as m_yt,
        patch("agents.media_search.agent.search_site", new_callable=AsyncMock) as m_site,
    ):
        m_yt.return_value = [_YT]
        m_site.return_value = [_TW]

        domain = DomainConfig(name="t", description="t", youtube_search=True, twitter_search=True)
        results = await run_media_search("topic", domain=domain, serper_api_key="k")

    assert len(results) == 2
    sources = {r.source for r in results}
    assert "youtube" in sources
    assert "twitter" in sources


@pytest.mark.asyncio
async def test_deduplicates_urls():
    dup = EmbedCandidate(url="https://youtube.com/watch?v=1", title="dup", source="youtube")
    with (
        patch("agents.media_search.agent.search_videos", new_callable=AsyncMock) as m_yt,
        patch("agents.media_search.agent.search_site", new_callable=AsyncMock) as m_site,
    ):
        m_yt.return_value = [_YT, dup]
        m_site.return_value = []

        domain = DomainConfig(name="t", description="t", youtube_search=True, twitter_search=True)
        results = await run_media_search("topic", domain=domain, serper_api_key="k")

    assert len(results) == 1


@pytest.mark.asyncio
async def test_skips_failed_source_silently():
    with (
        patch("agents.media_search.agent.search_videos", new_callable=AsyncMock) as m_yt,
        patch("agents.media_search.agent.search_site", new_callable=AsyncMock) as m_site,
    ):
        m_yt.side_effect = Exception("network error")
        m_site.return_value = [_TW]

        domain = DomainConfig(name="t", description="t", youtube_search=True, twitter_search=True)
        results = await run_media_search("topic", domain=domain, serper_api_key="k")

    assert len(results) == 1
    assert results[0].source == "twitter"
