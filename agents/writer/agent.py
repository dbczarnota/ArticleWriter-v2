from __future__ import annotations
import pathlib
from pydantic import BaseModel
from pydantic_ai import Agent
from agents._base.config import WriterAgentConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents.instructions.agent import WritingBrief
from domains._base.config import DomainConfig

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class ArticleHtml(BaseModel):
    html: str


async def run_writer_agent(
    brief: WritingBrief,
    *,
    topic: str,
    domain: DomainConfig,
    config: WriterAgentConfig,
    reflection_feedback: str | None = None,
    _agent: Agent | None = None,
) -> ArticleHtml:
    """Write an HTML article from the writing brief. Accepts optional reflection feedback for round 2."""
    facts_block = "\n".join(f"- {f}" for f in brief.selected_facts)
    quotes_block = "\n".join(f"- {q}" for q in brief.selected_quotes)

    user_prompt = (
        f"TOPIC: {topic}\n\n"
        f"WRITING INSTRUCTIONS:\n{brief.writing_instructions}\n\n"
        f"FACTS TO USE:\n{facts_block}\n\n"
        f"QUOTES TO USE:\n{quotes_block}"
    )

    if reflection_feedback:
        user_prompt += f"\n\n--- REVISION FEEDBACK ---\n{reflection_feedback}"

    agent = _agent or Agent(
        config.model,
        output_type=ArticleHtml,
        system_prompt=render_prompt(
            _PROMPTS_DIR / "writer.j2",
            domain_name=domain.name,
            guidelines=domain.guidelines,
            example_articles=list(domain.example_articles),
            target_word_count=domain.target_word_count,
            language=domain.language,
            format_style=model_format_style(config.model),
        ),
    )

    result = await agent.run(user_prompt)
    return result.output
