from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.stream_analysis.config import StreamAnalysisAgentConfig


def test_config_defaults():
    cfg = StreamAnalysisAgentConfig()
    assert cfg.model == "google-gla:gemini-flash-latest"
    assert len(cfg.fallback_models) >= 1
    assert cfg.chunk_duration_seconds == 30


def test_config_is_frozen():
    cfg = StreamAnalysisAgentConfig()
    with pytest.raises(Exception):  # FrozenInstanceError
        cfg.model = "other"  # type: ignore[misc]


@pytest.mark.asyncio
async def test_run_stream_analysis_agent_returns_result():
    from agents.stream_analysis.agent import StreamChunkResult, run_stream_analysis_agent
    from agents.stream_analysis.config import StreamAnalysisAgentConfig

    mock_result = MagicMock()
    mock_result.output = StreamChunkResult(
        speakers=[],
        topics=[],
        facts=[],
        quotes=[],
        raw_transcript="testowa transkrypcja",
    )
    mock_result.usage.return_value = MagicMock(input_tokens=100, output_tokens=50)

    with patch(
        "agents.stream_analysis.agent.run_with_fallback",
        new=AsyncMock(return_value=(mock_result, "google-gla:gemini-flash-latest")),
    ):
        result = await run_stream_analysis_agent(
            audio_bytes=b"fake_audio",
            chunk_start_seconds=0.0,
            config=StreamAnalysisAgentConfig(),
        )

    assert result.raw_transcript == "testowa transkrypcja"
    assert isinstance(result.topics, list)
    assert isinstance(result.facts, list)
    assert isinstance(result.quotes, list)
