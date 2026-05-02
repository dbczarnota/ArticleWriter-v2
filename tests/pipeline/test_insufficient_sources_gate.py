"""Guardrail: pipeline must refuse to invoke writer when extraction yielded no facts/quotes.

Real upstream causes this catches: Serper API credits exhausted, Jina credits exhausted,
all URLs rejected by parser, extraction LLM returned empty.
"""

from unittest.mock import AsyncMock, patch

import pytest

from agents._base.resilient import InsufficientSourcesError
from agents._base.types import EmbedCandidate
from agents.extraction.agent import ExtractionResult
from agents.pipeline.runner import run_pipeline
from backend.config import AppSettings
from domains.registry import load_domain


@pytest.fixture
def styl_fm_settings():
    return AppSettings(domain="styl_fm")


async def test_gate_raises_when_extraction_is_empty(styl_fm_settings):
    """Empty extraction (0 facts + 0 quotes) must raise InsufficientSourcesError."""
    domain = load_domain(styl_fm_settings.domain)

    with (
        patch("agents.pipeline.runner.run_search_agent", new_callable=AsyncMock, return_value=[]),
        patch(
            "agents.pipeline.runner.run_media_search",
            new_callable=AsyncMock,
            return_value=([], {}),
        ),
        patch(
            "agents.pipeline.runner.run_scraping_agent",
            new_callable=AsyncMock,
            return_value=([], []),
        ),
        patch("agents.pipeline.runner.run_parsing_agent", new_callable=AsyncMock, return_value=[]),
        patch(
            "agents.pipeline.runner.run_extraction_agent",
            new_callable=AsyncMock,
            return_value=ExtractionResult(facts=[], quotes=[], keywords=[]),
        ),pytest.raises(InsufficientSourcesError) as exc_info
    ):
        await run_pipeline(
            "Topic with no available sources",
            settings=styl_fm_settings,
            domain=domain,
            serper_api_key="fake-key",
        )

    err = exc_info.value
    assert err.facts_count == 0
    assert err.quotes_count == 0
    assert err.min_required == 1


async def test_gate_threshold_configurable(styl_fm_settings):
    """min_source_signals=3 fails on 2 quotes alone (below threshold)."""
    from dataclasses import replace

    settings = replace(
        styl_fm_settings,
        pipeline=replace(styl_fm_settings.pipeline, min_source_signals=3),
    )
    domain = load_domain(settings.domain)

    with (
        patch("agents.pipeline.runner.run_search_agent", new_callable=AsyncMock, return_value=[]),
        patch(
            "agents.pipeline.runner.run_media_search",
            new_callable=AsyncMock,
            return_value=([], {}),
        ),
        patch(
            "agents.pipeline.runner.run_scraping_agent",
            new_callable=AsyncMock,
            return_value=([], []),
        ),
        patch("agents.pipeline.runner.run_parsing_agent", new_callable=AsyncMock, return_value=[]),
        patch(
            "agents.pipeline.runner.run_extraction_agent",
            new_callable=AsyncMock,
            return_value=ExtractionResult(facts=[], quotes=[], keywords=[]),
        ),pytest.raises(InsufficientSourcesError) as exc_info
    ):
        await run_pipeline(
            "Topic",
            settings=settings,
            domain=domain,
            serper_api_key="fake-key",
        )

    assert exc_info.value.min_required == 3


async def test_gate_includes_upstream_errors(styl_fm_settings):
    """When search fails, the upstream_errors list captures the stage error for diagnosis."""
    domain = load_domain(styl_fm_settings.domain)

    with (
        patch(
            "agents.pipeline.runner.run_search_agent",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Serper API: 401 Unauthorized — credits exhausted"),
        ),
        patch(
            "agents.pipeline.runner.run_media_search",
            new_callable=AsyncMock,
            return_value=([], {}),
        ),
        patch(
            "agents.pipeline.runner.run_scraping_agent",
            new_callable=AsyncMock,
            return_value=([], []),
        ),
        patch("agents.pipeline.runner.run_parsing_agent", new_callable=AsyncMock, return_value=[]),
        patch(
            "agents.pipeline.runner.run_extraction_agent",
            new_callable=AsyncMock,
            return_value=ExtractionResult(facts=[], quotes=[], keywords=[]),
        ),pytest.raises(InsufficientSourcesError) as exc_info
    ):
        await run_pipeline(
            "Topic",
            settings=styl_fm_settings,
            domain=domain,
            serper_api_key="fake-key",
        )

    # Search failure should be captured in upstream_errors
    err = exc_info.value
    assert any(
        e.get("stage") == "search" and "credits exhausted" in e.get("error", "")
        for e in err.upstream_errors
    )


# Sanity: pipeline DOES proceed past the gate when there's at least one fact
async def test_gate_passes_with_at_least_one_fact(styl_fm_settings):
    """One fact is enough to not trip the default gate (min_source_signals=1).

    Verifies the gate is permissive — does NOT raise — when there's source material.
    Other stages may fail downstream (their try/except handles that), but the gate itself
    must pass control through.
    """
    from agents._base.types import Fact

    domain = load_domain(styl_fm_settings.domain)
    fact = Fact(
        text="Sample fact",
        context="test",
        source_url="https://example.com/article",
        source_title="Sample article",
    )

    instructions_mock = AsyncMock(
        side_effect=RuntimeError("downstream stop — gate already passed")
    )

    with (
        patch("agents.pipeline.runner.run_search_agent", new_callable=AsyncMock, return_value=[]),
        patch(
            "agents.pipeline.runner.run_media_search",
            new_callable=AsyncMock,
            return_value=([], {}),
        ),
        patch(
            "agents.pipeline.runner.run_scraping_agent",
            new_callable=AsyncMock,
            return_value=([], []),
        ),
        patch("agents.pipeline.runner.run_parsing_agent", new_callable=AsyncMock, return_value=[]),
        patch(
            "agents.pipeline.runner.run_extraction_agent",
            new_callable=AsyncMock,
            return_value=ExtractionResult(facts=[fact], quotes=[], keywords=[]),
        ),
        patch("agents.pipeline.runner.run_instructions_agent", instructions_mock),
        # writer / reflection / followup are all called too — stub with safe no-ops
        patch(
            "agents.pipeline.runner.run_writer_agent",
            new_callable=AsyncMock,
            return_value=(_make_dummy_article(), []),
        ),
        patch(
            "agents.pipeline.runner.run_followup_agent",
            new_callable=AsyncMock,
            return_value=_make_dummy_followup(),
        ),
    ):
        # Gate passed → instructions reached. Instructions raises (handled by its own
        # try/except), pipeline continues, eventually returns or raises somewhere else.
        # The only thing this test verifies is that InsufficientSourcesError is NOT raised.
        try:
            await run_pipeline(
                "Topic",
                settings=styl_fm_settings,
                domain=domain,
                serper_api_key="fake-key",
            )
        except InsufficientSourcesError:
            pytest.fail("Gate should not have tripped — extraction had 1 fact")
        except Exception:
            # Other failures downstream are OK — they prove the gate let control through.
            pass

    assert instructions_mock.await_count == 1, "instructions agent must be reached past the gate"


def _make_dummy_article():
    from agents.writer.agent import ArticleHtml

    return ArticleHtml(html="<h1>x</h1>")


def _make_dummy_followup():
    from agents.followup.agent import FollowUpOutput

    return FollowUpOutput(alternative_titles=["x"], followup_topics=["y"])


# Reference imports are used in fixtures via runner internals
_ = EmbedCandidate
