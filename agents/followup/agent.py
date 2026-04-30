# agents/followup/agent.py
from __future__ import annotations
import pathlib
from pydantic import BaseModel
from pydantic_ai import Agent
from agents._base.config import FollowUpAgentConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents._base.types import ArticleOutput
from agents.extraction.agent import ExtractionResult
from agents.writer.agent import ArticleHtml

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class FollowUpOutput(BaseModel):
    alternative_titles: list[str]
    followup_topics: list[str]


async def run_followup_agent(
    article: ArticleHtml,
    *,
    topic: str,
    extraction_result: ExtractionResult,
    config: FollowUpAgentConfig,
    _agent: Agent | None = None,
) -> ArticleOutput:
    """Generate alternative titles, follow-up topics, and track used facts/quotes."""
    facts_text = "\n".join(
        f"- {f.text} [{f.context}]" for f in extraction_result.facts
    )
    quotes_text = "\n".join(
        f'- "{q.text}" — {q.speaker}' for q in extraction_result.quotes
    )

    user_prompt = (
        f"TOPIC: {topic}\n\n"
        f"PUBLISHED ARTICLE:\n{article.html}\n\n"
        f"SOURCE FACTS:\n{facts_text or '(none)'}\n\n"
        f"SOURCE QUOTES:\n{quotes_text or '(none)'}"
    )

    agent = _agent or Agent(
        config.model,
        output_type=FollowUpOutput,
        system_prompt=render_prompt(
            _PROMPTS_DIR / "followup.j2",
            num_titles=config.num_titles,
            num_topics=config.num_topics,
            format_style=model_format_style(config.model),
        ),
    )

    result = await agent.run(user_prompt)
    output = result.output

    sources = list({f.source_url for f in extraction_result.facts}
                   | {q.source_url for q in extraction_result.quotes})

    return ArticleOutput(
        html=article.html,
        alternative_titles=output.alternative_titles,
        followup_topics=output.followup_topics,
        used_facts=[],
        used_quotes=[],
        sources=sources,
    )
