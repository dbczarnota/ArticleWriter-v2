# toolsets/instagram/fetcher.py
"""Instagram post fetcher — Protocol-based so the implementation can be
swapped (e.g. for a paid API) without touching callers."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Protocol

import httpx


@dataclass
class InstagramPost:
    media_bytes: bytes
    media_type: str  # "image/jpeg" or "video/mp4"
    description: str
    comments: list[str] = field(default_factory=list)


class InstagramFetcher(Protocol):
    async def fetch(self, shortcode: str) -> InstagramPost: ...


def parse_shortcode(url: str) -> str:
    """Extract shortcode from any Instagram post/reel/tv URL."""
    m = re.search(r"instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)", url)
    if not m:
        raise ValueError(f"Cannot parse Instagram shortcode from: {url!r}")
    return m.group(1)


_APP_ID = "936619743392459"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_MAX_COMMENTS = 20


class HttpxInstagramFetcher:
    """Free, no-auth fetcher.

    Tries three approaches in order:
    1. Legacy GET /graphql/query/ (query_hash)
    2. POST /api/graphql (doc_id)
    3. Page HTML → JSON-LD (most reliable from server IPs — Instagram serves
       structured SEO data even when it blocks internal API calls)
    Instagram may rate-limit or block at any time.
    """

    async def fetch(self, shortcode: str) -> InstagramPost:
        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={
                "User-Agent": _USER_AGENT,
                "x-ig-app-id": _APP_ID,
                "Accept": "*/*",
                "Accept-Language": "pl,en;q=0.9",
                "Referer": f"https://www.instagram.com/p/{shortcode}/",
                "Origin": "https://www.instagram.com",
            },
        ) as client:
            data = await self._fetch_legacy(client, shortcode)
            if data is None:
                data = await self._fetch_graphql(client, shortcode)
            if data is None:
                data = await self._fetch_webpage(client, shortcode)
            if data is None:
                raise RuntimeError(
                    f"All Instagram fetch methods failed for shortcode {shortcode!r}"
                )
            return data

    async def _fetch_legacy(
        self, client: httpx.AsyncClient, shortcode: str
    ) -> InstagramPost | None:
        """Legacy GET /graphql/query/ with query_hash."""
        try:
            r = await client.get(
                "https://www.instagram.com/graphql/query/",
                params={
                    "query_hash": "2c5d4d8b70cad329c4a6ebe3abb6eedd",
                    "variables": f'{{"shortcode":"{shortcode}"}}',
                },
            )
            if r.status_code != 200:
                return None
            item = r.json().get("data", {}).get("shortcode_media")
            if not item:
                return None
            return await self._parse_legacy_item(client, item)
        except Exception:
            return None

    async def _fetch_graphql(
        self, client: httpx.AsyncClient, shortcode: str
    ) -> InstagramPost | None:
        """Newer POST /api/graphql endpoint — more stable for reels."""
        try:
            r = await client.post(
                "https://www.instagram.com/api/graphql",
                content=(
                    f"doc_id=10015901848480474"
                    f"&variables=%7B%22shortcode%22%3A%22{shortcode}%22%7D"
                ),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if r.status_code != 200:
                return None
            items = (
                r.json()
                .get("data", {})
                .get("xdt_api__v1__media__shortcode__web_info", {})
                .get("items", [])
            )
            if not items:
                return None
            return await self._parse_v1_item(client, items[0])
        except Exception:
            return None

    async def _parse_legacy_item(
        self, client: httpx.AsyncClient, item: dict
    ) -> InstagramPost:
        is_video = item.get("is_video", False)
        if is_video:
            media_url = item.get("video_url", "")
            media_type = "video/mp4"
        else:
            # Carousel: take first image
            carousel = item.get("edge_sidecar_to_children", {}).get("edges", [])
            if carousel:
                media_url = carousel[0]["node"].get("display_url", "")
            else:
                media_url = item.get("display_url", "")
            media_type = "image/jpeg"

        description = (
            (item.get("edge_media_to_caption", {}).get("edges") or [{}])[0]
            .get("node", {})
            .get("text", "")
        )
        comments = [
            e["node"]["text"]
            for e in (item.get("edge_media_to_comment", {}).get("edges") or [])
            if e.get("node", {}).get("text")
        ][:_MAX_COMMENTS]

        media_bytes = (await client.get(media_url)).content
        return InstagramPost(
            media_bytes=media_bytes,
            media_type=media_type,
            description=description,
            comments=comments,
        )

    async def _parse_v1_item(
        self, client: httpx.AsyncClient, item: dict
    ) -> InstagramPost:
        video_versions = item.get("video_versions") or []
        if video_versions:
            media_url = video_versions[0]["url"]
            media_type = "video/mp4"
        else:
            carousel = item.get("carousel_media") or []
            if carousel:
                candidates = carousel[0].get("image_versions2", {}).get("candidates") or []
            else:
                candidates = item.get("image_versions2", {}).get("candidates") or []
            media_url = candidates[0]["url"] if candidates else ""
            media_type = "image/jpeg"

        description = (item.get("caption") or {}).get("text", "")
        comments = [
            e["node"]["text"]
            for e in (item.get("preview_comments", {}).get("edges") or [])
            if e.get("node", {}).get("text")
        ][:_MAX_COMMENTS]

        media_bytes = (await client.get(media_url)).content
        return InstagramPost(
            media_bytes=media_bytes,
            media_type=media_type,
            description=description,
            comments=comments,
        )

    async def _fetch_webpage(
        self, client: httpx.AsyncClient, shortcode: str
    ) -> InstagramPost | None:
        """Third fallback: parse JSON-LD from the public page HTML.

        Instagram serves structured SEO data (<script type="application/ld+json">)
        even when its internal API endpoints are blocked for server IPs.
        This gives caption + image/video URL, but no comments.
        """
        try:
            r = await client.get(
                f"https://www.instagram.com/p/{shortcode}/",
                headers={
                    "User-Agent": _USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "pl,en;q=0.9",
                },
            )
            if r.status_code != 200:
                return None

            for match in re.finditer(
                r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
                r.text,
                re.DOTALL,
            ):
                try:
                    blob = json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue
                if isinstance(blob, list):
                    blob = blob[0] if blob else {}
                if not isinstance(blob, dict):
                    continue

                description = blob.get("caption") or blob.get("headline") or ""

                media_url = ""
                media_type = "image/jpeg"
                videos = blob.get("video") or []
                if isinstance(videos, list) and videos:
                    media_url = videos[0].get("contentUrl") or videos[0].get("url", "")
                    media_type = "video/mp4"
                if not media_url:
                    img = blob.get("image") or blob.get("thumbnailUrl") or ""
                    if isinstance(img, list):
                        img = img[0] if img else ""
                    media_url = str(img)

                if not description and not media_url:
                    continue

                media_bytes = b""
                if media_url:
                    try:
                        media_resp = await client.get(media_url)
                        if media_resp.status_code == 200:
                            media_bytes = media_resp.content
                    except Exception:
                        pass

                return InstagramPost(
                    media_bytes=media_bytes,
                    media_type=media_type,
                    description=description,
                    comments=[],
                )
        except Exception:
            pass
        return None


class ApifyInstagramFetcher:
    """Reliable fetcher using Apify's instagram-scraper actor.

    Uses Apify's residential proxies + managed sessions — gets past
    Instagram's IP blocks and returns caption + up to 20 comments.
    Requires an Apify API token (APIFY_API_TOKEN env var).
    Runs synchronously server-side; typical latency 30–90 s.
    """

    _ACTOR = "apify~instagram-scraper"
    _RUN_URL = f"https://api.apify.com/v2/acts/{_ACTOR}/run-sync-get-dataset-items"

    def __init__(self, api_token: str) -> None:
        self._token = api_token

    async def fetch(self, shortcode: str) -> InstagramPost:
        post_url = f"https://www.instagram.com/p/{shortcode}/"
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(
                self._RUN_URL,
                params={"token": self._token},
                json={
                    "directUrls": [post_url],
                    "resultsType": "posts",
                    "resultsLimit": 1,
                    "addParentData": False,
                    "maxCommentsCount": _MAX_COMMENTS,
                    "commentsMode": "RANKED_UNFILTERED",
                },
            )
            r.raise_for_status()
            items: list[dict] = r.json()
        if not items:
            raise RuntimeError(f"Apify returned no items for shortcode {shortcode!r}")
        return await self._parse_item(items[0])

    async def _parse_item(self, item: dict) -> InstagramPost:
        video_url = item.get("videoUrl") or ""
        if video_url:
            media_url = video_url
            media_type = "video/mp4"
        else:
            images: list[str] = item.get("images") or []
            media_url = images[0] if images else (item.get("displayUrl") or "")
            media_type = "image/jpeg"

        description = item.get("caption") or ""
        comments = [
            f"@{c['ownerUsername']}: {c['text']}" if c.get("ownerUsername") else c["text"]
            for c in (item.get("latestComments") or [])
            if c.get("text")
        ][:_MAX_COMMENTS]

        media_bytes = b""
        if media_url:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                try:
                    resp = await client.get(media_url)
                    if resp.status_code == 200:
                        media_bytes = resp.content
                except Exception:
                    pass

        return InstagramPost(
            media_bytes=media_bytes,
            media_type=media_type,
            description=description,
            comments=comments,
        )
