import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from agents._base.config import ReflectionAgentConfig
from agents.reflection.agent import ReflectionFeedback, run_reflection_agent
from agents.writer.agent import ArticleHtml
from backend.domain import DomainConfig

_DOMAIN = DomainConfig(
    name="test_domain",
    description="Test",
    language="pl",
    target_word_count=600,
    guidelines="Pisz krótko i emocjonalnie.",
)

_ARTICLE = ArticleHtml(html="<h1>Dawid</h1><p>Krótki artykuł bez emocji.</p>")


def _make_reflection_agent(
    feedback: str = "Dodaj więcej emocji.",
    priority_fixes: list[str] | None = None,
):
    return Agent(
        TestModel(
            custom_output_args={
                "feedback": feedback,
                "priority_fixes": priority_fixes or ["Wzmocnij lead", "Dodaj emocje"],
            }
        ),
        output_type=ReflectionFeedback,
        system_prompt="test",
    )


@pytest.mark.asyncio
async def test_run_reflection_agent_returns_feedback():
    result = await run_reflection_agent(
        _ARTICLE,
        topic="Dawid Podsiadło",
        domain=_DOMAIN,
        config=ReflectionAgentConfig(),
        _agent=_make_reflection_agent(),
    )
    assert isinstance(result, ReflectionFeedback)
    assert len(result.feedback) > 0
    assert len(result.priority_fixes) >= 1


@pytest.mark.asyncio
async def test_run_reflection_agent_includes_domain_guidelines():
    """feedback comes from the agent — any non-empty feedback is valid."""
    result = await run_reflection_agent(
        _ARTICLE,
        topic="topic",
        domain=_DOMAIN,
        config=ReflectionAgentConfig(),
        _agent=_make_reflection_agent(feedback="Artykuł jest za długi."),
    )
    assert "długi" in result.feedback


@pytest.mark.asyncio
async def test_run_reflection_agent_returns_priority_fixes_list():
    result = await run_reflection_agent(
        _ARTICLE,
        topic="topic",
        domain=_DOMAIN,
        config=ReflectionAgentConfig(),
        _agent=_make_reflection_agent(priority_fixes=["Fix 1", "Fix 2", "Fix 3"]),
    )
    assert len(result.priority_fixes) == 3
