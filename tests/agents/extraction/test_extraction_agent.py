# tests/agents/extraction/test_extraction_agent.py
import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from agents._base.config import ExtractionAgentConfig
from agents._base.types import Fact, ParsedArticle, Quote
from agents.extraction.agent import ExtractionOutput, run_extraction_agent


def _make_parsed_article(url: str = "https://example.com/art") -> ParsedArticle:
    return ParsedArticle(
        url=url,
        title="Dawid Podsiadło zarobił miliony",
        content="Artysta zarobił 2 mln zł. Powiedział: 'To był najpiękniejszy rok'.",
    )


def _make_extraction_agent(
    facts: list[dict] | None = None,
    quotes: list[dict] | None = None,
    keywords: list[str] | None = None,
):
    if facts is None:
        facts = [
            {
                "text": "Zarobił 2 miliony złotych",
                "context": "Dawid Podsiadło, trasa 2025",
                "source_urls": ["https://example.com/art"],
            }
        ]
    if quotes is None:
        quotes = [
            {
                "text": "To był najpiękniejszy rok",
                "speaker": "Dawid Podsiadło",
                "context": "o trasie 2025",
                "source_urls": ["https://example.com/art"],
            }
        ]
    if keywords is None:
        keywords = ["Dawid Podsiadło", "trasa 2025", "zarobki"]

    return Agent(
        TestModel(
            custom_output_args={
                "facts": facts,
                "quotes": quotes,
                "keywords": keywords,
            }
        ),
        output_type=ExtractionOutput,
        system_prompt="test",
    )


@pytest.mark.asyncio
async def test_run_extraction_agent_returns_facts_and_quotes():
    articles = [_make_parsed_article()]
    result = await run_extraction_agent(
        articles,
        topic="Dawid Podsiadło",
        language="pl",
        config=ExtractionAgentConfig(),
        _agent=_make_extraction_agent(),
    )
    assert len(result.facts) == 1
    assert isinstance(result.facts[0], Fact)
    assert result.facts[0].text == "Zarobił 2 miliony złotych"
    assert result.facts[0].context == "Dawid Podsiadło, trasa 2025"

    assert len(result.quotes) == 1
    assert isinstance(result.quotes[0], Quote)
    assert result.quotes[0].speaker == "Dawid Podsiadło"

    assert "Dawid Podsiadło" in result.keywords


@pytest.mark.asyncio
async def test_run_extraction_agent_empty_input():
    result = await run_extraction_agent(
        [],
        topic="topic",
        language="pl",
        config=ExtractionAgentConfig(),
    )
    assert result.facts == []
    assert result.quotes == []
    assert result.keywords == []


@pytest.mark.asyncio
async def test_run_extraction_agent_no_facts_case():
    """Agent may return empty lists — we accept that."""
    articles = [_make_parsed_article()]
    result = await run_extraction_agent(
        articles,
        topic="topic",
        language="pl",
        config=ExtractionAgentConfig(),
        _agent=_make_extraction_agent(facts=[], quotes=[], keywords=[]),
    )
    assert result.facts == []
    assert result.quotes == []
