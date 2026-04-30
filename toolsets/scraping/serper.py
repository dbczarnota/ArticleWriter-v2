from __future__ import annotations
import httpx
from agents._base.types import EmbedCandidate, SearchResult

_BASE = "https://google.serper.dev"


def _lang_payload(language: str) -> dict:
    code = language[:2]
    return {"gl": code, "hl": code, "lr": f"lang_{code}"}


async def search(
    query: str,
    *,
    num: int = 10,
    freshness: str = "qdr:w",
    language: str = "pl",
    api_key: str,
) -> list[SearchResult]:
    """Google web search via Serper."""
    payload = {"q": query, "num": num, "tbs": freshness, **_lang_payload(language)}
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(f"{_BASE}/search", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    return [
        SearchResult(url=item["link"], title=item["title"],
                     snippet=item.get("snippet", ""), source="web")
        for item in data.get("organic", [])
    ]


async def search_news(
    query: str,
    *,
    num: int = 10,
    language: str = "pl",
    api_key: str,
) -> list[SearchResult]:
    """Google News via Serper /news endpoint."""
    payload = {"q": query, "num": num, **_lang_payload(language)}
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(f"{_BASE}/news", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    return [
        SearchResult(url=item["link"], title=item["title"],
                     snippet=item.get("snippet", ""), source="web")
        for item in data.get("news", [])
    ]


async def search_videos(
    query: str,
    *,
    num: int = 5,
    language: str = "pl",
    api_key: str,
) -> list[EmbedCandidate]:
    """YouTube video search via Serper /videos endpoint."""
    payload = {"q": query, "num": num, **_lang_payload(language)}
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(f"{_BASE}/videos", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    return [
        EmbedCandidate(
            url=item["link"],
            title=item["title"],
            source="youtube",
            thumbnail_url=item.get("imageUrl"),
            description=item.get("snippet", ""),
            channel=item.get("channel", ""),
        )
        for item in data.get("videos", [])
    ]


async def search_site(
    query: str,
    *,
    site: str,
    source: str,
    num: int = 5,
    language: str = "pl",
    api_key: str,
) -> list[EmbedCandidate]:
    """Web search filtered to a specific site (Twitter, TikTok, Instagram, Facebook)."""
    payload = {"q": f"site:{site} {query}", "num": num, **_lang_payload(language)}
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(f"{_BASE}/search", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    return [
        EmbedCandidate(
            url=item["link"],
            title=item["title"],
            source=source,  # type: ignore[arg-type]
            description=item.get("snippet", ""),
        )
        for item in data.get("organic", [])
    ]
