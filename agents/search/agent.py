# agents/search/agent.py
from __future__ import annotations
import pathlib
from pydantic import BaseModel
from pydantic_ai import Agent
from agents._base.config import SearchAgentConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents._base.types import SearchResult
from toolsets.scraping.serper import search as serper_search

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

    Deduplicates URLs across queries — same article from multiple queries counted once.
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

    result = await agent.run(
        f"Topic: {topic}\nGenerate all queries in language: {domain_language}"
    )

    all_results: list[SearchResult] = []
    seen_urls: set[str] = set()
    for query in result.output.queries:
        for r in await serper_search(
            query,
            num=config.max_results,
            freshness=config.search_freshness,
            language=domain_language,
            api_key=serper_api_key,
        ):
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                all_results.append(r)

    return all_results
