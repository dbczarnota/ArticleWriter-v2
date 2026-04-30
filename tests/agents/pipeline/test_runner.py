# tests/agents/pipeline/test_runner.py
import pytest
from unittest.mock import AsyncMock, patch
from agents._base.types import (
    ArticleOutput, EmbedCandidate, Fact, Quote, SearchResult, ScrapedPage, ParsedArticle,
)
from agents.extraction.agent import ExtractionResult
from agents.adaptive_search.agent import AdaptiveSearchDecision
from agents.instructions.agent import WritingBrief
from agents.reflection.agent import ReflectionFeedback
from agents.writer.agent import ArticleHtml
from backend.config import AppSettings, PipelineFlags
from domains._base.config import DomainConfig


_DOMAIN = DomainConfig(
    name="test",
    description="Test",
    language="pl",
    guidelines="Test guidelines",
)

_SEARCH_RESULTS = [SearchResult(url="https://e.com/1", title="T1", snippet="S1", source="web")]
_SCRAPED = [ScrapedPage(url="https://e.com/1", title="T1", content="Content", scrape_tier="httpx")]
_ARTICLES = [ParsedArticle(url="https://e.com/1", title="T1", content="Content", publication_date=None)]
_EXTRACTION = ExtractionResult(
    facts=[Fact("Fakt 1", "ctx", "https://e.com/1", "T1")],
    quotes=[Quote("Cytat 1", "Ktoś", "ctx", "https://e.com/1")],
    keywords=["kw1"],
)
_BRIEF = WritingBrief(
    selected_facts=["Fakt 1 [ctx]"],
    selected_quotes=['"Cytat 1" — Ktoś'],
    writing_instructions="Pisz krótko.",
)
_ARTICLE_HTML = ArticleHtml(html="<h1>Test</h1><p>Treść</p>")
_REFLECTION = ReflectionFeedback(feedback="Dodaj emocje.", priority_fixes=["Fix 1"])
_ARTICLE_OUTPUT = ArticleOutput(
    html="<h1>Test</h1><p>Treść</p>",
    alternative_titles=["Tytuł alt"],
    followup_topics=["Temat 1"],
    used_facts=["Fakt 1"],
    used_quotes=["Cytat 1"],
    sources=["https://e.com/1"],
)
_EMBED = EmbedCandidate(url="https://youtube.com/watch?v=1", title="YT Video", source="youtube")


@pytest.fixture
def mocked_agents():
    with (
        patch("agents.pipeline.runner.run_search_agent", new_callable=AsyncMock) as m_search,
        patch("agents.pipeline.runner.run_scraping_agent", new_callable=AsyncMock) as m_scrape,
        patch("agents.pipeline.runner.run_parsing_agent", new_callable=AsyncMock) as m_parse,
        patch("agents.pipeline.runner.run_extraction_agent", new_callable=AsyncMock) as m_extract,
        patch("agents.pipeline.runner.run_adaptive_search_agent", new_callable=AsyncMock) as m_adaptive,
        patch("agents.pipeline.runner.run_instructions_agent", new_callable=AsyncMock) as m_instr,
        patch("agents.pipeline.runner.run_writer_agent", new_callable=AsyncMock) as m_writer,
        patch("agents.pipeline.runner.run_reflection_agent", new_callable=AsyncMock) as m_reflect,
        patch("agents.pipeline.runner.run_followup_agent", new_callable=AsyncMock) as m_followup,
        patch("agents.pipeline.runner.serper_search", new_callable=AsyncMock) as m_serper,
        patch("agents.pipeline.runner.run_media_search", new_callable=AsyncMock) as m_media,
    ):
        m_search.return_value = _SEARCH_RESULTS
        m_scrape.return_value = (_SCRAPED, [])
        m_parse.return_value = _ARTICLES
        m_extract.return_value = _EXTRACTION
        m_adaptive.return_value = AdaptiveSearchDecision(needs_more_research=False)
        m_instr.return_value = _BRIEF
        m_writer.return_value = (_ARTICLE_HTML, [])
        m_reflect.return_value = _REFLECTION
        m_followup.return_value = _ARTICLE_OUTPUT
        m_serper.return_value = []
        m_media.return_value = [_EMBED]
        yield {
            "search": m_search,
            "scraping": m_scrape,
            "parsing": m_parse,
            "extraction": m_extract,
            "adaptive": m_adaptive,
            "instructions": m_instr,
            "writer": m_writer,
            "reflection": m_reflect,
            "followup": m_followup,
            "serper": m_serper,
            "media": m_media,
        }


