# tests/agents/pipeline/test_runner.py
from unittest.mock import AsyncMock, patch

import pytest

from agents._base.types import (
    ArticleOutput,
    EmbedCandidate,
    Fact,
    ParsedArticle,
    Quote,
    ScrapedPage,
    SearchResult,
)
from agents.adaptive_search.agent import AdaptiveSearchDecision
from agents.extraction.agent import ExtractionResult
from agents.instructions.agent import WritingBrief
from agents.reflection.agent import ReflectionFeedback
from agents.writer.agent import ArticleHtml
from backend.config import AppSettings, PipelineFlags
from backend.domain import DomainConfig

_DOMAIN = DomainConfig(
    name="test",
    description="Test",
    language="pl",
    guidelines="Test guidelines",
)

_SEARCH_RESULTS = [SearchResult(url="https://e.com/1", title="T1", snippet="S1", source="web")]
_SCRAPED = [ScrapedPage(url="https://e.com/1", title="T1", content="Content", scrape_tier="httpx")]
_ARTICLES = [
    ParsedArticle(url="https://e.com/1", title="T1", content="Content", publication_date=None)
]
_EXTRACTION = ExtractionResult(
    facts=[Fact("Fakt 1", "ctx", source_urls=["https://e.com/1"])],
    quotes=[Quote("Cytat 1", "Ktoś", "ctx", source_urls=["https://e.com/1"])],
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
    # Scraping / parsing / extraction are called from both the main flow
    # (runner.py) AND the adaptive_search loop (_adaptive_search.py). We
    # patch BOTH bindings to the SAME AsyncMock so call_count totals across
    # both call sites — that's what the assertions in this file expect.
    m_scrape = AsyncMock()
    m_parse = AsyncMock()
    m_extract = AsyncMock()
    with (
        patch("agents.pipeline.runner.run_search_agent", new_callable=AsyncMock) as m_search,
        patch("agents.pipeline.runner.run_scraping_agent", new=m_scrape),
        patch("agents.pipeline._adaptive_search.run_scraping_agent", new=m_scrape),
        patch("agents.pipeline.runner.run_parsing_agent", new=m_parse),
        patch("agents.pipeline._adaptive_search.run_parsing_agent", new=m_parse),
        patch("agents.pipeline.runner.run_extraction_agent", new=m_extract),
        patch("agents.pipeline._adaptive_search.run_extraction_agent", new=m_extract),
        patch(
            "agents.pipeline._adaptive_search.run_adaptive_search_agent", new_callable=AsyncMock
        ) as m_adaptive,
        patch("agents.pipeline.runner.run_instructions_agent", new_callable=AsyncMock) as m_instr,
        patch("agents.pipeline.runner.run_writer_agent", new_callable=AsyncMock) as m_writer,
        patch("agents.pipeline.runner.run_reflection_agent", new_callable=AsyncMock) as m_reflect,
        patch("agents.pipeline.runner.run_followup_agent", new_callable=AsyncMock) as m_followup,
        patch("agents.pipeline._adaptive_search.serper_search", new_callable=AsyncMock) as m_serper,
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
        m_media.return_value = ([_EMBED], {})
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

    settings = AppSettings(
        pipeline=PipelineFlags(adaptive_search=False, reflection=True, followup=True)
    )
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

    settings = AppSettings(
        pipeline=PipelineFlags(adaptive_search=False, reflection=True, followup=True)
    )
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

    settings = AppSettings(
        pipeline=PipelineFlags(adaptive_search=False, reflection=False, followup=True)
    )
    await run_pipeline("topic", settings=settings, domain=_DOMAIN, serper_api_key="k")
    mocked_agents["reflection"].assert_not_called()
    assert mocked_agents["writer"].call_count == 1  # only draft, no revision


@pytest.mark.asyncio
async def test_pipeline_skips_followup_returns_minimal_output(mocked_agents):
    from agents.pipeline.runner import run_pipeline

    settings = AppSettings(
        pipeline=PipelineFlags(adaptive_search=False, reflection=False, followup=False)
    )
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
        facts=[Fact("Extra fakt", "ctx", source_urls=["https://e.com/2"])],
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

    settings = AppSettings(
        pipeline=PipelineFlags(adaptive_search=True, reflection=False, followup=False)
    )
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

    settings = AppSettings(
        pipeline=PipelineFlags(adaptive_search=True, reflection=False, followup=False)
    )
    await run_pipeline("topic", settings=settings, domain=_DOMAIN, serper_api_key="k")
    mocked_agents["serper"].assert_not_called()
    mocked_agents["extraction"].assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_adaptive_respects_max_rounds(mocked_agents):
    """max_additional_rounds=1: only one extra round even if more could be done."""
    import dataclasses

    from agents._base.config import AdaptiveSearchAgentConfig
    from agents.pipeline.runner import run_pipeline

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
        adaptive_search_agent=dataclasses.replace(
            AdaptiveSearchAgentConfig(), max_additional_rounds=1
        ),
        pipeline=PipelineFlags(adaptive_search=True, reflection=False, followup=False),
    )
    await run_pipeline("topic", settings=settings, domain=_DOMAIN, serper_api_key="k")
    assert mocked_agents["adaptive"].call_count == 1
    assert mocked_agents["extraction"].call_count == 2


@pytest.mark.asyncio
async def test_pipeline_passes_embed_candidates_to_output(mocked_agents):
    from agents.pipeline.runner import run_pipeline

    settings = AppSettings(
        pipeline=PipelineFlags(adaptive_search=False, reflection=False, followup=False)
    )
    result = await run_pipeline("topic", settings=settings, domain=_DOMAIN, serper_api_key="k")
    assert len(result.embed_candidates) == 1
    assert result.embed_candidates[0].source == "youtube"


@pytest.mark.asyncio
async def test_pipeline_output_has_timing(mocked_agents):
    from agents.pipeline.runner import run_pipeline

    settings = AppSettings(
        pipeline=PipelineFlags(adaptive_search=False, reflection=False, followup=False)
    )
    result = await run_pipeline(
        "Dawid Podsiadło",
        settings=settings,
        domain=_DOMAIN,
        serper_api_key="key",
    )
    assert isinstance(result.timing, dict)
    assert "research" in result.timing
    assert result.timing["research"] >= 0.0


@pytest.mark.asyncio
async def test_pipeline_output_has_token_usage(mocked_agents):
    from agents.pipeline.runner import run_pipeline

    settings = AppSettings(
        pipeline=PipelineFlags(adaptive_search=False, reflection=False, followup=False)
    )
    result = await run_pipeline(
        "Dawid Podsiadło",
        settings=settings,
        domain=_DOMAIN,
        serper_api_key="key",
    )
    assert isinstance(result.token_usage, list)


def test_merge_extraction_deduplicates_by_text():
    from agents.pipeline._helpers import merge_extraction

    base = ExtractionResult(
        facts=[Fact("Fakt A", "ctx", source_urls=["https://a.com"])],
        quotes=[Quote("Cytat A", "Ktoś", "ctx", source_urls=["https://a.com"])],
        keywords=["kw1"],
    )
    extra = ExtractionResult(
        facts=[
            # Duplicate by text but with a DIFFERENT source — merge_extraction
            # should union the source_urls instead of dropping the entry.
            Fact("Fakt A", "ctx", source_urls=["https://a-mirror.com"]),
            Fact("Fakt B", "ctx", source_urls=["https://b.com"]),
        ],
        quotes=[Quote("Cytat B", "Ktoś B", "ctx", source_urls=["https://b.com"])],
        keywords=["kw1", "kw2"],
    )
    merged = merge_extraction(base, extra)
    assert len(merged.facts) == 2  # A + B, A merged not duplicated
    fact_a = next(f for f in merged.facts if f.text == "Fakt A")
    assert sorted(fact_a.source_urls) == ["https://a-mirror.com", "https://a.com"]
    assert len(merged.quotes) == 2
    assert merged.keywords == ["kw1", "kw2"]


@pytest.mark.asyncio
async def test_pipeline_applies_domain_num_queries(mocked_agents):
    """domain.default_num_queries overrides the SearchAgentConfig default when domain differs."""
    from agents.pipeline.runner import run_pipeline

    domain = DomainConfig(
        name="test_q",
        description="Test",
        language="pl",
        guidelines="g",
        default_num_queries=7,
        default_max_results=12,
    )
    settings = AppSettings(
        pipeline=PipelineFlags(adaptive_search=False, reflection=False, followup=False)
    )
    await run_pipeline("topic", settings=settings, domain=domain, serper_api_key="k")
    call_kwargs = mocked_agents["search"].call_args
    cfg_passed = call_kwargs.kwargs.get("config") or call_kwargs.args[1]
    assert cfg_passed.num_queries == 7
    assert cfg_passed.max_results == 12
