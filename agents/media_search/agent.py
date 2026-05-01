from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING
from pydantic import BaseModel
from pydantic_ai import Agent
from agents._base.types import EmbedCandidate
from domains._base.config import DomainConfig
from toolsets.scraping.serper import search_images, search_reddit, search_site, search_videos

if TYPE_CHECKING:
    from agents._base.debug_log import PipelineLogger


_SITE_MAP: dict[str, tuple[str, str]] = {
    "twitter_search":   ("x.com",           "twitter"),
    "facebook_search":  ("facebook.com",     "facebook"),
}

_IMAGE_SITE_MAP: dict[str, str] = {
    "instagram_search": "site:instagram.com/reel/",
    "tiktok_search":    "site:tiktok.com/video/",
}


class _LangQuery(BaseModel):
    lang: str
    keywords: list[str]


class _MediaKeywords(BaseModel):
    queries: list[_LangQuery]


async def _formulate_queries(
    topic: str,
    model: str,
    languages: tuple[str, ...],
) -> list[str]:
    """LLM extracts 2-4 keywords for each requested language. Returns one quoted query per language."""
    lang_list = ", ".join(languages)
    agent = Agent(
        model,
        output_type=_MediaKeywords,
        system_prompt=(
            f"For each language in [{lang_list}], extract 2-4 short keywords from the topic "
            "for social media search. Return proper nouns and key concepts only — no filler words. "
            "Use the BCP-47 language code as the lang field (e.g. 'en', 'pl'). "
            "For non-English languages, use the native-language form of the keywords."
        ),
    )
    result = await agent.run(f"Topic: {topic}\nLanguages: {lang_list}")
    return [
        " ".join(f'"{kw}"' for kw in lq.keywords[:4])
        for lq in result.output.queries
    ] or [topic]


async def run_media_search(
    topic: str,
    *,
    domain: DomainConfig,
    serper_api_key: str,
    max_per_source: int | None = None,
    freshness: str = "",
    query_model: str = "google-gla:gemini-2.5-flash-lite",
    log: PipelineLogger | None = None,
) -> tuple[list[EmbedCandidate], dict[str, str]]:
    """Search for embed candidates (YouTube, social media, Reddit) in parallel.

    Queries are formulated in each language listed in domain.media_search_languages.
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

    num = max_per_source if max_per_source is not None else domain.media_search_num
    media_queries = await _formulate_queries(topic, query_model, domain.media_search_languages)

    if log:
        active = (
            [f for f in ("youtube", "twitter", "facebook") if getattr(domain, f"{f}_search", False)]
            + [f for f in ("instagram", "tiktok") if getattr(domain, f"{f}_search", False)]
            + (["reddit"] if domain.reddit_search else [])
        )
        log.media_search_start(domain.media_search_languages, active, media_queries)

    coros: list = []
    labels: list[str] = []

    if domain.youtube_search:
        # YouTube: no freshness filter — relevant videos are often days/weeks old
        coros.append(search_videos(topic, num=num, api_key=serper_api_key))
        labels.append("youtube")

    for flag, (site, source) in _SITE_MAP.items():
        if getattr(domain, flag, False):
            for i, mq in enumerate(media_queries):
                coros.append(search_site(mq, site=site, source=source, num=num,
                                         freshness=freshness, api_key=serper_api_key))
                labels.append(f"{source}@{i}")

    for flag, site_prefix in _IMAGE_SITE_MAP.items():
        if getattr(domain, flag, False):
            for i, mq in enumerate(media_queries):
                query = f"{site_prefix} {mq}"
                coros.append(search_images(query, num=num, freshness=freshness, api_key=serper_api_key))
                labels.append(f"{flag.replace('_search', '')}@{i}")

    if domain.reddit_search:
        # Reddit is English-dominant — use first query (expected to be English)
        first_query = media_queries[0] if media_queries else topic
        reddit_query = " ".join(kw.strip('"') for kw in first_query.split())
        coros.append(search_reddit(reddit_query, num=num, freshness=freshness))
        labels.append("reddit")

    batches = await asyncio.gather(*coros, return_exceptions=True)

    candidates: list[EmbedCandidate] = []
    errors: dict[str, str] = {}
    seen_urls: set[str] = set()
    for label, batch in zip(labels, batches):
        source_name = label.split("@")[0]
        if isinstance(batch, Exception):
            errors[source_name] = str(batch)
            continue
        for c in batch:
            if c.url not in seen_urls:
                seen_urls.add(c.url)
                candidates.append(c)

    return candidates, errors
