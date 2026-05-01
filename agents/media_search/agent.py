# agents/media_search/agent.py
from __future__ import annotations
import asyncio
from pydantic import BaseModel
from pydantic_ai import Agent
from agents._base.types import EmbedCandidate
from domains._base.config import DomainConfig
from toolsets.scraping.serper import search_images, search_reddit, search_site, search_videos


_SITE_MAP: dict[str, tuple[str, str]] = {
    "twitter_search":   ("x.com",           "twitter"),
    "facebook_search":  ("facebook.com",     "facebook"),
}

_IMAGE_SITE_MAP: dict[str, str] = {
    "instagram_search": "site:instagram.com/reel/",
    "tiktok_search":    "site:tiktok.com/video/",
}


class _MediaKeywords(BaseModel):
    keywords: list[str]


async def _formulate_query(topic: str, model: str) -> str:
    """Use a cheap LLM to extract 2-3 English keywords from the topic for social media search."""
    agent = Agent(
        model,
        output_type=_MediaKeywords,
        system_prompt=(
            "Extract 2-4 short English keywords from the given topic for social media search. "
            "Return proper nouns and key concepts only — no filler words. "
            "If topic is in another language, translate the key names/concepts to English."
        ),
    )
    result = await agent.run(f"Topic: {topic}")
    return " ".join(f'"{kw}"' for kw in result.output.keywords[:4])


async def run_media_search(
    topic: str,
    *,
    domain: DomainConfig,
    serper_api_key: str,
    max_per_source: int = 5,
    query_model: str = "google-gla:gemini-2.5-flash-lite",
) -> tuple[list[EmbedCandidate], dict[str, str]]:
    """Search for embed candidates (YouTube, social media, Reddit) in parallel. No LLM for scraping.

    Returns (candidates, errors) where errors maps source name to error message.
    """
    has_any = (
        domain.youtube_search
        or domain.twitter_search
        or domain.facebook_search
        or domain.instagram_search
        or domain.tiktok_search
        or domain.reddit_search
    )
    if not has_any:
        return [], {}

    # Formulate short English query for site: searches
    media_query = await _formulate_query(topic, query_model)

    coros: list = []
    labels: list[str] = []

    if domain.youtube_search:
        coros.append(search_videos(topic, num=max_per_source, api_key=serper_api_key))
        labels.append("youtube")

    for flag, (site, source) in _SITE_MAP.items():
        if getattr(domain, flag, False):
            coros.append(search_site(media_query, site=site, source=source,
                                     num=max_per_source, api_key=serper_api_key))
            labels.append(source)

    for flag, site_prefix in _IMAGE_SITE_MAP.items():
        if getattr(domain, flag, False):
            query = f"{site_prefix} {media_query}"
            coros.append(search_images(query, num=max_per_source, api_key=serper_api_key))
            labels.append(flag.replace("_search", ""))

    if domain.reddit_search:
        # Reddit uses topic keywords without quotes
        reddit_query = " ".join(kw.strip('"') for kw in media_query.split())
        coros.append(search_reddit(reddit_query, num=max_per_source))
        labels.append("reddit")

    batches = await asyncio.gather(*coros, return_exceptions=True)

    candidates: list[EmbedCandidate] = []
    errors: dict[str, str] = {}
    seen_urls: set[str] = set()
    for label, batch in zip(labels, batches):
        if isinstance(batch, Exception):
            errors[label] = str(batch)
            continue
        for c in batch:
            if c.url not in seen_urls:
                seen_urls.add(c.url)
                candidates.append(c)

    return candidates, errors
