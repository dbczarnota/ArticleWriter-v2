from __future__ import annotations

from dataclasses import dataclass

from agents._base.config import AgentConfig


@dataclass(frozen=True)
class StreamDigestAgentConfig(AgentConfig):
    model: str = "google-gla:gemini-flash-latest"
    fallback_models: tuple[str, ...] = ("google-gla:gemini-2.0-flash",)
    chunks_per_digest: int = 5
    previous_digests_count: int = 2
