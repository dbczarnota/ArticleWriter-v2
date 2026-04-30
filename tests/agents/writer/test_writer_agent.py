import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from agents._base.config import WriterAgentConfig
from agents.instructions.agent import WritingBrief
from agents.reflection.agent import ReflectionFeedback
from agents.writer.agent import ArticleHtml, run_writer_agent
from domains._base.config import DomainConfig


_DOMAIN = DomainConfig(
    name="test_domain",
    description="Test",
    language="pl",
    target_word_count=600,
    guidelines="Pisz krótko.",
    example_articles=(),
)

_BRIEF = WritingBrief(
    selected_facts=["Zarobił 2 mln zł [Dawid Podsiadło, trasa 2025]"],
    selected_quotes=['"To był najpiękniejszy rok" — Dawid Podsiadło (o trasie)'],
    writing_instructions="Napisz emocjonalny artykuł o sukcesie artysty.",
)

_HTML = "<h1>Dawid zarobił miliony</h1><p>Artysta odniósł ogromny sukces.</p>"


def _make_writer_agent(html: str = _HTML) -> Agent:
    return Agent(
        TestModel(custom_output_args={"html": html}),
        output_type=ArticleHtml,
        system_prompt="test",
    )


@pytest.mark.asyncio
async def test_run_writer_agent_returns_html():
    result = await run_writer_agent(
        _BRIEF,
        topic="Dawid Podsiadło",
        domain=_DOMAIN,
        config=WriterAgentConfig(),
        _agent=_make_writer_agent(),
    )
    assert isinstance(result, ArticleHtml)
    assert "<h1>" in result.html
    assert len(result.html) > 20


@pytest.mark.asyncio
async def test_run_writer_agent_with_reflection_feedback():
    """When reflection_feedback is provided, it is included in the user prompt."""
    feedback = ReflectionFeedback(
        feedback="Dodaj więcej emocji w pierwszym akapicie.",
        priority_fixes=["Wzmocnij lead", "Usuń suchy wstęp"],
    )
    brief = WritingBrief(
        selected_facts=["Fakt"],
        selected_quotes=['"Cytat" — Ktoś'],
        writing_instructions="Pisz o sukcesie.",
    )
    result = await run_writer_agent(
        brief,
        topic="topic",
        domain=_DOMAIN,
        config=WriterAgentConfig(),
        reflection_feedback=feedback,
        _agent=_make_writer_agent(),
    )
    assert result.html == _HTML


@pytest.mark.asyncio
async def test_run_writer_agent_no_examples_domain():
    """Works correctly when domain has no example articles."""
    domain_no_examples = DomainConfig(
        name="no_examples",
        description="No examples",
        language="en",
        guidelines="Write factually.",
        example_articles=(),
    )
    result = await run_writer_agent(
        _BRIEF,
        topic="topic",
        domain=domain_no_examples,
        config=WriterAgentConfig(),
        _agent=_make_writer_agent("<p>Article content here.</p>"),
    )
    assert result.html == "<p>Article content here.</p>"
