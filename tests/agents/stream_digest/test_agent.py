from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.stream_digest.agent import (
    ChunkSummary,
    DigestStory,
    StreamDigestResult,
    TopicContext,
    _format_historical_topics,
)
from agents.stream_digest.config import StreamDigestAgentConfig


def test_config_defaults():
    cfg = StreamDigestAgentConfig()
    assert cfg.model == "google-gla:gemini-flash-latest"
    assert len(cfg.fallback_models) >= 1
    assert cfg.chunks_per_digest == 5
    assert cfg.previous_digests_count == 2
    assert cfg.topic_window_hours == 6


def test_config_is_frozen():
    cfg = StreamDigestAgentConfig()
    with pytest.raises(AttributeError):
        cfg.model = "other"  # type: ignore[misc]


def _make_chunk(start: float = 0.0, end: float = 120.0) -> ChunkSummary:
    return ChunkSummary(
        chunk_start=start,
        chunk_end=end,
        raw_transcript="Presenter mowi o gospodarce.",
        speakers=[{"label": "A", "description": "prezenter"}],
        topics=[{
            "title": "Gospodarka",
            "confidence": 0.9,
            "start_offset_seconds": 0.0,
            "end_offset_seconds": None,
            "facts": [{"text": "PKB wzrosl o 3%", "speaker_label": "A", "timestamp_offset_seconds": 10.0}],
            "quotes": [{"text": "Wzrost jest imponujacy.", "speaker_label": "A"}],
        }],
    )


def _make_topic_context(
    title: str = "Test topic",
    is_news: bool = True,
    minutes_ago: int = 30,
    now: datetime | None = None,
) -> TopicContext:
    now = now or datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
    from datetime import timedelta
    last_seen = now - timedelta(minutes=minutes_ago)
    return TopicContext(
        title=title,
        is_news=is_news,
        summary="Test summary.",
        first_seen_at=last_seen,
        last_seen_at=last_seen,
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
                summary="PKB wzrosl o 3%.",
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


@pytest.mark.asyncio
async def test_run_stream_digest_agent_passes_historical_topics_in_prompt():
    from agents.stream_digest.agent import run_stream_digest_agent

    chunks = [_make_chunk(0.0, 120.0)]
    now = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
    topics = [
        _make_topic_context("Wybory prezydenckie", is_news=True, minutes_ago=45, now=now),
        _make_topic_context("Koncert Chopina", is_news=False, minutes_ago=120, now=now),
    ]

    mock_result = MagicMock()
    mock_result.output = StreamDigestResult()
    mock_result.usage.return_value = MagicMock(input_tokens=100, output_tokens=50)

    captured_prompt: list[str] = []

    async def _fake_fallback(*args, **kwargs):
        captured_prompt.append(kwargs.get("user_prompt", ""))
        return (mock_result, "google-gla:gemini-flash-latest")

    with patch("agents.stream_digest.agent.run_with_fallback", new=_fake_fallback):
        await run_stream_digest_agent(
            chunks,
            config=StreamDigestAgentConfig(),
            historical_topics=topics,
            now_utc=now,
        )

    assert captured_prompt, "run_with_fallback was not called"
    prompt = captured_prompt[0]
    assert "TEMATY Z OSTATNICH 6H" in prompt
    assert "Wybory prezydenckie" in prompt
    assert "[NEWS]" in prompt
    assert "[ -- ]" in prompt
    assert "2026-05-10 12:00 UTC" in prompt


def test_format_historical_topics_empty():
    now = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
    result = _format_historical_topics([], now)
    assert "brak" in result


def test_format_historical_topics_formats_age():
    now = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
    topics = [_make_topic_context("Temat A", is_news=True, minutes_ago=90, now=now)]
    result = _format_historical_topics(topics, now)
    assert "[NEWS]" in result
    assert "Temat A" in result
    assert "90 min" in result
    assert "10:30" in result  # 12:00 - 90min = 10:30
