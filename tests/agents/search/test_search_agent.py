# tests/agents/search/test_search_agent.py
import httpx
import pytest
import respx
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from agents._base.config import SearchAgentConfig
from agents._base.types import SearchResult
from agents.search.agent import SearchQueriesResult, run_search_agent


def _make_test_agent(queries: list[str]):
    """Return Agent backed by TestModel that returns the given queries."""
    return Agent(
        TestModel(custom_output_args={"queries": queries}),
        output_type=SearchQueriesResult,
        system_prompt="test",
    )


def _serper_response(url: str, title: str = "T", snippet: str = "S") -> dict:
    return {"organic": [{"link": url, "title": title, "snippet": snippet}]}


@pytest.mark.asyncio
@respx.mock
async def test_run_search_agent_returns_search_results():
    """Each query hits Serper and returns a SearchResult."""
    call_n = 0

    def side_effect(request):
        nonlocal call_n
        call_n += 1
        return httpx.Response(
            200,
            json=_serper_response(f"https://example.com/news{call_n}"),
        )

    respx.post("https://google.serper.dev/search").mock(side_effect=side_effect)

    results = await run_search_agent(
        "Dawid Podsiadło",
        config=SearchAgentConfig(),
        domain_language="pl",
        serper_api_key="key",
        _agent=_make_test_agent(["Dawid Podsiadło 2025", "Podsiadło trasa"]),
    )

    assert len(results) == 2
    assert all(isinstance(r, SearchResult) for r in results)
    assert results[0].source == "web"


@pytest.mark.asyncio
@respx.mock
async def test_run_search_agent_deduplicates_urls():
    """Same URL from two queries appears only once in results."""
    respx.post("https://google.serper.dev/search").mock(
        return_value=httpx.Response(200, json=_serper_response("https://example.com/same-url"))
    )

    results = await run_search_agent(
        "topic",
        config=SearchAgentConfig(),
        domain_language="pl",
        serper_api_key="key",
        _agent=_make_test_agent(["query1", "query2"]),
    )

    assert len(results) == 1
    assert results[0].url == "https://example.com/same-url"


@pytest.mark.asyncio
@respx.mock
async def test_run_search_agent_calls_serper_for_each_query():
    """Serper called once per query."""
    call_count = 0

    def count_calls(request):
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=_serper_response(f"https://example.com/{call_count}"))

    respx.post("https://google.serper.dev/search").mock(side_effect=count_calls)

    await run_search_agent(
        "topic",
        config=SearchAgentConfig(),
        domain_language="pl",
        serper_api_key="key",
        _agent=_make_test_agent(["q1", "q2", "q3"]),
    )

    assert call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_search_agent_calls_news_when_enabled():
    """When news_search=True, agent fetches both /search and /news per query."""
    respx.post("https://google.serper.dev/search").mock(
        return_value=httpx.Response(
            200, json={"organic": [{"link": "https://web.com/1", "title": "Web", "snippet": "s"}]}
        )
    )
    respx.post("https://google.serper.dev/news").mock(
        return_value=httpx.Response(
            200, json={"news": [{"link": "https://news.com/1", "title": "News", "snippet": "n"}]}
        )
    )

    results = await run_search_agent(
        "topic",
        config=SearchAgentConfig(news_search=True, num_queries=1, max_results=5),
        domain_language="pl",
        serper_api_key="k",
        _agent=_make_test_agent(["query1"]),
    )
    urls = [r.url for r in results]
    assert "https://web.com/1" in urls
    assert "https://news.com/1" in urls
