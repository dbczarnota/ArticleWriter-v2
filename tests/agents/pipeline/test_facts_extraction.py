"""Unit tests for extract_facts_from_text helper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents._base.config import ExtractionAgentConfig
from agents.extraction.agent import ExtractionResult
from agents.pipeline._helpers import extract_facts_from_text


@pytest.mark.asyncio
async def test_extract_facts_returns_extraction_result():
    """extract_facts_from_text returns an ExtractionResult with editor-provided source_urls."""
    mock_output = MagicMock()
    mock_output.facts = [MagicMock(text="Anna zdobyła nagrodę", context="ceremonial", source_urls=[])]
    mock_output.quotes = [MagicMock(text="Jestem szczęśliwa", speaker="Anna", context="wywiad", source_urls=[])]
    mock_output.keywords = ["nagroda"]

    mock_result = MagicMock()
    mock_result.output = mock_output
    mock_result.usage.return_value = MagicMock(input_tokens=10, output_tokens=5)

    with patch("agents.pipeline._helpers.run_with_fallback", new_callable=AsyncMock) as mock_rwf:
        mock_rwf.return_value = (mock_result, "google-gla:gemini-flash-latest")
        with patch("agents.pipeline._helpers.record_agent_call"):
            result = await extract_facts_from_text(
                raw_text="Anna zdobyła nagrodę. 'Jestem szczęśliwa' — Anna.",
                topic="Anna Mucha",
                language="pl",
                config=ExtractionAgentConfig(),
            )

    assert isinstance(result, ExtractionResult)
    assert result.facts[0].text == "Anna zdobyła nagrodę"
    assert result.facts[0].source_urls == ["editor-provided"]
    assert result.quotes[0].source_urls == ["editor-provided"]
    assert result.keywords == ["nagroda"]


@pytest.mark.asyncio
async def test_extract_facts_soft_fails_on_llm_error():
    """LLM failure returns empty ExtractionResult instead of raising."""
    with patch("agents.pipeline._helpers.run_with_fallback", new_callable=AsyncMock) as mock_rwf:
        mock_rwf.side_effect = Exception("LLM unavailable")
        with patch("agents.pipeline._helpers.record_agent_call"):
            result = await extract_facts_from_text(
                raw_text="some text",
                topic="topic",
                language="pl",
                config=ExtractionAgentConfig(),
            )

    assert result == ExtractionResult(facts=[], quotes=[], keywords=[])
