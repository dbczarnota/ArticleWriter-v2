from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class AgentConfig:
    model: str
    enabled: bool = True
    thinking: Literal["off", "minimal", "low", "medium", "high"] = "off"
    tool_call_budget: int = 3
    max_tokens: int | None = None
    fallback_models: tuple[str, ...] = ()


@dataclass(frozen=True)
class SearchAgentConfig(AgentConfig):
    model: str = "google-gla:gemini-2.5-flash"
    num_queries: int = 3
    max_results: int = 5
    search_freshness: str = "qdr:w"
    news_search: bool = False


@dataclass(frozen=True)
class ScrapingConfig:
    """Nie jest agentycznym węzłem LLM — konfiguracja toolsetu scrapingu."""

    max_concurrent_jina: int = 8
    httpx_timeout: float = 15.0
    jina_timeout: float = 30.0
    filter_model: str = "google-gla:gemini-2.5-flash"
    filter_fallback_models: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParsingAgentConfig(AgentConfig):
    model: str = "google-gla:gemini-2.5-flash"


@dataclass(frozen=True)
class ExtractionAgentConfig(AgentConfig):
    model: str = "google-gla:gemini-2.5-flash"


@dataclass(frozen=True)
class AdaptiveSearchAgentConfig(AgentConfig):
    model: str = "google-gla:gemini-2.5-flash"
    max_additional_rounds: int = 1


@dataclass(frozen=True)
class InstructionsAgentConfig(AgentConfig):
    model: str = "google-gla:gemini-2.5-pro"
    thinking: Literal["off", "minimal", "low", "medium", "high"] = "low"


@dataclass(frozen=True)
class WriterAgentConfig(AgentConfig):
    model: str = "google-gla:gemini-2.5-pro"
    thinking: Literal["off", "minimal", "low", "medium", "high"] = "medium"


@dataclass(frozen=True)
class ReflectionAgentConfig(AgentConfig):
    model: str = "google-gla:gemini-2.5-flash"
    max_rounds: int = 1
    context_articles_count: int = 2  # parsed articles passed to reviewer as competitor coverage


@dataclass(frozen=True)
class FollowUpAgentConfig(AgentConfig):
    model: str = "google-gla:gemini-2.5-flash"
    num_titles: int = 10
    num_topics: int = 5


@dataclass(frozen=True)
class UsageTrackingAgentConfig(AgentConfig):
    model: str = "google-gla:gemini-2.5-flash"
