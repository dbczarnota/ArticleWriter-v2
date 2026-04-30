from __future__ import annotations
import pathlib
from pydantic import BaseModel
from pydantic_ai import Agent
from agents._base.config import InstructionsAgentConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents.extraction.agent import ExtractionResult
from domains._base.config import DomainConfig

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class WritingBrief(BaseModel):
    selected_facts: list[str]
    selected_quotes: list[str]
    writing_instructions: str


async def run_instructions_agent(
    extraction_result: ExtractionResult,
    *,
    topic: str,
    domain: DomainConfig,
    config: InstructionsAgentConfig,
    _agent: Agent | None = None,
) -> WritingBrief:
    """Select best facts/quotes and create writing instructions for WriterAgent."""
    facts_text = "\n".join(
        f"[{i + 1}] {f.text} [context: {f.context}] [source: {f.source_url}]"
        for i, f in enumerate(extraction_result.facts)
    )
    quotes_text = "\n".join(
        f'[{i + 1}] "{q.text}" — {q.speaker} ({q.context}) [source: {q.source_url}]'
        for i, q in enumerate(extraction_result.quotes)
    )
    keywords_text = ", ".join(extraction_result.keywords)

    material = (
        f"TOPIC: {topic}\n\n"
        f"AVAILABLE FACTS:\n{facts_text or '(none)'}\n\n"
        f"AVAILABLE QUOTES:\n{quotes_text or '(none)'}\n\n"
        f"KEYWORDS: {keywords_text}"
    )

    agent = _agent or Agent(
        config.model,
        output_type=WritingBrief,
        system_prompt=render_prompt(
            _PROMPTS_DIR / "instructions.j2",
            domain_name=domain.name,
            guidelines=domain.guidelines,
            max_facts=domain.max_facts_in_article,
            max_quotes=domain.max_quotes_in_article,
            target_word_count=domain.target_word_count,
            language=domain.language,
            format_style=model_format_style(config.model),
        ),
    )

    result = await agent.run(material)
    return result.output
