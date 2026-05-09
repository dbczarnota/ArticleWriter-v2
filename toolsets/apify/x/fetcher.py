# toolsets/apify/x/fetcher.py
"""X.com (Twitter) post fetcher — Protocol-based, swappable implementation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from toolsets.apify._client import ApifyClient

_MAX_REPLIES = 20
_ACTOR = "xquik~x-tweet-scraper"


@dataclass
class XPost:
    text: str
    author: str  # @username of the post author
    comments: list[str] = field(default_factory=list)  # "@username: reply text"


class XFetcher(Protocol):
    async def fetch(self, tweet_url: str) -> XPost: ...


def parse_tweet_url(url: str) -> tuple[str, str]:
    """Validate tweet URL and return (username, tweet_id)."""
    m = re.search(r"(?:twitter\.com|x\.com)/(\w+)/status/(\d+)", url)
    if not m:
        raise ValueError(f"Cannot parse tweet URL from: {url!r}")
    return m.group(1), m.group(2)


class ApifyXFetcher:
    """Fetches X.com posts via xquik~x-tweet-scraper.

    Uses tweetIds lookup — $0.15 per 1 000 tweets (~$0.00015/tweet).
    Author is parsed from the URL (always present in the URL).
    Replies are not currently available via this actor.
    """

    def __init__(self, api_token: str) -> None:
        self._client = ApifyClient(api_token)

    async def fetch(self, tweet_url: str) -> XPost:
        username, tweet_id = parse_tweet_url(tweet_url)

        result = await self._client.run_actor(
            _ACTOR,
            {"tweetIds": [tweet_id], "maxItems": 1},
            service="x",
        )

        # Actor returns a diagnostic dict on zero results
        text = ""
        for item in result.items:
            candidate = item.get("text") or item.get("full_text") or ""
            if candidate and not item.get("status"):  # skip diagnostic objects
                text = candidate
                break

        if not text:
            raise RuntimeError(f"xquik returned no tweet for id {tweet_id!r} (url: {tweet_url!r})")

        return XPost(text=text, author=username, comments=[])
