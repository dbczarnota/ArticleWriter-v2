# agents/reflection/agent.py
from __future__ import annotations

import pathlib
import time
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent

from agents._base.config import ReflectionAgentConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents._base.resilient import run_with_fallback
from agents._base.run_context import record_agent_call
from agents._base.types import ParsedArticle
from agents.extraction.agent import ExtractionResult
from agents.writer.agent import ArticleHtml
from backend.domain import DomainConfig

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class ReflectionFeedback(BaseModel):
    feedback: str
    priority_fixes: list[str]


async def run_reflection_agent(
    article: ArticleHtml,
    *,
    topic: str,
    domain: DomainConfig,
    config: ReflectionAgentConfig,
    extraction: ExtractionResult | None = None,
    context_articles: list[ParsedArticle] | None = None,
    _agent: Agent[Any, Any] | None = None,
) -> ReflectionFeedback:
    """Review article quality against domain guidelines and return actionable feedback.

    `extraction` (when provided) is the SOURCE OF TRUTH for fact-checking. The reviewer
    must validate the article against these extracted facts/quotes from real sources —
    NOT against its own training data, which is months old and outdated for current news.

    `context_articles` (when provided) are competitor articles covering the same story.
    They're shown to the reviewer for tone/comprehensiveness reference, NEVER passed to
    the writer (which avoids plagiarism). Reviewer is instructed in reflection.j2 to use
    them as context only.
    """
    _user_prompt = f"TOPIC: {topic}\n\nARTICLE TO REVIEW:\n{article.html}"

    if extraction is not None:
        facts_block = "\n".join(
            f"- {f.text} (context: {f.context}; "
            f"corroboration: {len(f.source_urls)}; "
            f"sources: {', '.join(f.source_urls) or '(none)'})"
            for f in extraction.facts
        )
        quotes_block = "\n".join(
            f'- "{q.text}" — {q.speaker} (context: {q.context}; '
            f"corroboration: {len(q.source_urls)}; "
            f"sources: {', '.join(q.source_urls) or '(none)'})"
            for q in extraction.quotes
        )
        _user_prompt += (
            "\n\n--- EXTRACTED SOURCE MATERIAL (THIS IS GROUND TRUTH FOR FACT-CHECKING) ---\n\n"
            f"FACTS:\n{facts_block or '(none)'}\n\n"
            f"QUOTES:\n{quotes_block or '(none)'}"
        )

    if context_articles:
        articles_block = "\n\n".join(
            f"### Competitor article {i + 1}\n"
            f"Source: {a.url}\n"
            f"Title: {a.title}\n"
            f"Published: {a.publication_date or 'unknown'}\n\n"
            f"{a.content}"
            for i, a in enumerate(context_articles)
        )
        _user_prompt += (
            "\n\n--- COMPETITOR COVERAGE (CONTEXT ONLY — DO NOT INSTRUCT WRITER TO COPY) ---\n\n"
            f"{articles_block}"
        )

    if _agent is not None:
        _t0 = time.perf_counter()
        result = await _agent.run(_user_prompt)
        _model_used = config.model
    else:

        def _factory(m: str) -> tuple[Agent[Any, Any], str]:
            sys_prompt = render_prompt(
                _PROMPTS_DIR / "reflection.j2",
                domain_name=domain.name,
                language=domain.language,
                guidelines=domain.guidelines,
                html_format=domain.html_format,
                reflection_stance=domain.reflection_stance,
                target_word_count=domain.target_word_count,
                format_style=model_format_style(m),
            )
            return Agent(m, output_type=ReflectionFeedback), sys_prompt

        _t0 = time.perf_counter()
        result, _model_used = await run_with_fallback(
            (config.model, *config.fallback_models),
            agent_factory=_factory,
            user_prompt=_user_prompt,
            agent_name="reflection",
        )
    _u = result.usage()
    record_agent_call(
        "reflection",
        _model_used,
        _u.input_tokens or 0,
        _u.output_tokens or 0,
        (time.perf_counter() - _t0) * 1000,
    )
    return result.output
