from __future__ import annotations
import httpx
from agents._base.types import SearchResult

_SERPER_URL = "https://google.serper.dev/search"


async def search(
    query: str,
    *,
    num: int = 10,
    freshness: str = "qdr:w",
    language: str = "pl",
    api_key: str,
) -> list[SearchResult]:
    """Search via Serper.dev and return list of SearchResult."""
    payload = {
        "q": query,
        "num": num,
        "tbs": freshness,
        "gl": language[:2],
        "hl": language[:2],
    }
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(_SERPER_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    return [
        SearchResult(
            url=item["link"],
            title=item["title"],
            snippet=item.get("snippet", ""),
            source="web",
        )
        for item in data.get("organic", [])
    ]
