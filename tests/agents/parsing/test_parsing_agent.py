# tests/agents/parsing/test_parsing_agent.py
import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from agents._base.config import ParsingAgentConfig
from agents._base.types import ParsedArticle, ScrapedPage
from agents.parsing.agent import ParseResult, run_parsing_agent


def _make_scraped_page(url: str = "https://example.com/art") -> ScrapedPage:
    return ScrapedPage(
        url=url,
        title="Dawid Podsiadło trasa 2025",
        content="Dawid Podsiadło zarobił 2 miliony złotych. Artysta ogłosił kolejną trasę.",
        scrape_tier="httpx",
    )


def _make_parse_agent(
    is_article: bool = True,
    title: str = "Dawid Podsiadło trasa 2025",
    content: str = "Czysty tekst artykułu.",
    publication_date: str | None = "2025-04-15",
) -> Agent:
    return Agent(
        TestModel(
            custom_output_args={
                "is_article": is_article,
                "title": title,
                "content": content,
                "publication_date": publication_date,
            }
        ),
        output_type=ParseResult,
        system_prompt="test",
    )


@pytest.mark.asyncio
async def test_run_parsing_agent_returns_parsed_articles():
    pages = [_make_scraped_page()]
    results = await run_parsing_agent(
        pages, config=ParsingAgentConfig(), _agent=_make_parse_agent()
    )
    assert len(results) == 1
    assert isinstance(results[0], ParsedArticle)
    assert results[0].url == "https://example.com/art"
    assert results[0].title == "Dawid Podsiadło trasa 2025"
    assert results[0].publication_date == "2025-04-15"


@pytest.mark.asyncio
async def test_run_parsing_agent_filters_non_articles():
    """Pages marked is_article=False by LLM are excluded."""
    pages = [_make_scraped_page("https://homepage.com")]
    results = await run_parsing_agent(
        pages,
        config=ParsingAgentConfig(),
        _agent=_make_parse_agent(is_article=False),
    )
    assert results == []


@pytest.mark.asyncio
async def test_run_parsing_agent_processes_each_page():
    """Each page processed by the agent separately."""
    pages = [
        _make_scraped_page("https://a.com"),
        _make_scraped_page("https://b.com"),
    ]
    results = await run_parsing_agent(
        pages, config=ParsingAgentConfig(), _agent=_make_parse_agent()
    )
    assert len(results) == 2
    assert {r.url for r in results} == {"https://a.com", "https://b.com"}


@pytest.mark.asyncio
async def test_run_parsing_agent_empty_input():
    results = await run_parsing_agent([], config=ParsingAgentConfig())
    assert results == []
