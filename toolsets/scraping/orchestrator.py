from __future__ import annotations

import asyncio

from agents._base.config import ScrapingConfig
from agents._base.types import ScrapedPage
from toolsets.scraping.scraper_httpx import scrape_with_httpx
from toolsets.scraping.scraper_jina import scrape_with_jina


async def scrape_url(
    url: str,
    *,
    config: ScrapingConfig,
    jina_api_key: str | None,
) -> ScrapedPage | None:
    """Scrape a URL with tier-1 (httpx) → tier-2 (Jina) fallback."""
    page = await scrape_with_httpx(url, timeout=config.httpx_timeout)
    if page is not None:
        return page
    return await scrape_with_jina(url, api_key=jina_api_key, timeout=config.jina_timeout)


async def scrape_urls(
    urls: list[str],
    *,
    config: ScrapingConfig,
    jina_api_key: str | None,
) -> list[ScrapedPage]:
    """Scrape multiple URLs concurrently. Drops URLs that returned None."""
    results = await asyncio.gather(
        *[scrape_url(url, config=config, jina_api_key=jina_api_key) for url in urls]
    )
    return [page for page in results if page is not None]
