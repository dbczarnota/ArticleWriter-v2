"""Tests for the reflection→writer loop mechanics in run_pipeline."""
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

_DOMAIN = DomainConfig(name="test", description="T", language="pl", guidelines="g")
_SEARCH = [SearchResult(url="https://e.com/1", title="T", snippet="s", source="web")]
_SCRAPED = [ScrapedPage(url="https://e.com/1", title="T", content="c", scrape_tier="httpx")]
_ARTICLES = [ParsedArticle(url="https://e.com/1", title="T", content="c", publication_date=None)]
_EXTRACTION = ExtractionResult(facts=[Fact("F", "c", "https://e.com/1", "T")], quotes=[], keywords=[])
_BRIEF = WritingBrief(selected_facts=["F [c]"], selected_quotes=[], writing_instructions="Short.")
_DRAFT = ArticleHtml(html="<h1>Draft</h1>")
_REVISED = ArticleHtml(html="<h1>Revised</h1>")
_FEEDBACK = ReflectionFeedback(feedback="Add more emotion.", priority_fixes=["Fix lead"])
_OUTPUT = ArticleOutput(
    html="<h1>Revised</h1>", alternative_titles=["Alt"], followup_topics=["F"],
    used_facts=[], used_quotes=[], sources=["https://e.com/1"],
)
_EMBED = EmbedCandidate(url="https://youtube.com/watch?v=1", title="V", source="youtube")


@pytest.fixture
def patched_pipeline():
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
        m_search.return_value = _SEARCH
        m_scrape.return_value = (_SCRAPED, [])
        m_parse.return_value = _ARTICLES
        m_extract.return_value = _EXTRACTION
        m_adaptive.return_value = AdaptiveSearchDecision(needs_more_research=False)
        m_instr.return_value = _BRIEF
        m_writer.side_effect = [(_DRAFT, []), (_REVISED, [])]
        m_reflect.return_value = _FEEDBACK
        m_followup.return_value = _OUTPUT
        m_serper.return_value = []
        m_media.return_value = ([_EMBED], {})
        yield {
            "writer": m_writer,
            "reflect": m_reflect,
            "followup": m_followup,
        }


@pytest.mark.asyncio
async def test_reflection_enabled_calls_writer_twice(patched_pipeline):
    """With reflection=True and max_rounds=1, writer is called twice: draft + revision."""
    from agents.pipeline.runner import run_pipeline
    settings = AppSettings(pipeline=PipelineFlags(adaptive_search=False, reflection=True, followup=True))
    await run_pipeline("topic", settings=settings, domain=_DOMAIN, serper_api_key="k")
    assert patched_pipeline["writer"].call_count == 2
    patched_pipeline["reflect"].assert_called_once()


@pytest.mark.asyncio
async def test_reflection_disabled_calls_writer_once(patched_pipeline):
    """With reflection=False, writer is called exactly once and reflection agent is skipped."""
    from agents.pipeline.runner import run_pipeline
    patched_pipeline["writer"].side_effect = [(_DRAFT, [])]
    settings = AppSettings(pipeline=PipelineFlags(adaptive_search=False, reflection=False, followup=True))
    await run_pipeline("topic", settings=settings, domain=_DOMAIN, serper_api_key="k")
    assert patched_pipeline["writer"].call_count == 1
    patched_pipeline["reflect"].assert_not_called()


@pytest.mark.asyncio
async def test_reflection_output_used_in_final_article(patched_pipeline):
    """The final ArticleOutput.html must come from the revised draft, not the first draft."""
    from agents.pipeline.runner import run_pipeline
    settings = AppSettings(pipeline=PipelineFlags(adaptive_search=False, reflection=True, followup=False))
    patched_pipeline["writer"].side_effect = [(_DRAFT, []), (_REVISED, [])]
    result = await run_pipeline("topic", settings=settings, domain=_DOMAIN, serper_api_key="k")
    assert result.html == _REVISED.html
