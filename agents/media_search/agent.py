# agents/media_search/agent.py
from __future__ import annotations
import asyncio
from agents._base.types import EmbedCandidate
from domains._base.config import DomainConfig
from toolsets.scraping.serper import search_site, search_videos

_SITE_MAP: dict[str, tuple[str, str]] = {
    "twitter_search":   ("x.com",           "twitter"),
    "tiktok_search":    ("tiktok.com",       "tiktok"),
    "instagram_search": ("instagram.com",    "instagram"),
    "facebook_search":  ("facebook.com",     "facebook"),
}


async def run_media_search(
    topic: str,
    *,
    domain: DomainConfig,
    serper_api_key: str,
    max_per_source: int = 5,
) -> tuple[list[EmbedCandidate], dict[str, str]]:
    """Search for embed candidates (YouTube, social media) in parallel. No LLM.

    Returns (candidates, errors) where errors maps source name to error message.
    """
    coros: list = []
    labels: list[str] = []

    if domain.youtube_search:
        coros.append(search_videos(topic, num=max_per_source, api_key=serper_api_key))
        labels.append("youtube")

    for flag, (site, source) in _SITE_MAP.items():
        if getattr(domain, flag, False):
            coros.append(search_site(topic, site=site, source=source,
                                     num=max_per_source, api_key=serper_api_key))
            labels.append(source)

    if not coros:
        return [], {}

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
