from __future__ import annotations

from pydantic import BaseModel, field_validator
from pydantic import Field as PydanticField


class ArticleRequest(BaseModel):
    id: str
    topic: str
    domain: str = "styl_fm"
    urls: list[str] = []
    domains_filter: list[str] = []
    agents: dict[str, dict] = {}
    pipeline: dict[str, bool] = {}
    additional_instructions: str | None = None

    @field_validator("topic", mode="before")
    @classmethod
    def _validate_topic(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("topic must not be empty")
        if len(v) > 300:
            raise ValueError("topic must be at most 300 characters")
        return v

    @field_validator("additional_instructions", mode="before")
    @classmethod
    def _validate_additional_instructions(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if len(v) > 2000:
            raise ValueError("additional_instructions must be at most 2000 characters")
        return v or None


class DomainConfigUpdate(BaseModel):
    description: str = ""
    language: str = "pl"
    target_word_count: int = PydanticField(ge=100, le=5000, default=600)
    max_facts: int = PydanticField(ge=1, le=50, default=8)
    max_quotes: int = PydanticField(ge=0, le=20, default=3)
    search_freshness: str = "qdr:w"
    num_queries: int = PydanticField(ge=1, le=10, default=3)
    max_results: int = PydanticField(ge=1, le=20, default=5)
    min_source_signals: int = PydanticField(ge=0, le=20, default=1)
    max_pages_to_scrape: int = PydanticField(ge=1, le=50, default=10)
    youtube_search: bool = False
    twitter_search: bool = False
    facebook_search: bool = False
    news_search: bool = False
    tiktok_search: bool = False
    instagram_search: bool = False
    reddit_search: bool = False
    media_search_languages: list[str] = PydanticField(default_factory=lambda: ["en"])
    media_search_num: int = PydanticField(ge=1, le=20, default=5)
    media_search_max_query_tiers: int = PydanticField(ge=1, le=5, default=2)
    youtube_sort_by_date: bool = True
    reflection_context_articles: int = PydanticField(ge=0, le=10, default=2)
    guidelines: str = ""
    html_format: str = ""
    reflection_stance: str = ""
    example_articles: list[str] = PydanticField(default_factory=list)
