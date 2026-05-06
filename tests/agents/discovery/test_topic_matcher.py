from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from agents._base.config import ExtractionAgentConfig
from agents.discovery.topic_matcher.agent import (
    MatchDecision,
    TopicCandidate,
    run_topic_matcher_agent,
)


def _make_matcher_agent(matched_id: str | None):
    return Agent(
        TestModel(custom_output_args={"matched_topic_id": matched_id, "reasoning": "test"}),
        output_type=MatchDecision,
    )


@pytest.mark.asyncio
async def test_empty_candidates_always_returns_none():
    """Whatever the LLM hallucinates, no candidates -> None."""
    agent = _make_matcher_agent(matched_id="some-id-the-llm-made-up")
    out = await run_topic_matcher_agent(
        title="X", summary="Y", candidates=[],
        config=ExtractionAgentConfig(), _agent=agent,
    )
    assert out.matched_topic_id is None


@pytest.mark.asyncio
async def test_returns_matched_id_when_in_candidates():
    cand = TopicCandidate(id=uuid4(), title="Existing", blurb="An ongoing story")
    agent = _make_matcher_agent(matched_id=str(cand.id))
    out = await run_topic_matcher_agent(
        title="More on existing", summary="...", candidates=[cand],
        config=ExtractionAgentConfig(), _agent=agent,
    )
    assert out.matched_topic_id == cand.id


@pytest.mark.asyncio
async def test_invalid_id_treated_as_no_match():
    cand = TopicCandidate(id=uuid4(), title="Existing", blurb="...")
    agent = _make_matcher_agent(matched_id=str(uuid4()))  # not in candidates
    out = await run_topic_matcher_agent(
        title="X", summary="Y", candidates=[cand],
        config=ExtractionAgentConfig(), _agent=agent,
    )
    assert out.matched_topic_id is None
