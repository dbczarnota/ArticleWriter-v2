# agents/scraping/agent.py
from __future__ import annotations
import pathlib
import time
from pydantic import BaseModel
from pydantic_ai import Agent
from agents._base.config import ScrapingConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents._base.resilient import run_with_fallback
from agents._base.run_context import record_agent_call
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
    extra_urls: list[str] | None = None,
    max_pages: int = 10,
    _filter_agent: Agent | None = None,
) -> tuple[list[ScrapedPage], list[str]]:
    """LLM snippet pre-filter, then scrape approved URLs via tiered orchestrator.

    Mirrors how Claude Code works: evaluate snippets before fetching full pages —
    fewer requests, cheaper, faster.

    Returns (scraped_pages, rejected_urls) where rejected_urls are URLs from
    search_results that were not approved by the LLM filter.
    """
    if not search_results:
        return [], []

    results_text = "\n\n".join(
        f"[{i + 1}] URL: {r.url}\nTitle: {r.title}\nSnippet: {r.snippet}"
        for i, r in enumerate(search_results)
    )

    _t0 = time.perf_counter()
    if _filter_agent is not None:
        filter_result = await _filter_agent.run(results_text)
        _filter_model_used = scraping_config.filter_model
    else:
        def _factory(m: str) -> Agent:
            return Agent(
                m,
                output_type=ApprovedUrlsResult,
                system_prompt=render_prompt(
                    _PROMPTS_DIR / "filter.j2",
                    topic=topic,
                    format_style=model_format_style(m),
                ),
            )
        filter_result, _filter_model_used = await run_with_fallback(
            (scraping_config.filter_model, *scraping_config.filter_fallback_models),
            agent_factory=_factory,
            user_prompt=results_text,
            agent_name="scraping_filter",
        )
    _u = filter_result.usage()
    record_agent_call("scraping_filter", _filter_model_used, _u.input_tokens or 0, _u.output_tokens or 0,
                      (time.perf_counter() - _t0) * 1000)
    approved_urls = filter_result.output.urls[:max_pages]

    approved_set = set(approved_urls)
    rejected_urls = [r.url for r in search_results if r.url not in approved_set]

    # User-supplied URLs bypass the LLM filter but still go through scraping
    if extra_urls:
        seen = set(approved_urls)
        approved_urls = approved_urls + [u for u in extra_urls if u not in seen]

    if not approved_urls:
        return [], rejected_urls

    pages = await scrape_urls(approved_urls, config=scraping_config, jina_api_key=jina_api_key)
    return pages, rejected_urls
