import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from agents._base.config import FollowUpAgentConfig
from agents._base.types import ArticleOutput, Fact, Quote
from agents.extraction.agent import ExtractionResult
from agents.followup.agent import run_followup_agent
from agents.writer.agent import ArticleHtml
from backend.domain import DomainConfig

_ARTICLE = ArticleHtml(html="<h1>Dawid zarobił miliony</h1><p>Treść artykułu.</p>")

_EXTRACTION = ExtractionResult(
    facts=[
        Fact("Zarobił 2 mln zł", "Dawid Podsiadło, trasa 2025", source_urls=["https://e.com"]),
        Fact(
            "Sprzedał 50 tys. biletów", "Dawid Podsiadło, trasa 2025", source_urls=["https://e.com"]
        ),
    ],
    quotes=[
        Quote(
            "To był najpiękniejszy rok",
            "Dawid Podsiadło",
            "o trasie",
            source_urls=["https://e.com"],
        ),
    ],
    keywords=["Dawid Podsiadło"],
)

_CONFIG = FollowUpAgentConfig()
_DOMAIN = DomainConfig(name="test", description="test")


def test_followup_config_num_teasers_default():
    assert FollowUpAgentConfig().num_teasers == 5


def _make_followup_agent(
    alternative_titles: list[str] | None = None,
    followup_topics: list[str] | None = None,
    used_fact_ids: list[int] | None = None,
    used_quote_ids: list[int] | None = None,
):
    from agents.followup.agent import FollowUpOutput

    return Agent(
        TestModel(
            custom_output_args={
                "alternative_titles": alternative_titles
                or [
                    "Dawid Podsiadło: miliony na koncie",
                    "Wielki sukces Podsiadły",
                    "Trasa roku zakończona",
                ],
                "followup_topics": followup_topics
                or [
                    "Dawid Podsiadło dyskografia",
                    "Polscy artyści vs zagranica",
                ],
                "used_fact_ids": used_fact_ids if used_fact_ids is not None else [1],
                "used_quote_ids": used_quote_ids if used_quote_ids is not None else [1],
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
        domain=_DOMAIN,
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
        domain=_DOMAIN,
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
        domain=_DOMAIN,
        _agent=_make_followup_agent(),
    )
    assert result.html == "<h1>Dawid zarobił miliony</h1><p>Treść artykułu.</p>"


@pytest.mark.asyncio
async def test_followup_maps_fact_ids_to_source_strings():
    """LLM returns IDs; agent maps them back to canonical source-text strings."""
    result = await run_followup_agent(
        _ARTICLE,
        topic="topic",
        extraction_result=_EXTRACTION,
        config=_CONFIG,
        domain=_DOMAIN,
        _agent=_make_followup_agent(used_fact_ids=[1, 2], used_quote_ids=[1]),
    )
    # IDs map back to the exact source-text strings — no drift, no bullet
    # prefixes, no whitespace mismatches.
    assert result.used_facts == ["Zarobił 2 mln zł", "Sprzedał 50 tys. biletów"]
    assert result.used_quotes == ["To był najpiękniejszy rok"]


@pytest.mark.asyncio
async def test_followup_drops_out_of_range_and_duplicate_ids():
    """Hallucinated/duplicate IDs are silently filtered."""
    result = await run_followup_agent(
        _ARTICLE,
        topic="topic",
        extraction_result=_EXTRACTION,
        config=_CONFIG,
        domain=_DOMAIN,
        _agent=_make_followup_agent(
            used_fact_ids=[1, 1, 99, 0, 2],  # duplicate 1, out-of-range 99 and 0
            used_quote_ids=[5, 1],  # out-of-range 5
        ),
    )
    assert result.used_facts == ["Zarobił 2 mln zł", "Sprzedał 50 tys. biletów"]
    assert result.used_quotes == ["To był najpiękniejszy rok"]