@pytest.mark.asyncio
async def test_full_pipeline_returns_article_output(mocked_agents):
    from agents.pipeline.runner import run_pipeline

    settings = AppSettings(pipeline=PipelineFlags(adaptive_search=False, reflection=True, followup=True))
    result = await run_pipeline(
        "Dawid Podsiadło",
        settings=settings,
        domain=_DOMAIN,
        serper_api_key="test-key",
    )
    assert isinstance(result, ArticleOutput)
    assert result.html == _ARTICLE_HTML.html


@pytest.mark.asyncio
async def test_pipeline_calls_all_stages(mocked_agents):
    from agents.pipeline.runner import run_pipeline

    settings = AppSettings(pipeline=PipelineFlags(adaptive_search=False, reflection=True, followup=True))
    await run_pipeline("topic", settings=settings, domain=_DOMAIN, serper_api_key="k")
    mocked_agents["search"].assert_called_once()
    mocked_agents["scraping"].assert_called_once()
    mocked_agents["parsing"].assert_called_once()
    mocked_agents["extraction"].assert_called_once()
    mocked_agents["instructions"].assert_called_once()
    assert mocked_agents["writer"].call_count == 2  # draft + revision
    mocked_agents["reflection"].assert_called_once()
    mocked_agents["followup"].assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_skips_reflection(mocked_agents):
    from agents.pipeline.runner import run_pipeline

    settings = AppSettings(pipeline=PipelineFlags(adaptive_search=False, reflection=False, followup=True))
    await run_pipeline("topic", settings=settings, domain=_DOMAIN, serper_api_key="k")
    mocked_agents["reflection"].assert_not_called()
    assert mocked_agents["writer"].call_count == 1  # only draft, no revision


@pytest.mark.asyncio
async def test_pipeline_skips_followup_returns_minimal_output(mocked_agents):
    from agents.pipeline.runner import run_pipeline

    settings = AppSettings(pipeline=PipelineFlags(adaptive_search=False, reflection=False, followup=False))
    result = await run_pipeline("topic", settings=settings, domain=_DOMAIN, serper_api_key="k")
    mocked_agents["followup"].assert_not_called()
    assert isinstance(result, ArticleOutput)
    assert result.html == _ARTICLE_HTML.html
    assert result.alternative_titles == []
    assert result.followup_topics == []
    assert "https://e.com/1" in result.sources


@pytest.mark.asyncio
async def test_pipeline_runs_extra_search_round(mocked_agents):
    """When adaptive agent says needs_more_research + has queries, runs one extra round."""
    from agents.pipeline.runner import run_pipeline

    extra_extraction = ExtractionResult(
        facts=[Fact("Extra fakt", "ctx", "https://e.com/2", "T2")],
        quotes=[],
        keywords=["kw2"],
    )
    mocked_agents["adaptive"].return_value = AdaptiveSearchDecision(
        needs_more_research=True,
        additional_queries=["Dawid Podsiadło zarobki 2025"],
    )
    mocked_agents["serper"].return_value = [
        SearchResult(url="https://e.com/2", title="T2", snippet="S2", source="web")
    ]
    mocked_agents["extraction"].side_effect = [_EXTRACTION, extra_extraction]
    mocked_agents["scraping"].return_value = (
        [ScrapedPage(url="https://e.com/2", title="T2", content="Extra", scrape_tier="httpx")],
        [],
    )
    mocked_agents["parsing"].return_value = [
        ParsedArticle(url="https://e.com/2", title="T2", content="Extra", publication_date=None)
    ]

    settings = AppSettings(pipeline=PipelineFlags(adaptive_search=True, reflection=False, followup=False))
    await run_pipeline("topic", settings=settings, domain=_DOMAIN, serper_api_key="k")
    assert mocked_agents["serper"].call_count == 1
    assert mocked_agents["extraction"].call_count == 2


