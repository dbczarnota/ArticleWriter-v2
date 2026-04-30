import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from agents._base.config import FollowUpAgentConfig
from agents._base.types import ArticleOutput, Fact, Quote
from agents.extraction.agent import ExtractionResult
from agents.followup.agent import run_followup_agent
from agents.writer.agent import ArticleHtml


_ARTICLE = ArticleHtml(html="<h1>Dawid zarobił miliony</h1><p>Treść artykułu.</p>")

_EXTRACTION = ExtractionResult(
    facts=[
        Fact("Zarobił 2 mln zł", "Dawid Podsiadło, trasa 2025", "https://e.com", "Art"),
        Fact("Sprzedał 50 tys. biletów", "Dawid Podsiadło, trasa 2025", "https://e.com", "Art"),
    ],
    quotes=[
        Quote("To był najpiękniejszy rok", "Dawid Podsiadło", "o trasie", "https://e.com"),
    ],
    keywords=["Dawid Podsiadło"],
)

_CONFIG = FollowUpAgentConfig()


def _make_followup_agent(
    alternative_titles: list[str] | None = None,
    followup_topics: list[str] | None = None,
    used_facts: list[str] | None = None,
    used_quotes: list[str] | None = None,
) -> Agent:
    from agents.followup.agent import FollowUpOutput
    return Agent(
        TestModel(
            custom_output_args={
                "alternative_titles": alternative_titles or [
                    "Dawid Podsiadło: miliony na koncie",
                    "Wielki sukces Podsiadły",
                    "Trasa roku zakończona",
                ],
                "followup_topics": followup_topics or [
                    "Dawid Podsiadło dyskografia",
                    "Polscy artyści vs zagranica",
                ],
                "used_facts": used_facts or ["Zarobił 2 mln zł"],
                "used_quotes": used_quotes or ["To był najpiękniejszy rok"],
            }
        ),
        output_type=FollowUpOutput,
        system_prompt="test",
    )


@pytest.mark.asyncio
async def test_run_followup_agent_returns_article_output():
    result = await run_followup_agent(
        _ARTICLE,
        topic="Dawid Podsiadło",
        extraction_result=_EXTRACTION,
        config=_CONFIG,
        _agent=_make_followup_agent(),
    )
    assert isinstance(result, ArticleOutput)
    assert result.html == _ARTICLE.html
    assert len(result.alternative_titles) >= 1
    assert len(result.followup_topics) >= 1


@pytest.mark.asyncio
async def test_run_followup_agent_respects_num_titles_config():
    """alternative_titles count honours FollowUpAgentConfig.num_titles."""
    config = FollowUpAgentConfig(num_titles=5, num_topics=3)
    titles = [f"Tytuł {i}" for i in range(5)]
    topics = [f"Temat {i}" for i in range(3)]

    result = await run_followup_agent(
        _ARTICLE,
        topic="topic",
        extraction_result=_EXTRACTION,
        config=config,
        _agent=_make_followup_agent(alternative_titles=titles, followup_topics=topics),
    )
    assert len(result.alternative_titles) == 5
    assert len(result.followup_topics) == 3


@pytest.mark.asyncio
async def test_run_followup_agent_preserves_html():
    result = await run_followup_agent(
        _ARTICLE,
        topic="topic",
        extraction_result=_EXTRACTION,
        config=_CONFIG,
        _agent=_make_followup_agent(),
    )
    assert result.html == "<h1>Dawid zarobił miliony</h1><p>Treść artykułu.</p>"
