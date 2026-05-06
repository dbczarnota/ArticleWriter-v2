"""Classifier agent — assigns zero-or-more category tags to an RSS item."""

from __future__ import annotations

import pathlib
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent

from agents._base.config import ExtractionAgentConfig
from agents._base.simple_agent import run_simple_agent
from backend.domain import CategoryConfig

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class CategoryDecision(BaseModel):
    categories: list[str] = []
    """Subset of input category names. Empty list = uncategorized."""
    confidences: dict[str, float] = {}
    """Optional per-tag confidence in [0..1] for diagnostics."""
    reasoning: str = ""


async def run_classifier_agent(
    *,
    title: str,
    summary: str | None,
    categories: list[CategoryConfig],
    config: ExtractionAgentConfig,
    _agent: Agent[Any, Any] | None = None,
) -> CategoryDecision:
    if not categories:
        return CategoryDecision(
            categories=[], confidences={}, reasoning="No categories configured."
        )

    cat_block = "\n".join(f"- {c.name}: {c.description}" for c in categories)
    user_prompt = (
        f"TITLE: {title}\n\nSUMMARY: {summary or '(no summary)'}\n\nCATEGORIES:\n{cat_block}"
    )

    output, _model, _tin, _tout = await run_simple_agent(
        prompts_dir=_PROMPTS_DIR,
        prompt_name="classify.j2",
        output_type=CategoryDecision,
        agent_name="discovery_classifier",
        user_prompt=user_prompt,
        config=config,
        _agent=_agent,
    )

    valid = {c.name for c in categories}
    return CategoryDecision(
        categories=[c for c in output.categories if c in valid],
        confidences={k: v for k, v in output.confidences.items() if k in valid},
        reasoning=output.reasoning,
    )
