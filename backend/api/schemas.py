from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, EmailStr, field_validator
from pydantic import Field as PydanticField

_DOMAIN_RE = re.compile(r"^[a-z0-9.-]+\.[a-z]{2,}$")
SOURCE_WHITELIST_MAX = 40
SOURCE_BLACKLIST_MAX = 20


class ArticleTemplateItem(BaseModel):
    id: str
    name: str
    body: str
    image_instructions: str = ""


class ImageTemplateItem(BaseModel):
    id: str
    name: str
    html: str


class EditorFactItem(BaseModel):
    text: str
    context: str = ""
    source: str = "editor-provided"
    """Origin marker used by the writer. Known values: "editor-provided"
    (raw text) or "editor-provided-photo" (extracted from an uploaded image)."""


class EditorQuoteItem(BaseModel):
    text: str
    speaker: str = ""
    context: str = ""
    source: str = "editor-provided"


class EditorExtractionPayload(BaseModel):
    """Pre-extracted editor facts/quotes/keywords sent from the modal step 2.
    When present, run_pipeline uses this directly and skips the in-pipeline
    text_extraction stage."""

    facts: list[EditorFactItem] = []
    quotes: list[EditorQuoteItem] = []
    keywords: list[str] = []


class ExtractEditorFactsRequest(BaseModel):
    """POST /v2/extract_editor_facts body — used by the modal's step 2 to
    preview what the LLM extracted from the editor's raw text."""

    topic: str
    raw_facts_text: str
    language: str | None = None

    @field_validator("topic", mode="before")
    @classmethod
    def _validate_topic(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("topic must not be empty")
        if len(v) > 300:
            raise ValueError("topic must be at most 300 characters")
        return v

    @field_validator("raw_facts_text", mode="before")
    @classmethod
    def _validate_raw_facts(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("raw_facts_text must not be empty")
        if len(v) > 10_000:
            raise ValueError("raw_facts_text must be at most 10 000 characters")
        return v


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
    raw_facts_text: str | None = None
    """Raw editor-provided text to be parsed for facts and quotes (legacy path).
    Used when editor_extraction is None — pipeline runs the text_extraction stage."""
    editor_extraction: EditorExtractionPayload | None = None
    """Pre-extracted (and optionally edited) editor facts/quotes from modal step 2.
    When present, pipeline skips the text_extraction stage and merges these directly."""
    article_template: str | None = None
    """Resolved template body (not ID). Frontend sends the body directly."""
    skip_web_research: bool = False
    """When true, pipeline skips search/scraping/parsing/extraction stages — article
    is written ONLY from editor-provided facts. Set from the modal step 2 checkbox."""
    social_media_attachments: list[dict] = []
    """Social media posts fetched by the editor before writing. Each entry:
    {"platform": "instagram"|"x", "post_url": str, "media_url": str, "media_type": str}
    Stored verbatim so ArticleView can show the temporary CDN download link."""

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

    @field_validator("raw_facts_text", mode="before")
    @classmethod
    def _validate_raw_facts(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if len(v) > 10_000:
            raise ValueError("raw_facts_text must be at most 10 000 characters")
        return v or None

    @field_validator("article_template", mode="before")
    @classmethod
    def _validate_article_template(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if len(v) > 5_000:
            raise ValueError("article_template must be at most 5 000 characters")
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
    discovery_retention_days: int = PydanticField(ge=1, le=365, default=14)
    stream_retention_days: int = PydanticField(ge=1, le=365, default=7)
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
    article_templates: list[ArticleTemplateItem] = PydanticField(default_factory=list)
    image_templates: list[ImageTemplateItem] = PydanticField(default_factory=list)
    image_creator_enabled: bool = False
    webhook_url: str | None = None
    webhook_secret: str | None = None
    source_whitelist: list[str] = PydanticField(default_factory=list)
    source_blacklist: list[str] = PydanticField(default_factory=list)

    @field_validator("source_whitelist", "source_blacklist", mode="before")
    @classmethod
    def _validate_source_list(cls, v: Any, info: Any) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError(f"{info.field_name} must be a list of domains")
        seen: set[str] = set()
        result: list[str] = []
        for raw in v:
            if not isinstance(raw, str):
                raise ValueError(f"{info.field_name}: each entry must be a string")
            d = raw.strip().lower()
            if not d:
                continue
            if d.startswith(("http://", "https://")):
                raise ValueError(f"invalid domain: {raw!r} — drop protocol prefix")
            if "/" in d or ":" in d:
                raise ValueError(f"invalid domain: {raw!r} — no paths or ports")
            if not _DOMAIN_RE.match(d):
                raise ValueError(f"invalid domain: {raw!r}")
            if d in seen:
                continue
            seen.add(d)
            result.append(d)
        max_n = (
            SOURCE_WHITELIST_MAX if info.field_name == "source_whitelist" else SOURCE_BLACKLIST_MAX
        )
        if len(result) > max_n:
            raise ValueError(f"max {max_n} domains (Serper query length limit)")
        return result


class ContactRequest(BaseModel):
    name: str = PydanticField(min_length=1, max_length=200)
    email: EmailStr
    company: str | None = PydanticField(default=None, max_length=200)
    message: str = PydanticField(min_length=1, max_length=4000)


class GeneratedImagePayload(BaseModel):
    label: str = ""
    url: str
    template_id: str | None = None
    created_at: str | None = None


class RelatedTopicPayload(BaseModel):
    title: str
    reason: str = ""


class WebhookPayloadMetadata(BaseModel):
    created_at: str | None = None
    domain: str = ""


class WebhookPayload(BaseModel):
    """Stable contract sent to OrgConfig.webhook_url. Fields with no data
    are sent as empty lists / null — never omitted."""

    article_id: str
    org_code: str
    sent_at: str
    topic: str
    title: str = ""
    alternative_titles: list[str] = PydanticField(default_factory=list)
    html: str = ""
    raw_facts: str = ""
    related_topics: list[RelatedTopicPayload] = PydanticField(default_factory=list)
    generated_images: list[GeneratedImagePayload] = PydanticField(default_factory=list)
    metadata: WebhookPayloadMetadata = PydanticField(default_factory=WebhookPayloadMetadata)


class WebhookDeliveryRecord(BaseModel):
    """One entry in Article.webhook_deliveries — also the response shape
    of POST /v2/articles/{id}/send-webhook."""

    sent_at: str
    status: str  # "success" | "error"
    http_status: int | None = None
    error: str | None = None
