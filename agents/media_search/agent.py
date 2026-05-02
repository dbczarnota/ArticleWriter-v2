from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from pydantic import BaseModel
from pydantic_ai import Agent

from agents._base.run_context import record_agent_call
from agents._base.types import EmbedCandidate
from domains._base.config import DomainConfig
from toolsets.scraping.serper import search_images, search_reddit, search_site, search_videos

if TYPE_CHECKING:
    from agents._base.debug_log import PipelineLogger


_SITE_MAP: dict[str, tuple[str, str]] = {
    "twitter_search": ("x.com", "twitter"),
    "facebook_search": ("facebook.com", "facebook"),
}

_IMAGE_SITE_MAP: dict[str, str] = {
    "instagram_search": "site:instagram.com/reel/",
    "tiktok_search": "site:tiktok.com/video/",
}


class _LangQueryTiers(BaseModel):
    lang: str
    tiers: list[list[str]]  # ordered narrow → broad; each inner list = keywords for one query


class _MediaKeywords(BaseModel):
    queries: list[_LangQueryTiers]


async def _formulate_queries(
    topic: str,
    model: str,
    languages: tuple[str, ...],
) -> list[tuple[str, list[str]]]:
    """LLM produces 2-3 tiered keyword sets per language: narrow → broad fallback.

    Returns: [(lang, [tier0_query, tier1_query, ...]), ...]
    Each tier is a quoted-keywords string ready for Serper. Caller tries tier0 first per
    source; if it returns 0 results, tries tier1, etc., up to a configured max.
    """
    lang_list = ", ".join(languages)
    agent = Agent(
        model,
        output_type=_MediaKeywords,
        system_prompt=(
            "You build social-media search queries from a news topic. For each language requested, "
            "produce 2-3 query TIERS, ordered from narrow (most specific) to broad (just the main entity).\n\n"
            "Tier 0 (NARROW): 4-6 keywords that pin the unique event — main people + the specific incident "
            "or location/time anchor (e.g. for 'Melania Trump nie wytrzymała przy królu Karolu' — "
            "[\"Melania Trump\", \"król Karol\", \"Biały Dom\", \"upomniała\", \"Trump\"]).\n"
            "Tier 1 (MID): 2-3 keywords focused on main entity + topic category, dropping specific incident "
            "details (e.g. [\"Melania Trump\", \"król Karol\", \"wizyta\"]).\n"
            "Tier 2 (BROAD, optional): 1-2 keywords — just the primary subject (e.g. [\"Melania Trump\"]). "
            "Include this tier only when the narrow tiers might genuinely miss content; skip it for niche topics.\n\n"
            f"Languages: [{lang_list}]. Use BCP-47 language codes (en, pl, …). For non-English languages, "
            "render keywords in their native language. Return proper nouns and key concepts only — no filler words "
            "and no trailing punctuation."
        ),
    )
    _t0 = time.perf_counter()
    result = await agent.run(f"Topic: {topic}\nLanguages: {lang_list}")
    _u = result.usage()
    record_agent_call(
        "media_search_formulate",
        model,
        _u.input_tokens or 0,
        _u.output_tokens or 0,
        (time.perf_counter() - _t0) * 1000,
    )
    out: list[tuple[str, list[str]]] = []
    for lq in result.output.queries:
        tier_strings = [
            " ".join(f'"{kw}"' for kw in tier[:6]) for tier in lq.tiers if tier
        ]
        if tier_strings:
            out.append((lq.lang, tier_strings))
    if not out:
        # Defensive fallback: if the LLM returned nothing usable, use the raw topic for each language.
        out = [(lang, [topic]) for lang in languages]
    return out


async def _try_with_tier_fallback(
    search_fn,  # async callable taking one str query, returning list of results
    queries: list[str],
) -> list:
    """Try each query in order; return the first non-empty result list, else []."""
    for q in queries:
        results = await search_fn(q)
        if results:
            return results
    return []


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
    max_tiers = domain.media_search_max_query_tiers
    queries_per_lang = await _formulate_queries(topic, query_model, domain.media_search_languages)
    # queries_per_lang: list[(lang, [tier0_q, tier1_q, ...])]

    # Flat list (lang_idx, tier-string) for the legacy logger contract — uses tier 0 only.
    media_queries_flat = [tiers[0] for _, tiers in queries_per_lang]

    if log:
        active = (
            [f for f in ("youtube", "twitter", "facebook") if getattr(domain, f"{f}_search", False)]
            + [f for f in ("instagram", "tiktok") if getattr(domain, f"{f}_search", False)]
            + (["reddit"] if domain.reddit_search else [])
        )
        log.media_search_start(domain.media_search_languages, active, media_queries_flat)

    coros: list = []
    labels: list[str] = []

    if domain.youtube_search:
        coros.append(
            search_videos(
                topic, num=num, sort_by_date=domain.youtube_sort_by_date, api_key=serper_api_key
            )
        )
        labels.append("youtube")

    for flag, (site, source) in _SITE_MAP.items():
        if getattr(domain, flag, False):
            for i, (_lang, tiers) in enumerate(queries_per_lang):
                tier_queries = tiers[:max_tiers]
                coros.append(
                    _try_with_tier_fallback(
                        lambda q, _site=site, _source=source: search_site(
                            q,
                            site=_site,
                            source=_source,
                            num=num,
                            freshness=freshness,
                            api_key=serper_api_key,
                        ),
                        tier_queries,
                    )
                )
                labels.append(f"{source}@{i}")

    for flag, site_prefix in _IMAGE_SITE_MAP.items():
        if getattr(domain, flag, False):
            for i, (_lang, tiers) in enumerate(queries_per_lang):
                tier_queries = [f"{site_prefix} {t}" for t in tiers[:max_tiers]]
                coros.append(
                    _try_with_tier_fallback(
                        lambda q: search_images(
                            q, num=num, freshness=freshness, api_key=serper_api_key
                        ),
                        tier_queries,
                    )
                )
                labels.append(f"{flag.replace('_search', '')}@{i}")

    if domain.reddit_search:
        # Reddit is English-dominant — use the English-language tier set if present, else the first.
        en_tiers = next(
            (tiers for lang, tiers in queries_per_lang if lang == "en"), None
        ) or (queries_per_lang[0][1] if queries_per_lang else [topic])
        reddit_tier_queries = [
            " ".join(kw.strip('"') for kw in q.split()) for q in en_tiers[:max_tiers]
        ]
        coros.append(
            _try_with_tier_fallback(
                lambda q: search_reddit(q, num=num, freshness=freshness),
                reddit_tier_queries,
            )
        )
        labels.append("reddit")

    batches = await asyncio.gather(*coros, return_exceptions=True)

    candidates: list[EmbedCandidate] = []
    errors: dict[str, str] = {}
    seen_urls: set[str] = set()
    for label, batch in zip(labels, batches, strict=True):
        source_name = label.split("@")[0]
        if isinstance(batch, BaseException):
            errors[source_name] = str(batch)
            continue
        for c in batch:
            if c.url not in seen_urls:
                seen_urls.add(c.url)
                candidates.append(c)

    return candidates, errors
