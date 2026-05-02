from __future__ import annotations

import httpx
import trafilatura

from agents._base.types import ScrapedPage

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl,en;q=0.5",
}
_MIN_CONTENT_LENGTH = 100


async def scrape_with_httpx(url: str, timeout: float = 15.0) -> ScrapedPage | None:
    """Tier-1 scraper: httpx + trafilatura. Returns None on HTTP error or empty content."""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=_HEADERS)
            response.raise_for_status()
            html = response.text
    except (httpx.HTTPStatusError, httpx.HTTPError, httpx.TimeoutException):
        return None

    content = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        no_fallback=False,
    )
    if not content or len(content.strip()) < _MIN_CONTENT_LENGTH:
        return None

    title = _extract_title(html)
    return ScrapedPage(url=url, title=title, content=content, scrape_tier="httpx")


def _extract_title(html: str) -> str:
    """Extract <title> from HTML. Fallback: empty string."""
    start = html.lower().find("<title>")
    end = html.lower().find("</title>")
    if start != -1 and end != -1 and end > start:
        return html[start + 7 : end].strip()
    return ""
