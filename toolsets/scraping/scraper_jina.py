from __future__ import annotations

import httpx

from agents._base.types import ScrapedPage
from toolsets.scraping.rate_limiter import get_jina_semaphore

_JINA_BASE = "https://r.jina.ai"
_MIN_CONTENT_LENGTH = 100


async def scrape_with_jina(
    url: str,
    *,
    api_key: str | None,
    timeout: float = 30.0,
) -> ScrapedPage | None:
    """Tier-2 scraper: Jina Reader managed headless. Returns None on error or empty content.

    Uses global semaphore — max 8 concurrent requests (≈480 RPM at free tier 500 RPM).
    """
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    semaphore = get_jina_semaphore()
    async with semaphore:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(f"{_JINA_BASE}/{url}", headers=headers)
                response.raise_for_status()
                content = response.text.strip()
        except (httpx.HTTPStatusError, httpx.HTTPError, httpx.TimeoutException):
            return None

    if len(content) < _MIN_CONTENT_LENGTH:
        return None

    title = _extract_title_from_markdown(content)
    return ScrapedPage(url=url, title=title, content=content, scrape_tier="jina")


def _extract_title_from_markdown(content: str) -> str:
    """Extract title from first Markdown line (# Title)."""
    first_line = content.split("\n")[0].strip()
    if first_line.startswith("#"):
        return first_line.lstrip("#").strip()
    return ""
