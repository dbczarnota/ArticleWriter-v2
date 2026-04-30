from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DomainConfig:
    name: str
    description: str
    target_word_count: int = 600
    max_facts_in_article: int = 8
    max_quotes_in_article: int = 3
    default_search_freshness: str = "qdr:w"
    default_num_queries: int = 3
    default_max_results: int = 5
    youtube_search: bool = False
    twitter_search: bool = False
    facebook_search: bool = False
    guidelines: str = ""
    example_articles: list[str] = field(default_factory=list)
