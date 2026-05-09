# agents/media_extraction/agent.py
from __future__ import annotations

import pathlib
import time
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent, BinaryContent

from agents._base.config import ExtractionAgentConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents._base.resilient import run_with_fallback
from agents._base.run_context import record_agent_call
from agents.extraction.agent import ExtractionResult, Fact

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class _MediaFactData(BaseModel):
    text: str
    context: str


class _MediaExtractionOutput(BaseModel):
    facts: list[_MediaFactData]
    keywords: list[str]


async def run_media_extraction_agent(
    media_bytes: bytes,
    media_type: str,
    *,
    topic: str,
    language: str,
    config: ExtractionAgentConfig,
    source_marker: str = "editor-provided-photo",
    image_instructions: str | None = None,
) -> ExtractionResult:
    """Extract facts from an image or video using a single vision LLM call.

    No quotes — media files have no quotable text. All returned facts carry
    source_urls=[source_marker] so downstream agents and the modal step-2 UI
    can distinguish media-derived facts from text-derived ones.
    Soft-fails to an empty result on LLM error.
    """
    user_prompt_parts: list[Any] = [
        f"Osoba/temat materiału: {topic}.",
        BinaryContent(data=media_bytes, media_type=media_type),
    ]

    def _factory(m: str) -> tuple[Agent[Any, Any], str]:
        sys_prompt = render_prompt(
            _PROMPTS_DIR / "media_extraction.j2",
            topic=topic,
            language=language,
            format_style=model_format_style(m),
            image_instructions=image_instructions or "",
        )
        return Agent(m, output_type=_MediaExtractionOutput), sys_prompt

    t0 = time.perf_counter()
    result, model_used = await run_with_fallback(
        (config.model, *config.fallback_models),
        agent_factory=_factory,
        user_prompt=user_prompt_parts,
        agent_name="media_extraction",
    )
    u = result.usage()
    record_agent_call(
        "media_extraction",
        model_used,
        u.input_tokens or 0,
        u.output_tokens or 0,
        (time.perf_counter() - t0) * 1000,
    )
    output = result.output
    return ExtractionResult(
        facts=[
            Fact(text=f.text, context=f.context, source_urls=[source_marker])
            for f in output.facts
        ],
        quotes=[],
        keywords=output.keywords,
    )
