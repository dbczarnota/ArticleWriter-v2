from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainConfig:
    name: str
    description: str
    language: str = "pl"
    target_word_count: int = 600
    max_facts_in_article: int = 8
    max_quotes_in_article: int = 3
    default_search_freshness: str = "qdr:w"
    default_num_queries: int = 3
    default_max_results: int = 5
    default_reflection_context_articles: int = 2  # parsed articles fed to reviewer as competitor context
    default_min_source_signals: int = 1  # facts+quotes floor (also drives adaptive_search target)
    max_pages_to_scrape: int = 10
    youtube_search: bool = False
    youtube_sort_by_date: bool = True
    twitter_search: bool = False
    facebook_search: bool = False
    news_search: bool = False
    tiktok_search: bool = False
    instagram_search: bool = False
    reddit_search: bool = False
    media_search_languages: tuple[str, ...] = ("en",)
    media_search_num: int = 5
    media_search_max_query_tiers: int = 2  # narrow→broad fallback budget per (source, lang)
    guidelines: str = ""
    html_format: str = ""
    reflection_stance: str = ""
    example_articles: tuple[str, ...] = ()
