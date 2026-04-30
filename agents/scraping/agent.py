# agents/scraping/agent.py
from __future__ import annotations
import pathlib
from pydantic import BaseModel
from pydantic_ai import Agent
from agents._base.config import ScrapingConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents._base.types import ScrapedPage, SearchResult
from toolsets.scraping.orchestrator import scrape_urls

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class ApprovedUrlsResult(BaseModel):
    urls: list[str]


async def run_scraping_agent(
    search_results: list[SearchResult],
    topic: str,
    *,
    scraping_config: ScrapingConfig,
    jina_api_key: str | None,
    _filter_agent: Agent | None = None,
) -> list[ScrapedPage]:
    """LLM snippet pre-filter, then scrape approved URLs via tiered orchestrator.

    Mirrors how Claude Code works: evaluate snippets before fetching full pages —
    fewer requests, cheaper, faster.
    """
    if not search_results:
        return []

    results_text = "\n\n".join(
        f"[{i + 1}] URL: {r.url}\nTitle: {r.title}\nSnippet: {r.snippet}"
        for i, r in enumerate(search_results)
    )

    filter_agent = _filter_agent or Agent(
        scraping_config.filter_model,
        output_type=ApprovedUrlsResult,
        system_prompt=render_prompt(
            _PROMPTS_DIR / "filter.j2",
            topic=topic,
            format_style=model_format_style(scraping_config.filter_model),
        ),
    )

    filter_result = await filter_agent.run(results_text)
    approved_urls = filter_result.output.urls

    if not approved_urls:
        return []

    return await scrape_urls(approved_urls, config=scraping_config, jina_api_key=jina_api_key)
