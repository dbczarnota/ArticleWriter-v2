# agents/followup/agent.py
from __future__ import annotations

import pathlib
import time
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, field_validator
from pydantic_ai import Agent

from agents._base.config import FollowUpAgentConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents._base.resilient import run_with_fallback
from agents._base.run_context import record_agent_call
from agents._base.types import ArticleOutput
from agents.extraction.agent import ExtractionResult
from agents.writer.agent import ArticleHtml

if TYPE_CHECKING:
    from backend.domain import DomainConfig

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class FollowUpOutput(BaseModel):
    alternative_titles: list[str]
    followup_topics: list[str]
    # ID-based usage tracking. The agent receives source facts/quotes as a
    # numbered list (1-indexed) and returns just the IDs of the entries it
    # detected in the published article. We map IDs back to the original
    # source strings on the Python side, eliminating any string-comparison
    # drift (LLM dropping a comma, prepending "- ", paraphrasing whitespace).
    used_fact_ids: list[int] = []
    used_quote_ids: list[int] = []

    @field_validator("alternative_titles", "followup_topics", mode="before")
    @classmethod
    def _clean(cls, v: list) -> list:
        return [" ".join(s.split()) for item in v if isinstance(item, str) and (s := item.strip())]

    @field_validator("used_fact_ids", "used_quote_ids", mode="before")
    @classmethod
    def _clean_int_list(cls, v: Any) -> list[int]:
        if not isinstance(v, list):
            return []
        out: list[int] = []
        for item in v:
            try:
                out.append(int(item))
            except (TypeError, ValueError):
                continue
        return out


async def run_followup_agent(
    article: ArticleHtml,
    *,
    topic: str,
    extraction_result: ExtractionResult,
    config: FollowUpAgentConfig,
    domain: DomainConfig,
    _agent: Agent[Any, Any] | None = None,
) -> ArticleOutput:
    """Generate alternative titles, follow-up topics, and track which facts/quotes were used."""
    facts = list(extraction_result.facts)
    quotes = list(extraction_result.quotes)
    facts_text = "\n".join(f"[{i}] {f.text}" for i, f in enumerate(facts, start=1)) or "(none)"
    quotes_text = (
        "\n".join(f'[{i}] "{q.text}" — {q.speaker}' for i, q in enumerate(quotes, start=1))
        or "(none)"
    )

    user_prompt = (
        f"TOPIC: {topic}\n\n"
        f"PUBLISHED ARTICLE:\n{article.html}\n\n"
        f"SOURCE FACTS (with IDs in brackets):\n{facts_text}\n\n"
        f"SOURCE QUOTES (with IDs in brackets):\n{quotes_text}"
    )

    if _agent is not None:
        _t0 = time.perf_counter()
        result = await _agent.run(user_prompt)
        _model_used = config.model
    else:

        def _factory(m: str) -> tuple[Agent[Any, Any], str]:
            sys_prompt = render_prompt(
                _PROMPTS_DIR / "followup.j2",
                num_titles=config.num_titles,
                num_topics=config.num_topics,
                format_style=model_format_style(m),
                guidelines=domain.guidelines,
                example_titles=list(domain.example_titles),
            )
            return Agent(m, output_type=FollowUpOutput), sys_prompt

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

    # Map ID lists back to source-text strings. Out-of-range or duplicate IDs
    # are silently dropped so a hallucinated ID never inflates usage counts.
    used_facts = [
        facts[i - 1].text for i in dict.fromkeys(output.used_fact_ids) if 1 <= i <= len(facts)
    ]
    used_quotes = [
        quotes[i - 1].text for i in dict.fromkeys(output.used_quote_ids) if 1 <= i <= len(quotes)
    ]

    sources = list(
        {url for f in extraction_result.facts for url in f.source_urls if url}
        | {url for q in extraction_result.quotes for url in q.source_urls if url}
    )

    return ArticleOutput(
        html=article.html,
        alternative_titles=output.alternative_titles,
        followup_topics=output.followup_topics,
        used_facts=used_facts,
        used_quotes=used_quotes,
        sources=sources,
    )
