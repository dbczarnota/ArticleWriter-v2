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
