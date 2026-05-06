"""Topic writer agent — produces a stable internal description of a new
discovered story (title + blurb) used by the matcher for later items."""

from __future__ import annotations

import pathlib
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent

from agents._base.config import ExtractionAgentConfig
from agents._base.simple_agent import run_simple_agent

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class TopicDescriptor(BaseModel):
    title: str
    blurb: str


async def run_topic_writer_agent(
    *,
    title: str,
    summary: str | None,
    language: str = "pl",
    config: ExtractionAgentConfig,
    _agent: Agent[Any, Any] | None = None,
) -> TopicDescriptor:
    user_prompt = (
        f"OUTPUT LANGUAGE: {language}\n\n"
        f"ITEM TITLE: {title}\n\nITEM SUMMARY: {summary or '(no summary)'}"
    )

    output, _model, _tin, _tout = await run_simple_agent(
        prompts_dir=_PROMPTS_DIR,
        prompt_name="describe.j2",
        output_type=TopicDescriptor,
        agent_name="discovery_topic_writer",
        user_prompt=user_prompt,
        config=config,
        _agent=_agent,
    )

    if not output.title.strip() or not output.blurb.strip():
        raise ValueError("Topic writer returned empty title or blurb")
    return TopicDescriptor(
        title=output.title.strip()[:512],
        blurb=output.blurb.strip()[:1024],
    )
