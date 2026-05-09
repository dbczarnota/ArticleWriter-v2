from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.stream_digest.agent import ChunkSummary, DigestStory, StreamDigestResult
from agents.stream_digest.config import StreamDigestAgentConfig


def test_config_defaults():
    cfg = StreamDigestAgentConfig()
    assert cfg.model == "google-gla:gemini-flash-latest"
    assert len(cfg.fallback_models) >= 1
    assert cfg.chunks_per_digest == 5


def test_config_is_frozen():
    cfg = StreamDigestAgentConfig()
    with pytest.raises(AttributeError):
        cfg.model = "other"  # type: ignore[misc]


def _make_chunk(start: float = 0.0, end: float = 120.0) -> ChunkSummary:
    return ChunkSummary(
        chunk_start=start,
        chunk_end=end,
        raw_transcript="Presenter mówi o gospodarce.",
        speakers=[{"label": "A", "description": "prezenter"}],
        topics=[{"title": "Gospodarka", "confidence": 0.9}],
        facts=[{"text": "PKB wzrósł o 3%", "speaker_label": "A"}],
        quotes=[{"text": "Wzrost jest imponujący.", "speaker_label": "A"}],
    )


@pytest.mark.asyncio
async def test_run_stream_digest_agent_empty_input():
    from agents.stream_digest.agent import run_stream_digest_agent

    result = await run_stream_digest_agent([], config=StreamDigestAgentConfig())
    assert isinstance(result, StreamDigestResult)
    assert result.stories == []


@pytest.mark.asyncio
async def test_run_stream_digest_agent_returns_result():
    from agents.stream_digest.agent import run_stream_digest_agent

    chunks = [_make_chunk(0.0, 120.0), _make_chunk(120.0, 240.0)]

    mock_result = MagicMock()
    mock_result.output = StreamDigestResult(
        stories=[
            DigestStory(
                title="Gospodarka polska",
                start_seconds=0.0,
                end_seconds=240.0,
                summary="PKB wzrósł o 3% według prezenterów.",
            )
        ],
        window_start_seconds=0.0,
        window_end_seconds=240.0,
    )
    mock_result.usage.return_value = MagicMock(input_tokens=200, output_tokens=80)

    with patch(
        "agents.stream_digest.agent.run_with_fallback",
        new=AsyncMock(return_value=(mock_result, "google-gla:gemini-flash-latest")),
    ):
        result = await run_stream_digest_agent(chunks, config=StreamDigestAgentConfig())

    assert len(result.stories) == 1
    assert result.stories[0].title == "Gospodarka polska"
    assert result.window_start_seconds == 0.0
    assert result.window_end_seconds == 240.0


@pytest.mark.asyncio
async def test_run_stream_digest_agent_soft_fails():
    from agents.stream_digest.agent import run_stream_digest_agent

    chunks = [_make_chunk(0.0, 120.0)]

    with patch(
        "agents.stream_digest.agent.run_with_fallback",
        new=AsyncMock(side_effect=RuntimeError("LLM unavailable")),
    ):
        result = await run_stream_digest_agent(chunks, config=StreamDigestAgentConfig())

    assert isinstance(result, StreamDigestResult)
    assert result.stories == []
    assert result.window_start_seconds == 0.0
    assert result.window_end_seconds == 120.0
