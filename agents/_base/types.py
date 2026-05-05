from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Fact:
    text: str
    context: str  # kto/co/kiedy — żeby agent pisząc artykuł wiedział czego używa
    source_urls: list[str] = field(default_factory=list)
    """Every article URL that asserted this fact. Multi-source = stronger
    evidence — downstream agents (instructions/writer/reflection) prioritize
    facts with more source_urls."""


@dataclass
class Quote:
    text: str
    speaker: str
    context: str  # przy jakiej okazji, w jakim wywiadzie
    source_urls: list[str] = field(default_factory=list)
    """Every article URL that contained this exact quote."""


@dataclass
class ScrapedPage:
    url: str
    title: str
    content: str  # Markdown
    scrape_tier: Literal["httpx", "jina", "firecrawl"]


@dataclass
class ParsedArticle:
    url: str
    title: str
    content: str  # wyczyszczony Markdown (bez RODO, reklam, nawigacji)
    publication_date: str | None = None  # ISO date string lub None


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    source: Literal["web", "twitter", "facebook", "youtube"]


@dataclass
class EmbedCandidate:
    url: str
    title: str
    source: Literal["youtube", "twitter", "tiktok", "instagram", "facebook", "reddit"]
    thumbnail_url: str | None = None
    description: str | None = None
    channel: str | None = None
    competitor_source_url: str | None = None
    """URL of the competitor article this embed was found in, if any."""


@dataclass
class ArticleOutput:
    html: str
    alternative_titles: list[str] = field(default_factory=list)
    followup_topics: list[str] = field(default_factory=list)
    used_facts: list[str] = field(default_factory=list)
    used_quotes: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    scraped_urls: list[str] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    filter_reasons: dict[str, str] = field(default_factory=dict)
    embed_candidates: list[EmbedCandidate] = field(default_factory=list)
    timing: dict[str, float] = field(default_factory=dict)
    token_usage: list[dict] = field(default_factory=list)
    fallback_events: list[dict] = field(default_factory=list)
    article_id: str = field(default="")
