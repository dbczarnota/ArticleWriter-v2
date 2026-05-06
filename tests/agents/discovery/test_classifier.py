from __future__ import annotations

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from agents._base.config import ExtractionAgentConfig  # reuse model+fallback shape
from agents.discovery.classifier.agent import (
    CategoryDecision,
    run_classifier_agent,
)
from backend.domain import CategoryConfig


def _make_classifier_agent(categories: list[str], confidences: dict[str, float] | None = None):
    decision = {
        "categories": categories,
        "confidences": confidences or {},
        "reasoning": "test",
    }
    return Agent(TestModel(custom_output_args=decision), output_type=CategoryDecision)


@pytest.mark.asyncio
async def test_returns_categories_chosen_by_llm():
    cats = [CategoryConfig(name="Sport", description="x"), CategoryConfig(name="Polityka", description="y")]
    agent = _make_classifier_agent(categories=["Sport"])
    out = await run_classifier_agent(
        title="Mecz", summary="Polska wygrała", categories=cats,
        config=ExtractionAgentConfig(), _agent=agent,
    )
    assert out.categories == ["Sport"]


@pytest.mark.asyncio
async def test_empty_categories_returns_empty_list():
    agent = _make_classifier_agent(categories=[])
    out = await run_classifier_agent(
        title="T", summary="S", categories=[],
        config=ExtractionAgentConfig(), _agent=agent,
    )
    assert out.categories == []


@pytest.mark.asyncio
async def test_can_return_multiple_categories():
    agent = _make_classifier_agent(categories=["Sport", "Polityka"])
    out = await run_classifier_agent(
        title="T", summary="S",
        categories=[CategoryConfig(name="Sport", description="x"), CategoryConfig(name="Polityka", description="y")],
        config=ExtractionAgentConfig(), _agent=agent,
    )
    assert sorted(out.categories) == ["Polityka", "Sport"]
