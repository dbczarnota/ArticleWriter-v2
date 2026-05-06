from __future__ import annotations

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from agents._base.config import ExtractionAgentConfig
from agents.discovery.topic_writer.agent import (
    TopicDescriptor,
    run_topic_writer_agent,
)


def _make_writer_agent(title: str, blurb: str):
    return Agent(
        TestModel(custom_output_args={"title": title, "blurb": blurb}),
        output_type=TopicDescriptor,
    )


@pytest.mark.asyncio
async def test_returns_descriptor_with_title_and_blurb():
    agent = _make_writer_agent(
        title="Two teenage girls injured riding one e-scooter in Łuków",
        blurb="A traffic incident on May 4 in Łuków, Poland",
    )
    out = await run_topic_writer_agent(
        title="Two girls on one scooter",
        summary="Police footage from Łuków, May 4 2026",
        config=ExtractionAgentConfig(),
        _agent=agent,
    )
    assert out.title.startswith("Two teenage")
    assert out.blurb


@pytest.mark.asyncio
async def test_empty_title_or_blurb_raises():
    """Don't create a topic with no descriptor — agent should provide both."""
    agent = _make_writer_agent(title="", blurb="x")
    with pytest.raises(ValueError):
        await run_topic_writer_agent(
            title="t", summary="s",
            config=ExtractionAgentConfig(), _agent=agent,
        )
