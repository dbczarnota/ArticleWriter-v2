from __future__ import annotations

from dataclasses import dataclass

from agents._base.config import AgentConfig


@dataclass(frozen=True)
class StreamAnalysisAgentConfig(AgentConfig):
    model: str = "google-gla:gemini-flash-latest"
    fallback_models: tuple[str, ...] = ("google-gla:gemini-2.0-flash",)
    chunk_duration_seconds: int = 30
