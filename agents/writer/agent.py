from __future__ import annotations

import pathlib
import time
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage

from agents._base.config import WriterAgentConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents._base.resilient import run_with_fallback
from agents._base.run_context import record_agent_call
from agents.instructions.agent import WritingBrief
from domains._base.config import DomainConfig

if TYPE_CHECKING:
    from agents.reflection.agent import ReflectionFeedback

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class ArticleHtml(BaseModel):
    html: str


async def run_writer_agent(
    brief: WritingBrief,
    *,
    topic: str,
    domain: DomainConfig,
    config: WriterAgentConfig,
    reflection_feedback: ReflectionFeedback | None = None,
    additional_instructions: str | None = None,
    message_history: list[ModelMessage] | None = None,
    _agent: Agent[Any, Any] | None = None,
) -> tuple[ArticleHtml, list[ModelMessage]]:
    """Write an HTML article from the writing brief.

    `message_history` is the writer's accumulated turns from prior rounds (for the
    writer→reflection→writer revision loop). When provided, the writer sees its own
    earlier drafts and can revise consciously rather than regenerate from scratch.
    """
    facts_block = "\n".join(f"- {f}" for f in brief.selected_facts)
    quotes_block = "\n".join(f"- {q}" for q in brief.selected_quotes)

    user_prompt = (
        f"TOPIC: {topic}\n\n"
        f"WRITING INSTRUCTIONS:\n{brief.writing_instructions}\n\n"
        f"FACTS TO USE:\n{facts_block}\n\n"
        f"QUOTES TO USE:\n{quotes_block}"
    )

    if additional_instructions:
        user_prompt += f"\n\n### Additional Instructions and Context:\n{additional_instructions}"

    if reflection_feedback:
        fixes = "\n".join(f"- {f}" for f in reflection_feedback.priority_fixes)
        user_prompt += (
            f"\n\n--- REVISION FEEDBACK ---\n{reflection_feedback.feedback}"
            f"\n\nPRIORITY FIXES:\n{fixes}"
        )

    if _agent is not None:
        _t0 = time.perf_counter()
        result = await _agent.run(user_prompt, message_history=message_history or [])
        _model_used = config.model
    else:

        def _factory(m: str) -> tuple[Agent[Any, Any], str]:
            sys_prompt = render_prompt(
                _PROMPTS_DIR / "writer.j2",
                domain_name=domain.name,
                guidelines=domain.guidelines,
                html_format=domain.html_format,
                example_articles=list(domain.example_articles),
                target_word_count=domain.target_word_count,
                language=domain.language,
                format_style=model_format_style(m),
            )
            return Agent(m, output_type=ArticleHtml), sys_prompt

        _t0 = time.perf_counter()
        result, _model_used = await run_with_fallback(
            (config.model, *config.fallback_models),
            agent_factory=_factory,
            user_prompt=user_prompt,
            message_history=message_history,
            agent_name="writer",
        )
    _u = result.usage()
    record_agent_call(
        "writer",
        _model_used,
        _u.input_tokens or 0,
        _u.output_tokens or 0,
        (time.perf_counter() - _t0) * 1000,
    )
    return result.output, list(result.all_messages())
