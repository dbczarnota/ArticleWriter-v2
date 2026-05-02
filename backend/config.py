from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from agents._base.config import (
    AdaptiveSearchAgentConfig,
    ExtractionAgentConfig,
    FollowUpAgentConfig,
    InstructionsAgentConfig,
    ParsingAgentConfig,
    ReflectionAgentConfig,
    ScrapingConfig,
    SearchAgentConfig,
    UsageTrackingAgentConfig,
    WriterAgentConfig,
)

if TYPE_CHECKING:
    from backend.api.schemas import ArticleRequest


AVAILABLE_MODELS: list[dict[str, str]] = [
    {"id": "google-gla:gemini-2.5-pro", "label": "Gemini 2.5 Pro"},
    {"id": "google-gla:gemini-2.5-flash", "label": "Gemini 2.5 Flash"},
    {"id": "anthropic:claude-sonnet-4-6", "label": "Claude Sonnet 4.6"},
    {"id": "anthropic:claude-haiku-4-5", "label": "Claude Haiku 4.5"},
    {"id": "openai:gpt-4o", "label": "GPT-4o"},
    {"id": "openai:gpt-4o-mini", "label": "GPT-4o Mini"},
]


# Mapowanie nazw kluczy z ArticleRequest.agents na pola AppSettings
_AGENT_FIELD_MAP: dict[str, str] = {
    "search": "search",
    "scraping": "scraping",
    "parsing": "parsing",
    "extraction": "extraction",
    "adaptive_search": "adaptive_search_agent",
    "instructions": "instructions",
    "writer": "writer",
    "reflection": "reflection",
    "followup": "followup",
    "usage_tracking": "usage_tracking",
}


@dataclass(frozen=True)
class PipelineFlags:
    llm_knowledge: bool = False
    adaptive_search: bool = True
    reflection: bool = True
    followup: bool = True
    cutoff_days: int = 30
    min_source_signals: int = 1  # raise InsufficientSourcesError if facts+quotes below this


_FALLBACK: tuple[str, ...] = ("groq:openai/gpt-oss-120b",)


@dataclass(frozen=True)
class AppSettings:
    domain: str = "styl_fm"
    search: SearchAgentConfig = field(
        default_factory=lambda: SearchAgentConfig(fallback_models=_FALLBACK)
    )
    scraping: ScrapingConfig = field(
        default_factory=lambda: ScrapingConfig(filter_fallback_models=_FALLBACK)
    )
    parsing: ParsingAgentConfig = field(
        default_factory=lambda: ParsingAgentConfig(fallback_models=_FALLBACK)
    )
    extraction: ExtractionAgentConfig = field(
        default_factory=lambda: ExtractionAgentConfig(fallback_models=_FALLBACK)
    )
    adaptive_search_agent: AdaptiveSearchAgentConfig = field(
        default_factory=lambda: AdaptiveSearchAgentConfig(fallback_models=_FALLBACK)
    )
    instructions: InstructionsAgentConfig = field(
        default_factory=lambda: InstructionsAgentConfig(fallback_models=_FALLBACK)
    )
    writer: WriterAgentConfig = field(
        default_factory=lambda: WriterAgentConfig(fallback_models=_FALLBACK)
    )
    reflection: ReflectionAgentConfig = field(
        default_factory=lambda: ReflectionAgentConfig(fallback_models=_FALLBACK)
    )
    followup: FollowUpAgentConfig = field(
        default_factory=lambda: FollowUpAgentConfig(fallback_models=_FALLBACK)
    )
    usage_tracking: UsageTrackingAgentConfig = field(
        default_factory=lambda: UsageTrackingAgentConfig(fallback_models=_FALLBACK)
    )
    pipeline: PipelineFlags = field(default_factory=PipelineFlags)

    @classmethod
    def from_request(cls, req: ArticleRequest) -> AppSettings:
        from dataclasses import fields
        from dataclasses import replace as dc_replace

        defaults = cls(domain=req.domain)

        patches: dict = {}

        for req_key, settings_key in _AGENT_FIELD_MAP.items():
            payload = (req.agents or {}).get(req_key)
            if not payload:
                continue
            base = getattr(defaults, settings_key)
            valid_fields = {f.name for f in fields(type(base))}
            merged = {k: v for k, v in payload.items() if k in valid_fields and v is not None}
            if merged:
                patches[settings_key] = dc_replace(base, **merged)

        if req.pipeline:
            base_flags = defaults.pipeline
            valid_fields = {f.name for f in fields(PipelineFlags)}
            merged = {k: v for k, v in req.pipeline.items() if k in valid_fields and v is not None}
            if merged:
                patches["pipeline"] = dc_replace(base_flags, **merged)

        return dc_replace(defaults, **patches) if patches else defaults
