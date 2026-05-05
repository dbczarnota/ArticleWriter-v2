# agents/pipeline/_helpers.py
"""Stage-agnostic helpers used across the pipeline orchestration.

Date filtering, social-media URL extraction (from search results AND from
scraped content), article ranking by extraction contribution, and extraction
merging. All pure / stateless — no IO, no LLM calls. Pulled out of runner.py
to keep the orchestration entry point focused on flow control.
"""

from __future__ import annotations

import re
from typing import Literal

from agents._base.types import EmbedCandidate, ParsedArticle
from agents.extraction.agent import ExtractionResult


def filter_by_date(
    articles: list[ParsedArticle],
    cutoff_days: int,
    manual_urls: set[str],
) -> tuple[list[ParsedArticle], dict[str, str]]:
    from datetime import UTC, datetime, timedelta

    cutoff = datetime.now(UTC).date() - timedelta(days=cutoff_days)
    kept: list[ParsedArticle] = []
    reasons: dict[str, str] = {}
    for article in articles:
        if article.url in manual_urls:
            kept.append(article)
            continue
        if article.publication_date is None:
            kept.append(article)
            continue
        try:
            pub = datetime.fromisoformat(article.publication_date).date()
        except ValueError:
            kept.append(article)
            continue
        if pub < cutoff:
            reasons[article.url] = f"Too old: {pub}"
        else:
            kept.append(article)
    return kept, reasons


_SocialSource = Literal["youtube", "twitter", "tiktok", "instagram", "facebook", "reddit"]

_SOCIAL_DOMAINS: dict[str, _SocialSource] = {
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "tiktok.com": "tiktok",
    "instagram.com": "instagram",
    "facebook.com": "facebook",
    "reddit.com": "reddit",
}


def extract_social_from_search(
    results: list,
) -> tuple[list, list[EmbedCandidate]]:
    """Split search results into (scrapable, social_embed_candidates).

    Social media URLs are useless to scrape but valuable as embeds.
    """
    from urllib.parse import urlparse

    scrapable: list = []
    embeds: list[EmbedCandidate] = []
    for r in results:
        host = urlparse(r.url).netloc.removeprefix("www.")
        source: _SocialSource | None = None
        for domain, src in _SOCIAL_DOMAINS.items():
            if host == domain or host.endswith("." + domain):
                source = src
                break
        if source:
            embeds.append(
                EmbedCandidate(
                    url=r.url,
                    title=r.title,
                    source=source,
                    description=r.snippet or None,
                )
            )
        else:
            scrapable.append(r)
    return scrapable, embeds


_SOCIAL_URL_RE = re.compile(
    r"https?://(?:www\.)?"
    r"(?:youtube\.com/(?:watch|shorts|embed)[^\s\)\]\"'<>]*"
    r"|youtu\.be/[^\s\)\]\"'<>]+"
    r"|twitter\.com/\w+/status/[^\s\)\]\"'<>]+"
    r"|x\.com/\w+/status/[^\s\)\]\"'<>]+"
    r"|tiktok\.com/@[^\s\)\]\"'<>/]+/video/[^\s\)\]\"'<>]+"
    r"|instagram\.com/(?:p|reel|tv)/[^\s\)\]\"'<>/]+"
    r"|facebook\.com/(?:[^/]+/(?:posts|videos|reels)/|watch/\?v=)[^\s\)\]\"'<>]+"
    r"|reddit\.com/r/[^\s\)\]\"'<>]+)",
    re.IGNORECASE,
)


def normalize_social_url(url: str) -> str:
    """Convert embed/shortlink forms to canonical watch URLs."""
    # youtube.com/embed/VIDEO_ID → youtube.com/watch?v=VIDEO_ID
    m = re.match(
        r"(https?://(?:www\.)?youtube\.com)/embed/([A-Za-z0-9_-]+)", url, re.IGNORECASE
    )
    if m:
        return f"{m.group(1)}/watch?v={m.group(2)}"
    return url


def extract_social_from_content(
    pages: list,
) -> list[EmbedCandidate]:
    """Extract social media URLs embedded in scraped competitor article content.

    Regex-only, zero LLM cost. Complements extract_social_from_search (which
    catches top-level social URLs) by surfacing embeds mentioned within articles.
    """
    from urllib.parse import urlparse

    seen: set[str] = set()
    candidates: list[EmbedCandidate] = []
    for page in pages:
        for match in _SOCIAL_URL_RE.finditer(page.content):
            url = normalize_social_url(match.group(0).rstrip(".,;)"))
            if url in seen:
                continue
            seen.add(url)
            host = urlparse(url).netloc.removeprefix("www.")
            source: _SocialSource | None = None
            for domain, src in _SOCIAL_DOMAINS.items():
                if host == domain or host.endswith("." + domain):
                    source = src
                    break
            if source:
                candidates.append(
                    EmbedCandidate(
                        url=url,
                        title=url,
                        source=source,
                        competitor_source_url=page.url,
                    )
                )
    return candidates


def rank_articles_by_extraction(
    articles: list[ParsedArticle], extraction: ExtractionResult
) -> list[ParsedArticle]:
    """Sort parsed articles by how much they contributed to the extraction.

    A fact counts twice as much as a quote (facts are more directly load-bearing for
    fact-checking; quotes are also ranked but less aggressively). Articles that didn't
    contribute anything fall to the end in their original order. Reviewer's competitor
    coverage is taken from the top of this list.
    """
    from collections import Counter

    score: Counter[str] = Counter()
    for f in extraction.facts:
        score[f.source_url] += 2
    for q in extraction.quotes:
        score[q.source_url] += 1
    return sorted(articles, key=lambda a: score[a.url], reverse=True)


def merge_extraction(base: ExtractionResult, extra: ExtractionResult) -> ExtractionResult:
    seen_facts = {f.text for f in base.facts}
    seen_quotes = {q.text for q in base.quotes}
    merged_facts = base.facts + [f for f in extra.facts if f.text not in seen_facts]
    merged_quotes = base.quotes + [q for q in extra.quotes if q.text not in seen_quotes]
    merged_keywords = list(dict.fromkeys(base.keywords + extra.keywords))
    return ExtractionResult(facts=merged_facts, quotes=merged_quotes, keywords=merged_keywords)
