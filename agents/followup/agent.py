# agents/followup/agent.py
from __future__ import annotations

import pathlib
import time
from typing import Any

from pydantic import BaseModel, field_validator
from pydantic_ai import Agent

from agents._base.config import FollowUpAgentConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents._base.resilient import run_with_fallback
from agents._base.run_context import record_agent_call
from agents._base.types import ArticleOutput
from agents.extraction.agent import ExtractionResult
from agents.writer.agent import ArticleHtml

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class FollowUpOutput(BaseModel):
    alternative_titles: list[str]
    followup_topics: list[str]

    @field_validator("alternative_titles", "followup_topics", mode="before")
    @classmethod
    def _clean(cls, v: list) -> list:
        return [" ".join(s.split()) for item in v if isinstance(item, str) and (s := item.strip())]


async def run_followup_agent(
    article: ArticleHtml,
    *,
    topic: str,
    extraction_result: ExtractionResult,
    config: FollowUpAgentConfig,
    _agent: Agent[Any, Any] | None = None,
) -> ArticleOutput:
    """Generate alternative titles, follow-up topics, and track used facts/quotes."""
    facts_text = "\n".join(f"- {f.text} [{f.context}]" for f in extraction_result.facts)
    quotes_text = "\n".join(f'- "{q.text}" — {q.speaker}' for q in extraction_result.quotes)

    user_prompt = (
        f"TOPIC: {topic}\n\n"
        f"PUBLISHED ARTICLE:\n{article.html}\n\n"
        f"SOURCE FACTS:\n{facts_text or '(none)'}\n\n"
        f"SOURCE QUOTES:\n{quotes_text or '(none)'}"
    )

    if _agent is not None:
        _t0 = time.perf_counter()
        result = await _agent.run(user_prompt)
        _model_used = config.model
    else:

        def _factory(m: str):
            return Agent(
                m,
                output_type=FollowUpOutput,
                system_prompt=render_prompt(
                    _PROMPTS_DIR / "followup.j2",
                    num_titles=config.num_titles,
                    num_topics=config.num_topics,
                    format_style=model_format_style(m),
                ),
            )

        _t0 = time.perf_counter()
        result, _model_used = await run_with_fallback(
            (config.model, *config.fallback_models),
            agent_factory=_factory,
            user_prompt=user_prompt,
            agent_name="followup",
        )
    _u = result.usage()
    record_agent_call(
        "followup",
        _model_used,
        _u.input_tokens or 0,
        _u.output_tokens or 0,
        (time.perf_counter() - _t0) * 1000,
    )
    output = result.output

    sources = list(
        {f.source_url for f in extraction_result.facts if f.source_url}
        | {q.source_url for q in extraction_result.quotes if q.source_url}
    )

    return ArticleOutput(
        html=article.html,
        alternative_titles=output.alternative_titles,
        followup_topics=output.followup_topics,
        used_facts=[],
        used_quotes=[],
        sources=sources,
    )
