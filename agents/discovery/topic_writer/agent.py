"""Topic writer agent — produces a stable internal description of a new
discovered story (title + blurb) used by the matcher for later items."""

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

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class TopicDescriptor(BaseModel):
    title: str
    blurb: str


async def run_topic_writer_agent(
    *,
    title: str,
    summary: str | None,
    config: ExtractionAgentConfig,
    _agent: Agent[Any, Any] | None = None,
) -> TopicDescriptor:
    user_prompt = f"ITEM TITLE: {title}\n\nITEM SUMMARY: {summary or '(no summary)'}"

    if _agent is not None:
        _t0 = time.perf_counter()
        result = await _agent.run(user_prompt)
        _model_used = config.model
    else:

        def _factory(m: str) -> tuple[Agent[Any, Any], str]:
            sys_prompt = render_prompt(
                _PROMPTS_DIR / "describe.j2",
                format_style=model_format_style(m),
            )
            return Agent(m, output_type=TopicDescriptor), sys_prompt

        _t0 = time.perf_counter()
        result, _model_used = await run_with_fallback(
            (config.model, *config.fallback_models),
            agent_factory=_factory,
            user_prompt=user_prompt,
            agent_name="discovery_topic_writer",
        )

    _u = result.usage()
    record_agent_call(
        "discovery_topic_writer",
        _model_used,
        _u.input_tokens or 0,
        _u.output_tokens or 0,
        (time.perf_counter() - _t0) * 1000,
    )

    if not result.output.title.strip() or not result.output.blurb.strip():
        raise ValueError("Topic writer returned empty title or blurb")
    return TopicDescriptor(
        title=result.output.title.strip()[:512],
        blurb=result.output.blurb.strip()[:1024],
    )
