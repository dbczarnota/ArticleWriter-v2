"""Classifier agent — assigns zero-or-more category tags to an RSS item."""

from __future__ import annotations

import pathlib
import time
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent

from agents._base.config import ExtractionAgentConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents._base.resilient import run_with_fallback
from agents._base.run_context import record_agent_call
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
        return CategoryDecision(categories=[], confidences={}, reasoning="No categories configured.")

    cat_block = "\n".join(f"- {c.name}: {c.description}" for c in categories)
    user_prompt = (
        f"TITLE: {title}\n\n"
        f"SUMMARY: {summary or '(no summary)'}\n\n"
        f"CATEGORIES:\n{cat_block}"
    )

    if _agent is not None:
        _t0 = time.perf_counter()
        result = await _agent.run(user_prompt)
        _model_used = config.model
    else:
        def _factory(m: str) -> tuple[Agent[Any, Any], str]:
            sys_prompt = render_prompt(
                _PROMPTS_DIR / "classify.j2",
                format_style=model_format_style(m),
            )
            return Agent(m, output_type=CategoryDecision), sys_prompt

        _t0 = time.perf_counter()
        result, _model_used = await run_with_fallback(
            (config.model, *config.fallback_models),
            agent_factory=_factory,
            user_prompt=user_prompt,
            agent_name="discovery_classifier",
        )

    _u = result.usage()
    record_agent_call(
        "discovery_classifier",
        _model_used,
        _u.input_tokens or 0,
        _u.output_tokens or 0,
        (time.perf_counter() - _t0) * 1000,
    )

    valid = {c.name for c in categories}
    return CategoryDecision(
        categories=[c for c in result.output.categories if c in valid],
        confidences={k: v for k, v in result.output.confidences.items() if k in valid},
        reasoning=result.output.reasoning,
    )
