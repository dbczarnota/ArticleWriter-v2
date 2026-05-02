# agents/reflection/agent.py
from __future__ import annotations

import pathlib
import time
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage

from agents._base.config import ReflectionAgentConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents._base.resilient import run_with_fallback
from agents._base.run_context import record_agent_call
from agents.writer.agent import ArticleHtml
from domains._base.config import DomainConfig

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class ReflectionFeedback(BaseModel):
    feedback: str
    priority_fixes: list[str]


async def run_reflection_agent(
    article: ArticleHtml,
    *,
    topic: str,
    domain: DomainConfig,
    config: ReflectionAgentConfig,
    message_history: list[ModelMessage] | None = None,
    _agent: Agent[Any, Any] | None = None,
) -> ReflectionFeedback:
    """Review article quality against domain guidelines and return actionable feedback."""
    _user_prompt = f"TOPIC: {topic}\n\nARTICLE TO REVIEW:\n{article.html}"

    if _agent is not None:
        _t0 = time.perf_counter()
        result = await _agent.run(_user_prompt, message_history=message_history or [])
        _model_used = config.model
    else:

        def _factory(m: str):
            return Agent(
                m,
                output_type=ReflectionFeedback,
                system_prompt=render_prompt(
                    _PROMPTS_DIR / "reflection.j2",
                    domain_name=domain.name,
                    guidelines=domain.guidelines,
                    reflection_stance=domain.reflection_stance,
                    target_word_count=domain.target_word_count,
                    format_style=model_format_style(m),
                ),
            )

        _t0 = time.perf_counter()
        result, _model_used = await run_with_fallback(
            (config.model, *config.fallback_models),
            agent_factory=_factory,
            user_prompt=_user_prompt,
            message_history=message_history,
            agent_name="reflection",
        )
    _u = result.usage()
    record_agent_call(
        "reflection",
        _model_used,
        _u.input_tokens or 0,
        _u.output_tokens or 0,
        (time.perf_counter() - _t0) * 1000,
    )
    return result.output