@pytest.mark.asyncio
async def test_pipeline_adaptive_skips_when_no_queries(mocked_agents):
    """needs_more_research=True but additional_queries=[] → no extra search."""
    from agents.pipeline.runner import run_pipeline

    mocked_agents["adaptive"].return_value = AdaptiveSearchDecision(
        needs_more_research=True,
        additional_queries=[],
    )

    settings = AppSettings(pipeline=PipelineFlags(adaptive_search=True, reflection=False, followup=False))
    await run_pipeline("topic", settings=settings, domain=_DOMAIN, serper_api_key="k")
    mocked_agents["serper"].assert_not_called()
    mocked_agents["extraction"].assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_adaptive_respects_max_rounds(mocked_agents):
    """max_additional_rounds=1: only one extra round even if more could be done."""
    from agents.pipeline.runner import run_pipeline
    from agents._base.config import AdaptiveSearchAgentConfig
    import dataclasses

    mocked_agents["adaptive"].return_value = AdaptiveSearchDecision(
        needs_more_research=True,
        additional_queries=["extra query"],
    )
    mocked_agents["serper"].return_value = [
        SearchResult(url="https://e.com/extra", title="E", snippet="s", source="web")
    ]
    mocked_agents["extraction"].side_effect = [
        _EXTRACTION,
        ExtractionResult(facts=[], quotes=[], keywords=[]),
    ]

    settings = AppSettings(
        adaptive_search_agent=dataclasses.replace(AdaptiveSearchAgentConfig(), max_additional_rounds=1),
        pipeline=PipelineFlags(adaptive_search=True, reflection=False, followup=False),
    )
    await run_pipeline("topic", settings=settings, domain=_DOMAIN, serper_api_key="k")
    assert mocked_agents["adaptive"].call_count == 1
    assert mocked_agents["extraction"].call_count == 2


@pytest.mark.asyncio
async def test_pipeline_passes_embed_candidates_to_output(mocked_agents):
    from agents.pipeline.runner import run_pipeline

    settings = AppSettings(pipeline=PipelineFlags(adaptive_search=False, reflection=False, followup=False))
    result = await run_pipeline("topic", settings=settings, domain=_DOMAIN, serper_api_key="k")
    assert len(result.embed_candidates) == 1
    assert result.embed_candidates[0].source == "youtube"


def test_merge_extraction_deduplicates_by_text():
    from agents.pipeline.runner import _merge_extraction

    base = ExtractionResult(
        facts=[Fact("Fakt A", "ctx", "https://a.com", "A")],
        quotes=[Quote("Cytat A", "Ktoś", "ctx", "https://a.com")],
        keywords=["kw1"],
    )
    extra = ExtractionResult(
        facts=[
            Fact("Fakt A", "ctx", "https://a.com", "A"),  # duplicate
            Fact("Fakt B", "ctx", "https://b.com", "B"),  # new
        ],
        quotes=[Quote("Cytat B", "Ktoś B", "ctx", "https://b.com")],
        keywords=["kw1", "kw2"],
    )
    merged = _merge_extraction(base, extra)
    assert len(merged.facts) == 2  # A + B, not duplicate A
    assert len(merged.quotes) == 2
    assert merged.keywords == ["kw1", "kw2"]
