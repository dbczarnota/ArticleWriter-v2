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
from agents._base.types import Fact, Quote
from agents.extraction.agent import ExtractionResult

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class _ImageFactData(BaseModel):
    text: str
    context: str


class _ImageExtractionOutput(BaseModel):
    facts: list[_ImageFactData]
    keywords: list[str]


class _VideoFactData(BaseModel):
    text: str
    context: str


class _VideoQuoteData(BaseModel):
    text: str
    speaker: str
    context: str


class _VideoExtractionOutput(BaseModel):
    facts: list[_VideoFactData]
    quotes: list[_VideoQuoteData]
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
    """Extract facts (and quotes for video) from an image or video.

    Selects image_extraction.j2 or video_extraction.j2 based on media_type.
    Video extraction additionally returns quotes (spoken words, sung lyrics).
    All items carry source_urls=[source_marker].
    Soft-fails to empty ExtractionResult on LLM error.
    """
    is_video = media_type.startswith("video/")
    template = "video_extraction.j2" if is_video else "image_extraction.j2"

    user_prompt_parts: list[Any] = [
        f"Osoba/temat materiału: {topic}.",
        BinaryContent(data=media_bytes, media_type=media_type),
    ]

    def _factory(m: str) -> tuple[Agent[Any, Any], str]:
        sys_prompt = render_prompt(
            _PROMPTS_DIR / template,
            topic=topic,
            language=language,
            format_style=model_format_style(m),
            image_instructions=image_instructions or "",
        )
        output_type = _VideoExtractionOutput if is_video else _ImageExtractionOutput
        return Agent(m, output_type=output_type), sys_prompt

    t0 = time.perf_counter()
    result, model_used = await run_with_fallback(
        (config.model, *config.fallback_models),
        agent_factory=_factory,
        user_prompt=user_prompt_parts,
        agent_name="media_extraction",
    )
    u = result.usage
    record_agent_call(
        "media_extraction",
        model_used,
        u.input_tokens or 0,
        u.output_tokens or 0,
        (time.perf_counter() - t0) * 1000,
    )
    output = result.output
    facts = [
        Fact(text=f.text, context=f.context, source_urls=[source_marker]) for f in output.facts
    ]
    quotes: list[Quote] = []
    if is_video and isinstance(output, _VideoExtractionOutput):
        quotes = [
            Quote(text=q.text, speaker=q.speaker, context=q.context, source_urls=[source_marker])
            for q in output.quotes
        ]
    return ExtractionResult(facts=facts, quotes=quotes, keywords=output.keywords)
