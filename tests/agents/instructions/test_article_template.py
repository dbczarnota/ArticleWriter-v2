"""Test that article_template is injected before additional_instructions in material."""

from unittest.mock import MagicMock, patch

import pytest

from agents._base.config import InstructionsAgentConfig
from agents.extraction.agent import ExtractionResult
from agents.instructions.agent import WritingBrief, run_instructions_agent
from backend.domain import DomainConfig


def _make_domain() -> DomainConfig:
    """Create a minimal DomainConfig for testing."""
    import dataclasses

    kwargs: dict = {}
    for f in dataclasses.fields(DomainConfig):
        if f.name not in kwargs:
            if f.default is not dataclasses.MISSING:
                kwargs[f.name] = f.default
            elif f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
                kwargs[f.name] = f.default_factory()
            else:
                # Fill string fields with empty string, int/float with 0, bool with False
                if f.type in (str, "str"):
                    kwargs[f.name] = ""
                elif f.type in (int, "int"):
                    kwargs[f.name] = 0
                elif f.type in (bool, "bool"):
                    kwargs[f.name] = False
                else:
                    kwargs[f.name] = None
    return DomainConfig(**kwargs)


@pytest.mark.asyncio
async def test_article_template_injected_before_additional_instructions():
    """TEMPLATE INSTRUCTIONS block appears before Additional Instructions block in material."""
    captured_prompt: dict = {}

    async def fake_run(material: str):
        captured_prompt["text"] = material
        mock = MagicMock()
        mock.output = WritingBrief(selected_facts=[], selected_quotes=[], writing_instructions="ok")
        mock.usage.return_value = MagicMock(input_tokens=1, output_tokens=1)
        return mock

    mock_agent = MagicMock()
    mock_agent.run = fake_run

    with patch("agents.instructions.agent.record_agent_call"):
        await run_instructions_agent(
            ExtractionResult(facts=[], quotes=[], keywords=[]),
            topic="Test",
            domain=_make_domain(),
            config=InstructionsAgentConfig(),
            additional_instructions="ADDITIONAL",
            article_template="TEMPLATE",
            _agent=mock_agent,
        )

    text = captured_prompt["text"]
    template_pos = text.find("TEMPLATE INSTRUCTIONS")
    additional_pos = text.find("Additional Instructions")
    assert template_pos != -1, "TEMPLATE INSTRUCTIONS block missing"
    assert additional_pos != -1, "Additional Instructions block missing"
    assert template_pos < additional_pos, "Template must appear before additional instructions"


@pytest.mark.asyncio
async def test_no_template_no_template_block():
    """When article_template is None, no TEMPLATE INSTRUCTIONS block is added."""
    captured_prompt: dict = {}

    async def fake_run(material: str):
        captured_prompt["text"] = material
        mock = MagicMock()
        mock.output = WritingBrief(selected_facts=[], selected_quotes=[], writing_instructions="ok")
        mock.usage.return_value = MagicMock(input_tokens=1, output_tokens=1)
        return mock

    mock_agent = MagicMock()
    mock_agent.run = fake_run

    with patch("agents.instructions.agent.record_agent_call"):
        await run_instructions_agent(
            ExtractionResult(facts=[], quotes=[], keywords=[]),
            topic="Test",
            domain=_make_domain(),
            config=InstructionsAgentConfig(),
            article_template=None,
            _agent=mock_agent,
        )

    assert "TEMPLATE INSTRUCTIONS" not in captured_prompt["text"]
