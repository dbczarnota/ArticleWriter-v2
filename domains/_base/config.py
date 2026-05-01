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
    youtube_search: bool = False
    twitter_search: bool = False
    facebook_search: bool = False
    news_search: bool = False
    tiktok_search: bool = False
    instagram_search: bool = False
    reddit_search: bool = False
    media_search_languages: tuple[str, ...] = ("en",)
    media_search_num: int = 5
    guidelines: str = ""
    html_format: str = ""
    example_articles: tuple[str, ...] = ()
