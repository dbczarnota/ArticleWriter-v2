from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.db.models import OrgConfig
    from backend.repositories.protocols import OrgConfigRepository


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
    default_reflection_context_articles: int = 2
    default_min_source_signals: int = 1
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
    media_search_max_query_tiers: int = 2
    guidelines: str = ""
    html_format: str = ""
    reflection_stance: str = ""
    reflection_rounds: int = 1
    example_articles: tuple[str, ...] = ()
    example_titles: tuple[str, ...] = ()
    agent_models: dict[str, str] = field(default_factory=dict)
    """Org-level primary model per agent: {agent_key: model_id}."""
    agent_fallback_models: dict[str, list[str]] = field(default_factory=dict)
    """Org-level fallback models per agent: {agent_key: [fallback1, ...]}."""


def to_domain_config(config: OrgConfig, domain_name: str) -> DomainConfig:
    return DomainConfig(
        name=domain_name,
        description=config.description,
        language=config.language,
        target_word_count=config.target_word_count,
        max_facts_in_article=config.max_facts,
        max_quotes_in_article=config.max_quotes,
        default_search_freshness=config.search_freshness,
        default_num_queries=config.num_queries,
        default_max_results=config.max_results,
        default_min_source_signals=config.min_source_signals,
        max_pages_to_scrape=config.max_pages_to_scrape,
        youtube_search=config.youtube_search,
        youtube_sort_by_date=config.youtube_sort_by_date,
        twitter_search=config.twitter_search,
        facebook_search=config.facebook_search,
        news_search=config.news_search,
        tiktok_search=config.tiktok_search,
        instagram_search=config.instagram_search,
        reddit_search=config.reddit_search,
        media_search_languages=tuple(config.media_search_languages),
        media_search_num=config.media_search_num,
        media_search_max_query_tiers=config.media_search_max_query_tiers,
        default_reflection_context_articles=config.reflection_context_articles,
        guidelines=config.guidelines,
        html_format=config.html_format,
        reflection_stance=config.reflection_stance,
        reflection_rounds=config.reflection_rounds,
        example_articles=tuple(config.example_articles),
        example_titles=tuple(config.example_titles),
        agent_models=dict(config.agent_models) if config.agent_models else {},
        agent_fallback_models={k: list(v) for k, v in config.agent_fallback_models.items()}
        if config.agent_fallback_models
        else {},
    )


async def get_domain_config(
    org_code: str,
    domain_name: str,
    repo: OrgConfigRepository,
) -> DomainConfig | None:
    """Load domain config from repo and convert. Returns None if no row exists."""
    config = await repo.get(org_code)
    if config is None:
        return None
    return to_domain_config(config, domain_name)
