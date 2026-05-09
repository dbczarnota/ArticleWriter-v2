# toolsets/instagram/fetcher.py
"""Instagram post fetcher — Protocol-based so the implementation can be
swapped (e.g. for a paid API) without touching callers."""
from __future__ import annotations

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
    """Free, no-auth fetcher using Instagram's reverse-engineered GraphQL API.

    Uses the legacy query_hash endpoint as primary and falls back to the newer
    POST /api/graphql endpoint. Both hit the same CDN-backed data. Instagram
    may rate-limit or block at any time — callers should treat errors as
    soft failures.
    """

    async def fetch(self, shortcode: str) -> InstagramPost:
        async with httpx.AsyncClient(
            timeout=15.0,
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
