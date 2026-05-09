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
    """Fetches X.com posts + replies via apidojo/twitter-scraper-lite.

    Two-step approach (single actor, two runs):
    1. Fetch tweet by URL → extract tweet text, author, and numeric id
    2. Search conversation_id:{id} → fetch up to 20 replies

    Cost: ~$0.07 per tweet+replies pair.
    Requires an Apify API token.
    """

    _ACTOR = "apidojo~twitter-scraper-lite"
    _RUN_URL = f"https://api.apify.com/v2/acts/{_ACTOR}/run-sync-get-dataset-items"

    def __init__(self, api_token: str) -> None:
        self._token = api_token

    async def fetch(self, tweet_url: str) -> XPost:
        # Step 1: fetch the tweet itself
        tweet_items = await self._run({"startUrls": [tweet_url], "maxItems": 1})
        if not tweet_items:
            raise RuntimeError(f"Apify returned no tweet for {tweet_url!r}")

        tweet = tweet_items[0]
        text = tweet.get("text") or tweet.get("full_text") or ""
        author_obj = tweet.get("author") or {}
        author = author_obj.get("userName") or author_obj.get("screen_name") or "unknown"
        tweet_id = tweet.get("id") or tweet.get("id_str") or ""

        # Step 2: fetch replies via conversation_id search
        comments: list[str] = []
        if tweet_id:
            reply_items = await self._run(
                {"searchTerms": [f"conversation_id:{tweet_id}"], "sort": "Latest", "maxItems": _MAX_REPLIES},
            )
            for item in reply_items:
                reply_text = item.get("text") or item.get("full_text") or ""
                if not reply_text or item.get("id") == tweet_id:
                    continue
                reply_author_obj = item.get("author") or {}
                reply_author = reply_author_obj.get("userName") or reply_author_obj.get("screen_name") or ""
                if reply_author:
                    comments.append(f"@{reply_author}: {reply_text}")
                else:
                    comments.append(reply_text)

        return XPost(text=text, author=author, comments=comments)

    async def _run(self, input_data: dict) -> list[dict]:
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(
                self._RUN_URL,
                params={"token": self._token},
                json=input_data,
            )
            r.raise_for_status()
            return r.json()
