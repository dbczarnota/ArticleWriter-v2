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
    """Fetches X.com posts + replies via Apify's twitter-scraper actor.

    Uses Apify's residential proxies + managed auth — bypasses X's API
    restrictions. Returns tweet text, author, and up to 20 replies.
    Requires an Apify API token.
    """

    _ACTOR = "apify~twitter-scraper"
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
                    "maxTweets": 1,
                    "replies": True,
                    "maxReplies": _MAX_REPLIES,
                    "addUserInfo": True,
                },
            )
            r.raise_for_status()
            items: list[dict] = r.json()

        if not items:
            raise RuntimeError(f"Apify returned no items for {tweet_url!r}")
        return self._parse_item(items[0])

    def _parse_item(self, item: dict) -> XPost:
        # Tweet text — try common field names across actor versions
        text = (
            item.get("text")
            or item.get("full_text")
            or item.get("content")
            or ""
        )

        # Author username
        author_obj = item.get("author") or item.get("user") or {}
        author = (
            author_obj.get("userName")
            or author_obj.get("screen_name")
            or item.get("authorUsername")
            or "unknown"
        )

        # Replies
        raw_replies: list[dict] = item.get("replies") or item.get("tweetReplies") or []
        comments: list[str] = []
        for reply in raw_replies[:_MAX_REPLIES]:
            reply_text = reply.get("text") or reply.get("full_text") or ""
            if not reply_text:
                continue
            reply_author_obj = reply.get("author") or reply.get("user") or {}
            reply_author = (
                reply_author_obj.get("userName")
                or reply_author_obj.get("screen_name")
                or ""
            )
            if reply_author:
                comments.append(f"@{reply_author}: {reply_text}")
            else:
                comments.append(reply_text)

        return XPost(text=text, author=author, comments=comments)
