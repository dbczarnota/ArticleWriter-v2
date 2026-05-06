"""Topic matcher agent — decides whether a new RSS item belongs to an
existing topic or needs a new one."""

from __future__ import annotations

import pathlib
import time
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from pydantic_ai import Agent

from agents._base.config import ExtractionAgentConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents._base.resilient import run_with_fallback
from agents._base.run_context import record_agent_call

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class TopicCandidate(BaseModel):
    id: UUID
    title: str
    blurb: str


class MatchDecision(BaseModel):
    matched_topic_id: UUID | None = None
    reasoning: str = ""


async def run_topic_matcher_agent(
    *,
    title: str,
    summary: str | None,
    candidates: list[TopicCandidate],
    config: ExtractionAgentConfig,
    _agent: Agent[Any, Any] | None = None,
) -> MatchDecision:
    if not candidates:
        return MatchDecision(matched_topic_id=None, reasoning="No active topic candidates.")

    cand_block = "\n\n".join(
        f"TOPIC_ID: {c.id}\nTITLE: {c.title}\nBLURB: {c.blurb}" for c in candidates
    )
    user_prompt = (
        f"NEW ITEM:\nTITLE: {title}\nSUMMARY: {summary or '(no summary)'}\n\n"
        f"EXISTING TOPICS:\n{cand_block}"
    )

    if _agent is not None:
        _t0 = time.perf_counter()
        result = await _agent.run(user_prompt)
        _model_used = config.model
    else:

        def _factory(m: str) -> tuple[Agent[Any, Any], str]:
            sys_prompt = render_prompt(
                _PROMPTS_DIR / "match.j2",
                format_style=model_format_style(m),
            )
            return Agent(m, output_type=MatchDecision), sys_prompt

        _t0 = time.perf_counter()
        result, _model_used = await run_with_fallback(
            (config.model, *config.fallback_models),
            agent_factory=_factory,
            user_prompt=user_prompt,
            agent_name="discovery_topic_matcher",
        )

    _u = result.usage()
    record_agent_call(
        "discovery_topic_matcher",
        _model_used,
        _u.input_tokens or 0,
        _u.output_tokens or 0,
        (time.perf_counter() - _t0) * 1000,
    )

    # Validate the LLM didn't hallucinate a UUID outside the candidate list.
    # TODO(perf): swap LLM-judge for embedding pre-filter when topic count
    # per matching window > ~200; spec section "Out of scope".
    valid_ids = {c.id for c in candidates}
    matched = result.output.matched_topic_id
    if matched is not None and matched not in valid_ids:
        matched = None
    return MatchDecision(matched_topic_id=matched, reasoning=result.output.reasoning)
