from unittest.mock import AsyncMock, patch

import pytest

from agents._base.config import ScrapingConfig
from agents._base.types import ScrapedPage
from toolsets.scraping.orchestrator import scrape_url, scrape_urls

_PAGE_HTTPX = ScrapedPage(
    url="https://example.com/art",
    title="Tytuł httpx",
    content="Treść zescrapowana przez httpx " * 10,
    scrape_tier="httpx",
)

_PAGE_JINA = ScrapedPage(
    url="https://example.com/art",
    title="Tytuł jina",
    content="Treść zescrapowana przez jina " * 10,
    scrape_tier="jina",
)


@pytest.mark.asyncio
async def test_scrape_url_returns_httpx_when_tier1_succeeds():
    with (
        patch(
            "toolsets.scraping.orchestrator.scrape_with_httpx", new_callable=AsyncMock
        ) as mock_httpx,
        patch(
            "toolsets.scraping.orchestrator.scrape_with_jina", new_callable=AsyncMock
        ) as mock_jina,
    ):
        mock_httpx.return_value = _PAGE_HTTPX
        page = await scrape_url(
            "https://example.com/art", config=ScrapingConfig(), jina_api_key=None
        )

    assert page is not None
    assert page.scrape_tier == "httpx"
    mock_jina.assert_not_called()


@pytest.mark.asyncio
async def test_scrape_url_falls_back_to_jina_when_tier1_fails():
    with (
        patch(
            "toolsets.scraping.orchestrator.scrape_with_httpx", new_callable=AsyncMock
        ) as mock_httpx,
        patch(
            "toolsets.scraping.orchestrator.scrape_with_jina", new_callable=AsyncMock
        ) as mock_jina,
    ):
        mock_httpx.return_value = None
        mock_jina.return_value = _PAGE_JINA
        page = await scrape_url(
            "https://example.com/art", config=ScrapingConfig(), jina_api_key="key"
        )

    assert page is not None
    assert page.scrape_tier == "jina"
    mock_httpx.assert_called_once()
    mock_jina.assert_called_once()


@pytest.mark.asyncio
async def test_scrape_url_returns_none_when_both_fail():
    with (
        patch(
            "toolsets.scraping.orchestrator.scrape_with_httpx", new_callable=AsyncMock
        ) as mock_httpx,
        patch(
            "toolsets.scraping.orchestrator.scrape_with_jina", new_callable=AsyncMock
        ) as mock_jina,
    ):
        mock_httpx.return_value = None
        mock_jina.return_value = None
        page = await scrape_url(
            "https://example.com/art", config=ScrapingConfig(), jina_api_key="key"
        )

    assert page is None


@pytest.mark.asyncio
async def test_scrape_urls_returns_successful_pages_only():
    urls = [
        "https://example.com/art1",
        "https://example.com/art2",
        "https://example.com/art3",
    ]

    async def fake_scrape(url, config, jina_api_key):
        if "art2" in url:
            return None
        return ScrapedPage(url=url, title="T", content="c " * 50, scrape_tier="httpx")

    with patch("toolsets.scraping.orchestrator.scrape_url", side_effect=fake_scrape):
        pages = await scrape_urls(urls, config=ScrapingConfig(), jina_api_key=None)

    assert len(pages) == 2
    assert all(p.scrape_tier == "httpx" for p in pages)
    assert not any("art2" in p.url for p in pages)


@pytest.mark.asyncio
async def test_scrape_urls_runs_concurrently():
    """scrape_urls uses asyncio.gather — all URLs scraped in parallel."""
    import asyncio
    import time

    async def fake_scrape(url, config, jina_api_key):
        await asyncio.sleep(0.05)
        return ScrapedPage(url=url, title="T", content="c " * 50, scrape_tier="httpx")

    urls = ["https://a.com", "https://b.com", "https://c.com"]
    with patch("toolsets.scraping.orchestrator.scrape_url", side_effect=fake_scrape):
        start = time.monotonic()
        await scrape_urls(urls, config=ScrapingConfig(), jina_api_key=None)
        elapsed = time.monotonic() - start

    # Sequential would take 3 × 0.05 = 0.15s; concurrent ~0.05s
    assert elapsed < 0.12, f"Took {elapsed:.3f}s — expected < 0.12s (concurrent)"
