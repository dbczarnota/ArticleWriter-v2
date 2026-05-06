from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator
from pydantic import Field as PydanticField


class ArticleRequest(BaseModel):
    topic: str
    domain: str = "styl_fm"
    urls: list[str] = []
    domains_filter: list[str] = []
    agents: dict[str, dict] = {}
    pipeline: dict[str, bool] = {}
    additional_instructions: str | None = None
    author_name: str | None = None
    """Display name for the author (given + family from Kinde, or email fallback).
    Frontend computes and sends it; backend stores verbatim. Mirrors how
    marked_done_by_name is plumbed."""
    domain_overrides: dict[str, Any] = {}
    """Per-article domain config overrides. Keys match DomainConfigUpdate field names.
    Non-empty values replace the org's saved config for this article run only."""

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


class ArticleUpdate(BaseModel):
    marked_done: bool
    marked_done_by_name: str | None = None


class FeedConfigPayload(BaseModel):
    url: str
    name: str = ""
    poll_interval_min: int = PydanticField(ge=1, le=1440, default=15)

    @field_validator("url", mode="before")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        p = urlparse(v)
        if not (p.scheme in ("http", "https") and p.netloc):
            raise ValueError(f"Invalid feed URL: {v}")
        return v


class CategoryConfigPayload(BaseModel):
    name: str
    description: str


class DomainConfigUpdate(BaseModel):
    domain_name: str | None = None
    """Org's editorial-domain identifier. None means 'leave it as-is'.
    Stored in the orgs table, not org_configs — endpoint dispatches the
    update to OrgRepository when present."""
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
    reflection_rounds: int = PydanticField(ge=1, le=5, default=1)
    example_articles: list[str] = PydanticField(default_factory=list)
    example_titles: list[str] = PydanticField(default_factory=list)
    agent_models: dict[str, str] = PydanticField(default_factory=dict)
    agent_fallback_models: dict[str, list[str]] = PydanticField(default_factory=dict)
    discovery_enabled: bool = False
    discovery_feeds: list[FeedConfigPayload] = PydanticField(default_factory=list)
    discovery_categories: list[CategoryConfigPayload] = PydanticField(default_factory=list)
    discovery_topic_matching_window_days: int = PydanticField(ge=1, le=90, default=3)
    discovery_followup_threshold: int = PydanticField(ge=1, le=100, default=5)
    discovery_classifier_model: str = "google-gla:gemini-flash-lite-latest"
    discovery_matcher_model: str = "google-gla:gemini-flash-lite-latest"
    discovery_topic_writer_model: str = "google-gla:gemini-flash-lite-latest"
    discovery_classifier_fallback_models: list[str] = PydanticField(
        default_factory=lambda: ["groq:openai/gpt-oss-120b"]
    )
    discovery_matcher_fallback_models: list[str] = PydanticField(
        default_factory=lambda: ["groq:openai/gpt-oss-120b"]
    )
    discovery_topic_writer_fallback_models: list[str] = PydanticField(
        default_factory=lambda: ["groq:openai/gpt-oss-120b"]
    )
