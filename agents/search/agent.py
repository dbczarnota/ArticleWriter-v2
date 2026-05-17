# agents/search/agent.py
from __future__ import annotations

import asyncio
import pathlib
import time
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent

from agents._base.config import SearchAgentConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents._base.resilient import run_with_fallback
from agents._base.run_context import record_agent_call
from agents._base.types import SearchResult
from toolsets.scraping.serper import search as serper_search
from toolsets.scraping.serper import search_news as serper_search_news

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class SearchQueriesResult(BaseModel):
    queries: list[str]


async def run_search_agent(
    topic: str,
    *,
    config: SearchAgentConfig,
    domain_language: str,
    serper_api_key: str,
    site_include: tuple[str, ...] = (),
    site_exclude: tuple[str, ...] = (),
    _agent: Agent[Any, Any] | None = None,
) -> list[SearchResult]:
    """Generate search queries via LLM, fetch results from Serper for each query.

    When config.news_search=True, also fetches Google News results in parallel.
    Deduplicates URLs across all queries and sources.
    """
    _user_prompt = f"Topic: {topic}\nGenerate all queries in language: {domain_language}"

    if _agent is not None:
        _t0 = time.perf_counter()
        result = await _agent.run(_user_prompt)
        _model_used = config.model
    else:

        def _factory(m: str) -> tuple[Agent[Any, Any], str]:
            sys_prompt = render_prompt(
                _PROMPTS_DIR / "search.j2",
                num_queries=config.num_queries,
                format_style=model_format_style(m),
            )
            return Agent(m, output_type=SearchQueriesResult), sys_prompt

        _t0 = time.perf_counter()
        result, _model_used = await run_with_fallback(
            (config.model, *config.fallback_models),
            agent_factory=_factory,
            user_prompt=_user_prompt,
            agent_name="search",
        )
    _u = result.usage
    record_agent_call(
        "search",
        _model_used,
        _u.input_tokens or 0,
        _u.output_tokens or 0,
        (time.perf_counter() - _t0) * 1000,
    )

    all_results: list[SearchResult] = []
    seen_urls: set[str] = set()

    # Always include the editor's raw topic as a query — they may have phrased it
    # in the most precise way for the story, and the LLM-generated queries can drift.
    # Place it first so its results land before the LLM-generated ones; dedupe afterwards.
    seen_queries: set[str] = set()
    queries: list[str] = []
    for q in [topic, *result.output.queries]:
        q_norm = q.strip()
        q_key = q_norm.lower()
        if q_norm and q_key not in seen_queries:
            seen_queries.add(q_key)
            queries.append(q_norm)

    for query in queries:
        coros = [
            serper_search(
                query,
                num=config.max_results,
                freshness=config.search_freshness,
                language=domain_language,
                api_key=serper_api_key,
                site_include=site_include,
                site_exclude=site_exclude,
            )
        ]
        if config.news_search:
            coros.append(
                serper_search_news(
                    query,
                    num=config.max_results,
                    language=domain_language,
                    api_key=serper_api_key,
                    site_include=site_include,
                    site_exclude=site_exclude,
                )
            )
        batches = await asyncio.gather(*coros)
        for batch in batches:
            for r in batch:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    all_results.append(r)

    return all_results
