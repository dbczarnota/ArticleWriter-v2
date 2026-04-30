from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from agents._base.config import (
    SearchAgentConfig,
    ScrapingConfig,
    ParsingAgentConfig,
    ExtractionAgentConfig,
    AdaptiveSearchAgentConfig,
    InstructionsAgentConfig,
    WriterAgentConfig,
    ReflectionAgentConfig,
    FollowUpAgentConfig,
    UsageTrackingAgentConfig,
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


@dataclass(frozen=True)
class AppSettings:
    domain: str = "styl_fm"
    search: SearchAgentConfig = field(default_factory=SearchAgentConfig)
    scraping: ScrapingConfig = field(default_factory=ScrapingConfig)
    parsing: ParsingAgentConfig = field(default_factory=ParsingAgentConfig)
    extraction: ExtractionAgentConfig = field(default_factory=ExtractionAgentConfig)
    adaptive_search_agent: AdaptiveSearchAgentConfig = field(default_factory=AdaptiveSearchAgentConfig)
    instructions: InstructionsAgentConfig = field(default_factory=InstructionsAgentConfig)
    writer: WriterAgentConfig = field(default_factory=WriterAgentConfig)
    reflection: ReflectionAgentConfig = field(default_factory=ReflectionAgentConfig)
    followup: FollowUpAgentConfig = field(default_factory=FollowUpAgentConfig)
    usage_tracking: UsageTrackingAgentConfig = field(default_factory=UsageTrackingAgentConfig)
    pipeline: PipelineFlags = field(default_factory=PipelineFlags)

    @classmethod
    def from_request(cls, req: ArticleRequest) -> AppSettings:
        from dataclasses import fields, replace as dc_replace

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
