# agents/extraction/agent.py
from __future__ import annotations
import pathlib
import time
from dataclasses import dataclass
from pydantic import BaseModel
from pydantic_ai import Agent
from agents._base.config import ExtractionAgentConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents._base.run_context import record_agent_call
from agents._base.types import Fact, ParsedArticle, Quote

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class _FactData(BaseModel):
    text: str
    context: str
    source_url: str
    source_title: str


class _QuoteData(BaseModel):
    text: str
    speaker: str
    context: str
    source_url: str


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
    _agent: Agent | None = None,
) -> ExtractionResult:
    """Extract facts, quotes, and keywords from all parsed articles in one LLM call."""
    if not articles:
        return ExtractionResult(facts=[], quotes=[], keywords=[])

    articles_text = "\n\n---\n\n".join(
        f"Source: {a.url}\nTitle: {a.title}\n\n{a.content}" for a in articles
    )

    agent = _agent or Agent(
        config.model,
        output_type=ExtractionOutput,
        system_prompt=render_prompt(
            _PROMPTS_DIR / "extract.j2",
            topic=topic,
            language=language,
            format_style=model_format_style(config.model),
        ),
    )

    _t0 = time.perf_counter()
    result = await agent.run(articles_text)
    _u = result.usage()
    record_agent_call("extraction", config.model, _u.input_tokens or 0, _u.output_tokens or 0,
                      (time.perf_counter() - _t0) * 1000)

    return ExtractionResult(
        facts=[
            Fact(
                text=f.text,
                context=f.context,
                source_url=f.source_url,
                source_title=f.source_title,
            )
            for f in result.output.facts
        ],
        quotes=[
            Quote(
                text=q.text,
                speaker=q.speaker,
                context=q.context,
                source_url=q.source_url,
            )
            for q in result.output.quotes
        ],
        keywords=result.output.keywords,
    )
