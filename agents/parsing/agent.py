# agents/parsing/agent.py
from __future__ import annotations
import pathlib
from pydantic import BaseModel
from pydantic_ai import Agent
from agents._base.config import ParsingAgentConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents._base.types import ParsedArticle, ScrapedPage

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class ParseResult(BaseModel):
    is_article: bool
    title: str = ""
    content: str = ""
    publication_date: str | None = None


async def run_parsing_agent(
    scraped_pages: list[ScrapedPage],
    *,
    config: ParsingAgentConfig,
    _agent: Agent | None = None,
) -> list[ParsedArticle]:
    """Classify and clean each scraped page. Returns only pages identified as articles."""
    if not scraped_pages:
        return []

    agent = _agent or Agent(
        config.model,
        output_type=ParseResult,
        system_prompt=render_prompt(
            _PROMPTS_DIR / "parse.j2",
            format_style=model_format_style(config.model),
        ),
    )

    results: list[ParsedArticle] = []
    for page in scraped_pages:
        result = await agent.run(
            f"URL: {page.url}\nTitle: {page.title}\n\n{page.content}"
        )
        if result.output.is_article:
            results.append(
                ParsedArticle(
                    url=page.url,
                    title=result.output.title or page.title,
                    content=result.output.content or page.content,
                    publication_date=result.output.publication_date,
                )
            )

    return results
