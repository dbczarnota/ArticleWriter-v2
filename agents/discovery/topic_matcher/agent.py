"""Topic matcher agent — decides whether a new RSS item belongs to an
existing topic or needs a new one."""

from __future__ import annotations

import pathlib
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from pydantic_ai import Agent

from agents._base.config import ExtractionAgentConfig
from agents._base.simple_agent import run_simple_agent

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

    output, _model, _tin, _tout = await run_simple_agent(
        prompts_dir=_PROMPTS_DIR,
        prompt_name="match.j2",
        output_type=MatchDecision,
        agent_name="discovery_topic_matcher",
        user_prompt=user_prompt,
        config=config,
        _agent=_agent,
    )

    # Validate the LLM didn't hallucinate a UUID outside the candidate list.
    # TODO(perf): swap LLM-judge for embedding pre-filter when topic count
    # per matching window > ~200; spec section "Out of scope".
    valid_ids = {c.id for c in candidates}
    matched = output.matched_topic_id
    if matched is not None and matched not in valid_ids:
        matched = None
    return MatchDecision(matched_topic_id=matched, reasoning=output.reasoning)
