# toolsets/apify/x/fetcher.py
"""X.com (Twitter) post fetcher — Protocol-based, swappable implementation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from toolsets.apify._client import ApifyClient

_MAX_REPLIES = 20
_ACTOR = "apidojo~twitter-scraper-lite"


@dataclass
class XPost:
    text: str
    author: str  # @username of the post author
    comments: list[str] = field(default_factory=list)  # "@username: reply text"
    media_url: str = ""  # first media URL if tweet contains image/video (temporary CDN link)
    media_type: str = ""  # "image/jpeg" or "video/mp4"


class XFetcher(Protocol):
    async def fetch(self, tweet_url: str) -> XPost: ...


def parse_tweet_url(url: str) -> tuple[str, str]:
    """Validate tweet URL and return (username, tweet_id)."""
    m = re.search(r"(?:twitter\.com|x\.com)/(\w+)/status/(\d+)", url)
    if not m:
        raise ValueError(f"Cannot parse tweet URL from: {url!r}")
    return m.group(1), m.group(2)


class ApifyXFetcher:
    """Fetches X.com posts + replies via apidojo/twitter-scraper-lite.

    Two-step approach (single actor, two runs):
    1. Fetch tweet by URL  → extract text, author, numeric id
    2. Search conversation_id:{id} → fetch up to 20 replies

    Requires an Apify API token (subscription plan — free plan returns demo data).
    """

    def __init__(self, api_token: str) -> None:
        self._client = ApifyClient(api_token)

    async def fetch(self, tweet_url: str) -> XPost:
        username, _ = parse_tweet_url(tweet_url)

        # Step 1 — fetch the tweet itself
        step1 = await self._client.run_actor(
            _ACTOR,
            {"startUrls": [tweet_url], "maxItems": 1},
            service="x.tweet",
        )

        tweet = next(
            (i for i in step1.items if (i.get("text") or i.get("full_text")) and not i.get("demo")),
            None,
        )
        if tweet is None:
            raise RuntimeError(
                f"Apify returned no tweet for {tweet_url!r} "
                f"(items={step1.item_count}, check APIFY_API_TOKEN plan)"
            )

        text = tweet.get("full_text") or tweet.get("text") or ""
        author_obj = tweet.get("author") or {}
        author = (
            author_obj.get("userName")
            or author_obj.get("screen_name")
            or username  # fallback: parse from URL
        )
        tweet_id = str(tweet.get("id") or tweet.get("id_str") or "")

        # Step 2 — fetch replies via conversation_id search (best-effort)
        comments: list[str] = []
        if tweet_id:
            step2 = await self._client.run_actor(
                _ACTOR,
                {
                    "searchTerms": [f"conversation_id:{tweet_id}"],
                    "sort": "Latest",
                    "maxItems": _MAX_REPLIES,
                },
                service="x.replies",
            )
            for item in step2.items:
                reply_text = item.get("full_text") or item.get("text") or ""
                if not reply_text or item.get("demo") or str(item.get("id")) == tweet_id:
                    continue
                reply_author_obj = item.get("author") or {}
                reply_author = (
                    reply_author_obj.get("userName") or reply_author_obj.get("screen_name") or ""
                )
                if reply_author:
                    comments.append(f"@{reply_author}: {reply_text}")
                else:
                    comments.append(reply_text)

        # Best-effort media extraction.
        # extendedEntities is authoritative: .type tells us video vs photo,
        # and video_info.variants[] has the actual .mp4 URLs with bitrates.
        # mediaUrls (flat list) is a fallback — may contain thumbnail JPGs for videos.
        media_url = ""
        media_type = ""
        ext_media = (tweet.get("extendedEntities") or {}).get("media") or []
        if ext_media:
            m0 = ext_media[0]
            m_type = m0.get("type", "photo")
            if m_type in ("video", "animated_gif"):
                variants = (m0.get("video_info") or {}).get("variants") or []
                mp4 = [v for v in variants if v.get("content_type") == "video/mp4"]
                if mp4:
                    best = max(mp4, key=lambda v: v.get("bitrate") or 0)
                    media_url = best["url"]
                    media_type = "video/mp4"
                elif variants:
                    media_url = variants[0].get("url", "")
                    media_type = variants[0].get("content_type", "video/mp4")
            else:
                media_url = m0.get("media_url_https") or m0.get("url") or ""
                media_type = "image/jpeg"

        if not media_url:
            # fallback: mediaUrls flat list
            raw = tweet.get("mediaUrls") or []
            if raw and isinstance(raw, list):
                first = raw[0]
                if isinstance(first, str) and first:
                    media_url = first
                    is_video = "video.twimg.com" in media_url or ".mp4" in media_url
                    media_type = "video/mp4" if is_video else "image/jpeg"

        return XPost(
            text=text, author=author, comments=comments, media_url=media_url, media_type=media_type
        )
