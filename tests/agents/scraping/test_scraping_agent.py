# tests/agents/scraping/test_scraping_agent.py
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from agents._base.config import ScrapingConfig
from agents._base.types import ScrapedPage, SearchResult
from agents.scraping.agent import ApprovedUrlsResult, run_scraping_agent


def _make_search_result(url: str, snippet: str = "Dobry snippet z faktami.") -> SearchResult:
    return SearchResult(url=url, title="Tytuł", snippet=snippet, source="web")


def _make_scraped_page(url: str) -> ScrapedPage:
    return ScrapedPage(url=url, title="T", content="c " * 60, scrape_tier="httpx")


def _make_filter_agent(approved_urls: list[str]):
    return Agent(
        TestModel(custom_output_args={"urls": approved_urls}),
        output_type=ApprovedUrlsResult,
        system_prompt="test",
    )


@pytest.mark.asyncio
async def test_run_scraping_agent_scrapes_approved_urls():
    """LLM selects URLs, orchestrator scrapes them."""
    urls = ["https://a.com/art", "https://b.com/art"]
    search_results = [_make_search_result(url) for url in urls]

    with patch("agents.scraping.agent.scrape_urls", new_callable=AsyncMock) as mock_scrape:
        mock_scrape.return_value = [_make_scraped_page(u) for u in urls]

        pages, rejected = await run_scraping_agent(
            search_results,
            topic="Dawid Podsiadło",
            scraping_config=ScrapingConfig(),
            jina_api_key=None,
            _filter_agent=_make_filter_agent(urls),
        )

    assert len(pages) == 2
    assert rejected == []
    mock_scrape.assert_called_once_with(urls, config=ScrapingConfig(), jina_api_key=None)


@pytest.mark.asyncio
async def test_run_scraping_agent_skips_rejected_urls():
    """If LLM rejects all URLs, return empty list without scraping."""
    search_results = [_make_search_result("https://bad.com")]

    with patch("agents.scraping.agent.scrape_urls", new_callable=AsyncMock) as mock_scrape:
        pages, rejected = await run_scraping_agent(
            search_results,
            topic="topic",
            scraping_config=ScrapingConfig(),
            jina_api_key=None,
            _filter_agent=_make_filter_agent([]),
        )

    assert pages == []
    assert rejected == ["https://bad.com"]
    mock_scrape.assert_not_called()


@pytest.mark.asyncio
async def test_run_scraping_agent_empty_input_returns_empty():
    """No search results → no scraping."""
    with patch("agents.scraping.agent.scrape_urls", new_callable=AsyncMock) as mock_scrape:
        pages, rejected = await run_scraping_agent(
            [],
            topic="topic",
            scraping_config=ScrapingConfig(),
            jina_api_key=None,
        )

    assert pages == []
    assert rejected == []
    mock_scrape.assert_not_called()


@pytest.mark.asyncio
async def test_run_scraping_agent_passes_jina_key_to_orchestrator():
    """jina_api_key forwarded to scrape_urls."""
    url = "https://example.com/art"

    with patch("agents.scraping.agent.scrape_urls", new_callable=AsyncMock) as mock_scrape:
        mock_scrape.return_value = [_make_scraped_page(url)]

        _pages, _rejected = await run_scraping_agent(
            [_make_search_result(url)],
            topic="topic",
            scraping_config=ScrapingConfig(),
            jina_api_key="my-jina-key",
            _filter_agent=_make_filter_agent([url]),
        )

    _, kwargs = mock_scrape.call_args
    assert kwargs["jina_api_key"] == "my-jina-key"


@pytest.mark.asyncio
async def test_extra_urls_not_in_rejected():
    """User-supplied extra_urls bypass the LLM filter and must NOT appear in rejected_urls."""
    search_results = [_make_search_result("https://example.com/a")]
    extra = ["https://manual.com/article"]

    filter_agent = Agent(
        TestModel(custom_output_args={"urls": ["https://example.com/a"]}),
        output_type=ApprovedUrlsResult,
    )

    with patch("agents.scraping.agent.scrape_urls", new_callable=AsyncMock) as mock_scrape:
        mock_scrape.return_value = [
            _make_scraped_page("https://example.com/a"),
            _make_scraped_page("https://manual.com/article"),
        ]

        _, rejected = await run_scraping_agent(
            search_results,
            "topic",
            scraping_config=ScrapingConfig(),
            jina_api_key=None,
            extra_urls=extra,
            _filter_agent=filter_agent,
        )

    assert "https://manual.com/article" not in rejected
