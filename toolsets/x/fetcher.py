# toolsets/x/fetcher.py
"""X.com (Twitter) post fetcher — Protocol-based, swappable implementation."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

import httpx

_MAX_REPLIES = 20


@dataclass
class XPost:
    text: str
    author: str          # @username of the post author
    comments: list[str] = field(default_factory=list)  # "@username: reply text"


class XFetcher(Protocol):
    async def fetch(self, tweet_url: str) -> XPost: ...


def parse_tweet_url(url: str) -> str:
    """Validate tweet URL and return it normalised (x.com canonical form)."""
    m = re.search(r"(?:twitter\.com|x\.com)/(\w+)/status/(\d+)", url)
    if not m:
        raise ValueError(f"Cannot parse tweet URL from: {url!r}")
    return f"https://x.com/{m.group(1)}/status/{m.group(2)}"


class ApifyXFetcher:
    """Fetches X.com posts + replies via Apify's twitter-reply-scraper actor.

    Actor: louisdeconinck/twitter-reply-scraper
    Returns tweet text, author handle, and up to 20 replies with usernames.
    Requires an Apify API token.
    """

    _ACTOR = "louisdeconinck~twitter-reply-scraper"
    _RUN_URL = f"https://api.apify.com/v2/acts/{_ACTOR}/run-sync-get-dataset-items"

    def __init__(self, api_token: str) -> None:
        self._token = api_token

    async def fetch(self, tweet_url: str) -> XPost:
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(
                self._RUN_URL,
                params={"token": self._token},
                json={
                    "startUrls": [{"url": tweet_url}],
                    "maxReplies": _MAX_REPLIES,
                },
            )
            r.raise_for_status()
            items: list[dict] = r.json()

        if not items:
            raise RuntimeError(f"Apify returned no items for {tweet_url!r}")
        return self._parse_item(items[0])

    def _parse_item(self, item: dict) -> XPost:
        # louisdeconinck/twitter-reply-scraper output fields
        text = item.get("tweetContent") or item.get("text") or item.get("full_text") or ""
        author = item.get("handle") or item.get("authorUsername") or "unknown"

        raw_replies: list[dict] = item.get("repliesData") or item.get("replies") or []
        comments: list[str] = []
        for reply in raw_replies[:_MAX_REPLIES]:
            reply_text = reply.get("tweetContent") or reply.get("text") or ""
            if not reply_text:
                continue
            reply_author = reply.get("handle") or reply.get("authorUsername") or ""
            if reply_author:
                comments.append(f"@{reply_author}: {reply_text}")
            else:
                comments.append(reply_text)

        return XPost(text=text, author=author, comments=comments)
