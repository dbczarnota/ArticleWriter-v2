from __future__ import annotations

import os

import httpx
import logfire

from agents._base.run_context import record_serper_query
from agents._base.types import EmbedCandidate, SearchResult

_BASE = "https://google.serper.dev"
_SERPER_COST_PER_QUERY = float(os.environ.get("SERPER_COST_PER_QUERY_USD", "0.001"))


def _lang_payload(language: str) -> dict:
    code = language[:2]
    return {"gl": code, "hl": code, "lr": f"lang_{code}"}


def _log_serper_results(
    endpoint: str,
    query: str,
    items: list[dict],
    *,
    link_key: str = "link",
    title_key: str = "title",
    snippet_key: str = "snippet",
    cost_usd: float = _SERPER_COST_PER_QUERY,
) -> None:
    """Emit a structured `serper.results` event with the response shape.

    Auto-instrumented httpx spans only carry method/url/status/duration —
    they don't capture the response body. This event makes the actual
    items Serper returned (URL + title + first ~200 chars of snippet)
    queryable in Logfire by article_id + endpoint, so a post-mortem can
    see exactly what the LLM got handed without re-running the search.

    cost_usd is the estimated monetary cost of this query ($0.001 per Serper
    request, $0.0 for free endpoints like Reddit). With article_id propagated
    via OTEL baggage, Logfire can SUM(cost_usd) GROUP BY article_id or org_code.
    """
    summarized = [
        {
            "url": item.get(link_key, ""),
            "title": (item.get(title_key, "") or "")[:200],
            "snippet": (item.get(snippet_key, "") or "")[:300],
        }
        for item in items[:10]
    ]
    logfire.info(
        "serper.results",
        endpoint=endpoint,
        query=query,
        result_count=len(items),
        results=summarized,
        cost_usd=cost_usd,
    )
    if cost_usd > 0:
        record_serper_query(endpoint)


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
    organic = data.get("organic", [])
    _log_serper_results("/search", query, organic)
    return [
        SearchResult(
            url=item["link"], title=item["title"], snippet=item.get("snippet", ""), source="web"
        )
        for item in organic
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
    news = data.get("news", [])
    _log_serper_results("/news", query, news)
    return [
        SearchResult(
            url=item["link"], title=item["title"], snippet=item.get("snippet", ""), source="web"
        )
        for item in news
    ]


async def search_videos(
    query: str,
    *,
    num: int = 5,
    sort_by_date: bool = False,
    _language: str = "pl",
    api_key: str,
) -> list[EmbedCandidate]:
    """YouTube video search via Serper /videos endpoint.

    sort_by_date=True adds tbs=sbd:1 (Google sort-by-date). tbs freshness
    filtering is not supported by this endpoint.
    Only youtube.com and youtu.be results are returned.
    """
    payload: dict = {"q": query, "num": num}
    if sort_by_date:
        payload["tbs"] = "sbd:1"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(f"{_BASE}/videos", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    videos = data.get("videos", [])
    _log_serper_results("/videos", query, videos)
    return [
        EmbedCandidate(
            url=item["link"],
            title=item["title"],
            source="youtube",
            thumbnail_url=item.get("imageUrl"),
            description=item.get("snippet", ""),
            channel=item.get("channel", ""),
        )
        for item in videos
        if "youtube.com" in item.get("link", "") or "youtu.be" in item.get("link", "")
    ]


async def search_images(
    query: str,
    *,
    num: int = 5,
    freshness: str = "",
    api_key: str,
) -> list[EmbedCandidate]:
    """Google Images via Serper /images — useful for finding Instagram/TikTok thumbnails."""
    payload: dict = {"q": query, "num": num}
    if freshness:
        payload["tbs"] = freshness
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(f"{_BASE}/images", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    images = data.get("images", [])
    _log_serper_results("/images", query, images)

    results = []
    for item in images:
        link = item.get("link", "")
        source: str
        if "instagram.com" in link:
            source = "instagram"
        elif "tiktok.com" in link:
            source = "tiktok"
        elif "x.com" in link or "twitter.com" in link:
            source = "twitter"
        else:
            continue  # skip non-social images
        results.append(
            EmbedCandidate(
                url=link,
                title=item.get("title", ""),
                source=source,  # type: ignore[arg-type]
                thumbnail_url=item.get("imageUrl"),
            )
        )
    return results


_REDDIT_TIME = {"qdr:h": "hour", "qdr:d": "day", "qdr:w": "week", "qdr:m": "month", "qdr:y": "year"}


async def search_reddit(
    query: str,
    *,
    num: int = 5,
    freshness: str = "",
    api_key: str = "",  # unused, Reddit JSON API needs no auth
) -> list[EmbedCandidate]:
    """Reddit search via Reddit's public JSON API — no auth required."""
    params = {
        "q": query,
        "sort": "top",
        "t": _REDDIT_TIME.get(freshness, "week"),
        "limit": num,
        "type": "link",
    }
    headers = {"User-Agent": "articlewriter/1.0"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            "https://www.reddit.com/search.json",
            params=params,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
    children = data.get("data", {}).get("children", [])
    # Reddit's shape is `{data: {url, title, ...}}` per child — flatten for the helper.
    # cost_usd=0.0: Reddit JSON API is free, no Serper credit consumed.
    _log_serper_results(
        "reddit/search.json",
        query,
        [c.get("data", {}) for c in children],
        link_key="url",
        snippet_key="selftext",
        cost_usd=0.0,
    )

    results = []
    for child in children:
        post = child.get("data", {})
        url = post.get("url", "")
        if not url:
            continue
        title = post.get("title", "")
        subreddit = post.get("subreddit_name_prefixed", "")
        permalink = f"https://reddit.com{post.get('permalink', '')}"
        results.append(
            EmbedCandidate(
                url=permalink,
                title=title,
                source="reddit",  # type: ignore[arg-type]
                description=f"{subreddit} · {post.get('score', 0)} points",
            )
        )
    return results


# Facebook returns photo permalinks as `/{page}/photos/{slug}/{photo_id}/`.
# When a post has no text (emoji-only / image-only / etc.) the slug becomes
# `d41d8cd9` — the first 8 chars of MD5(""), Facebook's empty-input
# placeholder. Google indexes these placeholder URLs and points them at
# arbitrary unrelated content on the same page, so title/snippet describe
# one post but the link goes to a different one. Reject them.
_FB_BROKEN_PLACEHOLDER = "/photos/d41d8cd9/"


def _facebook_url_is_reliable(url: str) -> bool:
    return _FB_BROKEN_PLACEHOLDER not in url


async def search_site(
    query: str,
    *,
    site: str,
    source: str,
    num: int = 5,
    freshness: str = "",
    _language: str = "pl",
    api_key: str,
) -> list[EmbedCandidate]:
    """Web search filtered to a specific site (Twitter, TikTok, Instagram, Facebook). No language restriction."""
    payload: dict = {"q": f"site:{site} {query}", "num": num}
    if freshness:
        payload["tbs"] = freshness
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(f"{_BASE}/search", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    organic = data.get("organic", [])
    _log_serper_results(f"/search site:{site}", query, organic)
    if site == "facebook.com":
        kept: list[dict] = []
        for item in organic:
            link = item.get("link", "")
            if _facebook_url_is_reliable(link):
                kept.append(item)
            else:
                logfire.warn(
                    "media_search.facebook_url_rejected",
                    reason="empty_slug_placeholder",
                    url=link,
                    title=item.get("title", ""),
                    query=query,
                )
        organic = kept
    return [
        EmbedCandidate(
            url=item["link"],
            title=item["title"],
            source=source,  # type: ignore[arg-type]
            description=item.get("snippet", ""),
        )
        for item in organic
    ]
