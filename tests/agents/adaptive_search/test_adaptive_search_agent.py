import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from agents._base.config import AdaptiveSearchAgentConfig
from agents._base.types import Fact, Quote
from agents.adaptive_search.agent import AdaptiveSearchDecision, run_adaptive_search_agent
from agents.extraction.agent import ExtractionResult


def _make_extraction_result(num_facts: int = 5, num_quotes: int = 2) -> ExtractionResult:
    facts = [
        Fact(
            text=f"Fakt {i}",
            context="Dawid Podsiadło, trasa 2025",
            source_url="https://example.com",
            source_title="Artykuł",
        )
        for i in range(num_facts)
    ]
    quotes = [
        Quote(
            text=f"Cytat {i}",
            speaker="Dawid Podsiadło",
            context="o trasie",
            source_url="https://example.com",
        )
        for i in range(num_quotes)
    ]
    return ExtractionResult(facts=facts, quotes=quotes, keywords=["kw1"])


def _make_adaptive_agent(needs_more: bool, queries: list[str] | None = None):
    return Agent(
        TestModel(
            custom_output_args={
                "needs_more_research": needs_more,
                "additional_queries": queries or [],
                "reasoning": "Test reasoning",
            }
        ),
        output_type=AdaptiveSearchDecision,
        system_prompt="test",
    )


@pytest.mark.asyncio
async def test_returns_no_when_enough_material():
    result = await run_adaptive_search_agent(
        _make_extraction_result(num_facts=6, num_quotes=2),
        topic="Dawid Podsiadło",
        config=AdaptiveSearchAgentConfig(),
        _agent=_make_adaptive_agent(needs_more=False),
    )
    assert result.needs_more_research is False
    assert result.additional_queries == []


@pytest.mark.asyncio
async def test_returns_yes_with_queries_when_insufficient():
    result = await run_adaptive_search_agent(
        _make_extraction_result(num_facts=1, num_quotes=0),
        topic="Dawid Podsiadło",
        config=AdaptiveSearchAgentConfig(),
        _agent=_make_adaptive_agent(
            needs_more=True, queries=["Dawid Podsiadło zarobki 2025", "Podsiadło trasa wyniki"]
        ),
    )
    assert result.needs_more_research is True
    assert len(result.additional_queries) == 2


@pytest.mark.asyncio
async def test_empty_extraction_result_triggers_more_research():
    """Empty extraction always asks for more research (no agent call needed)."""
    result = await run_adaptive_search_agent(
        ExtractionResult(facts=[], quotes=[], keywords=[]),
        topic="topic",
        config=AdaptiveSearchAgentConfig(),
    )
    assert result.needs_more_research is True
