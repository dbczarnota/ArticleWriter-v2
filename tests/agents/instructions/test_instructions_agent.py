import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from agents._base.config import InstructionsAgentConfig
from agents._base.types import Fact, Quote
from agents.extraction.agent import ExtractionResult
from agents.instructions.agent import WritingBrief, run_instructions_agent
from backend.domain import DomainConfig

_DOMAIN = DomainConfig(
    name="test_domain",
    description="Test domain",
    language="pl",
    target_word_count=600,
    max_facts_in_article=4,
    max_quotes_in_article=2,
    guidelines="Pisz krótko i na temat.",
)

_EXTRACTION = ExtractionResult(
    facts=[
        Fact("Zarobił 2 mln zł", "Dawid Podsiadło, trasa 2025", "https://e.com", "Art"),
        Fact("Sprzedał 50 tys. biletów", "Dawid Podsiadło, trasa 2025", "https://e.com", "Art"),
        Fact("Trasa trwała 3 miesiące", "Dawid Podsiadło, trasa 2025", "https://e.com", "Art"),
    ],
    quotes=[
        Quote("To był najpiękniejszy rok", "Dawid Podsiadło", "o trasie", "https://e.com"),
    ],
    keywords=["Dawid Podsiadło", "trasa 2025"],
)


def _make_instructions_agent(
    selected_facts: list[str] | None = None,
    selected_quotes: list[str] | None = None,
    writing_instructions: str = "Napisz emocjonalny artykuł.",
):
    return Agent(
        TestModel(
            custom_output_args={
                "selected_facts": selected_facts
                or ["Zarobił 2 mln zł [Dawid Podsiadło, trasa 2025]"],
                "selected_quotes": selected_quotes
                or ['"To był najpiękniejszy rok" — Dawid Podsiadło (o trasie)'],
                "writing_instructions": writing_instructions,
            }
        ),
        output_type=WritingBrief,
        system_prompt="test",
    )


@pytest.mark.asyncio
async def test_run_instructions_agent_returns_writing_brief():
    brief = await run_instructions_agent(
        _EXTRACTION,
        topic="Dawid Podsiadło",
        domain=_DOMAIN,
        config=InstructionsAgentConfig(),
        _agent=_make_instructions_agent(),
    )
    assert isinstance(brief, WritingBrief)
    assert len(brief.selected_facts) >= 1
    assert len(brief.selected_quotes) >= 1
    assert len(brief.writing_instructions) > 0


@pytest.mark.asyncio
async def test_run_instructions_agent_writing_instructions_non_empty():
    brief = await run_instructions_agent(
        _EXTRACTION,
        topic="Dawid Podsiadło",
        domain=_DOMAIN,
        config=InstructionsAgentConfig(),
        _agent=_make_instructions_agent(writing_instructions="Skupiaj się na emocjach."),
    )
    assert "emocj" in brief.writing_instructions


@pytest.mark.asyncio
async def test_run_instructions_agent_respects_max_facts():
    """selected_facts len should not exceed domain.max_facts_in_article."""
    many_facts = [f"Fakt {i}" for i in range(10)]
    brief = await run_instructions_agent(
        _EXTRACTION,
        topic="topic",
        domain=_DOMAIN,
        config=InstructionsAgentConfig(),
        _agent=_make_instructions_agent(selected_facts=many_facts[: _DOMAIN.max_facts_in_article]),
    )
    assert len(brief.selected_facts) <= _DOMAIN.max_facts_in_article
