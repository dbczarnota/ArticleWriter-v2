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
    WriterAgentConfig,
)

if TYPE_CHECKING:
    from backend.api.schemas import ArticleRequest
    from backend.domain import DomainConfig


AVAILABLE_MODELS: list[dict[str, str]] = [
    {"id": "google-gla:gemini-pro-latest", "label": "Gemini Pro Latest"},
    {"id": "google-gla:gemini-flash-latest", "label": "Gemini Flash Latest"},
    {"id": "google-gla:gemini-flash-lite-latest", "label": "Gemini Flash Lite Latest"},
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
}

# ScrapingConfig uses filter_model / filter_fallback_models instead of model / fallback_models
_MODEL_FIELD: dict[str, str] = {"scraping": "filter_model"}
_FALLBACK_FIELD: dict[str, str] = {"scraping": "filter_fallback_models"}


@dataclass(frozen=True)
class PipelineFlags:
    llm_knowledge: bool = False
    adaptive_search: bool = True
    reflection: bool = True
    followup: bool = True
    cutoff_days: int = 30
    min_source_signals: int = 1  # raise InsufficientSourcesError if facts+quotes below this


_FALLBACK: tuple[str, ...] = ("google-gla:gemini-flash-latest",)


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
    pipeline: PipelineFlags = field(default_factory=PipelineFlags)

    @classmethod
    def from_request(cls, req: ArticleRequest, *, base: AppSettings | None = None) -> AppSettings:
        from dataclasses import fields
        from dataclasses import replace as dc_replace

        defaults = base if base is not None else cls(domain=req.domain)

        patches: dict = {}

        for req_key, settings_key in _AGENT_FIELD_MAP.items():
            payload = (req.agents or {}).get(req_key)
            if not payload:
                continue
            cfg = getattr(defaults, settings_key)
            valid_fields = {f.name for f in fields(type(cfg))}
            merged = {k: v for k, v in payload.items() if k in valid_fields and v is not None}
            if merged:
                patches[settings_key] = dc_replace(cfg, **merged)

        if req.pipeline:
            base_flags = defaults.pipeline
            valid_fields = {f.name for f in fields(PipelineFlags)}
            merged = {k: v for k, v in req.pipeline.items() if k in valid_fields and v is not None}
            if merged:
                patches["pipeline"] = dc_replace(base_flags, **merged)

        return dc_replace(defaults, **patches) if patches else defaults


def apply_org_models(settings: AppSettings, domain: DomainConfig) -> AppSettings:
    """Overlay org-level agent model config from DomainConfig onto AppSettings.

    Called in write_article after from_request() so per-request agents overrides
    (applied inside from_request) take precedence over org defaults.
    """
    if not domain.agent_models and not domain.agent_fallback_models:
        return settings

    from dataclasses import fields as dc_fields
    from dataclasses import replace as dc_replace

    patches: dict = {}
    all_keys = set(domain.agent_models) | set(domain.agent_fallback_models)

    for req_key in all_keys:
        settings_key = _AGENT_FIELD_MAP.get(req_key)
        if not settings_key:
            continue
        base = getattr(settings, settings_key)
        valid_fields = {f.name for f in dc_fields(type(base))}

        model_field = _MODEL_FIELD.get(req_key, "model")
        fallback_field = _FALLBACK_FIELD.get(req_key, "fallback_models")

        merged: dict = {}
        model = domain.agent_models.get(req_key)
        fallbacks = domain.agent_fallback_models.get(req_key)

        if model and model_field in valid_fields:
            merged[model_field] = model
        if fallbacks is not None and fallback_field in valid_fields:
            merged[fallback_field] = tuple(fallbacks)

        if merged:
            patches[settings_key] = dc_replace(base, **merged)

    return dc_replace(settings, **patches) if patches else settings
