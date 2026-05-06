"""RSS feed fetcher — httpx + feedparser, honors ETag and Last-Modified.

Returns a normalized FetchResult so callers don't need to know about
feedparser's untyped output."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import feedparser
import httpx
import logfire


class FeedFetchError(Exception):
    """Raised when the HTTP fetch fails (4xx / 5xx / network)."""


@dataclass
class RawFeedItem:
    title: str
    url: str
    guid: str | None
    summary: str | None
    published_at: datetime | None
    image_url: str | None = None


@dataclass
class FetchResult:
    items: list[RawFeedItem]
    etag: str | None
    last_modified: str | None
    not_modified: bool


def _parse_published(entry: dict) -> datetime | None:  # type: ignore[type-arg]
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    try:
        return datetime(*parsed[:6], tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def _parse_image(entry: dict) -> str | None:  # type: ignore[type-arg]
    """Best-effort extraction of an article hero image URL from RSS entry.

    Tries (in priority order):
    1. media:content with image type
    2. media:thumbnail
    3. enclosures of image/* type
    4. <img> in summary/content HTML

    Returns first absolute http(s) URL found, or None."""
    import re

    def _ok(url: object) -> str | None:
        if not isinstance(url, str):
            return None
        url = url.strip()
        if url.startswith("http://") or url.startswith("https://"):
            return url[:2048]
        return None

    media_content = entry.get("media_content") or []
    if isinstance(media_content, list):
        for m in media_content:
            if not isinstance(m, dict):
                continue
            mtype = str(m.get("type") or m.get("medium") or "")
            if mtype.startswith("image") or mtype == "image":
                got = _ok(m.get("url"))
                if got:
                    return got
        # Fall back to first media_content even without explicit image type.
        for m in media_content:
            if isinstance(m, dict):
                got = _ok(m.get("url"))
                if got:
                    return got

    media_thumbnail = entry.get("media_thumbnail") or []
    if isinstance(media_thumbnail, list):
        for m in media_thumbnail:
            if isinstance(m, dict):
                got = _ok(m.get("url"))
                if got:
                    return got

    enclosures = entry.get("enclosures") or []
    if isinstance(enclosures, list):
        for enc in enclosures:
            if isinstance(enc, dict) and str(enc.get("type") or "").startswith("image"):
                got = _ok(enc.get("href") or enc.get("url"))
                if got:
                    return got

    # Last resort: first <img src="..."> in the HTML body of summary/content.
    html_blobs: list[str] = []
    summary = entry.get("summary")
    if isinstance(summary, str):
        html_blobs.append(summary)
    content = entry.get("content")
    if isinstance(content, list):
        for c in content:
            if isinstance(c, dict):
                v = c.get("value")
                if isinstance(v, str):
                    html_blobs.append(v)
    for blob in html_blobs:
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', blob, re.IGNORECASE)
        if m:
            got = _ok(m.group(1))
            if got:
                return got
    return None


async def fetch_feed(
    feed_url: str,
    *,
    etag: str | None,
    last_modified: str | None,
    timeout_s: float = 15.0,
) -> FetchResult:
    headers: dict[str, str] = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        try:
            response = await client.get(feed_url, headers=headers)
        except httpx.HTTPError as e:
            raise FeedFetchError(f"network error: {e}") from e

    if response.status_code == 304:
        logfire.info(
            "discovery.feed.fetched",
            feed_url=feed_url,
            status_code=304,
            items_in_response=0,
            not_modified=True,
        )
        return FetchResult(items=[], etag=etag, last_modified=last_modified, not_modified=True)

    if response.status_code >= 400:
        raise FeedFetchError(f"HTTP {response.status_code} from {feed_url}")

    parsed = feedparser.parse(response.text)
    items: list[RawFeedItem] = []
    for entry in parsed.entries or []:
        link: str = str(entry.get("link") or "")
        title: str = str(entry.get("title") or "")
        if not link or not title:
            continue
        raw_guid = entry.get("id") or entry.get("guid")
        raw_summary = entry.get("summary")
        items.append(
            RawFeedItem(
                title=title,
                url=link,
                guid=str(raw_guid) if raw_guid is not None else None,
                summary=str(raw_summary) if raw_summary is not None else None,
                published_at=_parse_published(entry),
                image_url=_parse_image(entry),
            )
        )
    new_etag = response.headers.get("ETag")
    new_last_modified = response.headers.get("Last-Modified")
    logfire.info(
        "discovery.feed.fetched",
        feed_url=feed_url,
        status_code=response.status_code,
        items_in_response=len(items),
        not_modified=False,
    )
    return FetchResult(
        items=items, etag=new_etag, last_modified=new_last_modified, not_modified=False
    )
