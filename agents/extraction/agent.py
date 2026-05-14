# agents/extraction/agent.py
from __future__ import annotations

import pathlib
import time
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent

from agents._base.config import ExtractionAgentConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents._base.resilient import run_with_fallback
from agents._base.run_context import record_agent_call
from agents._base.types import Fact, ParsedArticle, Quote

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class _FactData(BaseModel):
    text: str
    context: str
    source_urls: list[str]
    """Every article URL where this exact fact appears. Multi-source facts
    are stronger evidence — downstream agents prioritize them."""


class _QuoteData(BaseModel):
    text: str
    speaker: str
    context: str
    source_urls: list[str]
    """Every article URL where this exact quote appears."""


class ExtractionOutput(BaseModel):
    facts: list[_FactData]
    quotes: list[_QuoteData]
    keywords: list[str]


@dataclass
class ExtractionResult:
    facts: list[Fact]
    quotes: list[Quote]
    keywords: list[str]


async def run_extraction_agent(
    articles: list[ParsedArticle],
    *,
    topic: str,
    language: str,
    config: ExtractionAgentConfig,
    _agent: Agent[Any, Any] | None = None,
) -> ExtractionResult:
    """Extract facts, quotes, and keywords from all parsed articles in one LLM call."""
    if not articles:
        return ExtractionResult(facts=[], quotes=[], keywords=[])

    articles_text = "\n\n---\n\n".join(
        f"Source: {a.url}\nTitle: {a.title}\n\n{a.content}" for a in articles
    )

    if _agent is not None:
        _t0 = time.perf_counter()
        result = await _agent.run(articles_text)
        _model_used = config.model
    else:

        def _factory(m: str) -> tuple[Agent[Any, Any], str]:
            sys_prompt = render_prompt(
                _PROMPTS_DIR / "extract.j2",
                topic=topic,
                language=language,
                format_style=model_format_style(m),
            )
            return Agent(m, output_type=ExtractionOutput), sys_prompt

        _t0 = time.perf_counter()
        result, _model_used = await run_with_fallback(
            (config.model, *config.fallback_models),
            agent_factory=_factory,
            user_prompt=articles_text,
            agent_name="extraction",
        )
    _u = result.usage
    record_agent_call(
        "extraction",
        _model_used,
        _u.input_tokens or 0,
        _u.output_tokens or 0,
        (time.perf_counter() - _t0) * 1000,
    )

    return ExtractionResult(
        facts=[
            Fact(
                text=f.text,
                context=f.context,
                source_urls=list(f.source_urls or []),
            )
            for f in result.output.facts
        ],
        quotes=[
            Quote(
                text=q.text,
                speaker=q.speaker,
                context=q.context,
                source_urls=list(q.source_urls or []),
            )
            for q in result.output.quotes
        ],
        keywords=result.output.keywords,
    )
