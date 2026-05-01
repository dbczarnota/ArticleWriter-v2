# agents/search/agent.py
from __future__ import annotations
import asyncio
import pathlib
import time
from pydantic import BaseModel
from pydantic_ai import Agent
from agents._base.config import SearchAgentConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents._base.run_context import record_agent_call
from agents._base.types import SearchResult
from toolsets.scraping.serper import search as serper_search, search_news as serper_search_news

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class SearchQueriesResult(BaseModel):
    queries: list[str]


async def run_search_agent(
    topic: str,
    *,
    config: SearchAgentConfig,
    domain_language: str,
    serper_api_key: str,
    _agent: Agent | None = None,
) -> list[SearchResult]:
    """Generate search queries via LLM, fetch results from Serper for each query.

    When config.news_search=True, also fetches Google News results in parallel.
    Deduplicates URLs across all queries and sources.
    """
    agent = _agent or Agent(
        config.model,
        output_type=SearchQueriesResult,
        system_prompt=render_prompt(
            _PROMPTS_DIR / "search.j2",
            num_queries=config.num_queries,
            format_style=model_format_style(config.model),
        ),
    )

    _t0 = time.perf_counter()
    result = await agent.run(
        f"Topic: {topic}\nGenerate all queries in language: {domain_language}"
    )
    _u = result.usage()
    record_agent_call("search", config.model, _u.input_tokens or 0, _u.output_tokens or 0,
                      (time.perf_counter() - _t0) * 1000)

    all_results: list[SearchResult] = []
    seen_urls: set[str] = set()

    for query in result.output.queries:
        coros = [serper_search(query, num=config.max_results,
                               freshness=config.search_freshness,
                               language=domain_language, api_key=serper_api_key)]
        if config.news_search:
            coros.append(serper_search_news(query, num=config.max_results,
                                            language=domain_language, api_key=serper_api_key))
        batches = await asyncio.gather(*coros)
        for batch in batches:
            for r in batch:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    all_results.append(r)

    return all_results
