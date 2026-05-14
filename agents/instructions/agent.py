from __future__ import annotations

import pathlib
import time
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent

from agents._base.config import InstructionsAgentConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents._base.resilient import run_with_fallback
from agents._base.run_context import record_agent_call
from agents.extraction.agent import ExtractionResult
from backend.domain import DomainConfig

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
    additional_instructions: str | None = None,
    article_template: str | None = None,
    _agent: Agent[Any, Any] | None = None,
) -> WritingBrief:
    """Select best facts/quotes and create writing instructions for WriterAgent."""
    # Render `source_urls` and `corroboration` so the instructions LLM can
    # see *how many* sources back each fact/quote and prioritize accordingly.
    # A fact corroborated by 4 articles is stronger evidence than one that
    # appears in a single source.
    facts_text = "\n".join(
        f"[{i + 1}] {f.text} [context: {f.context}] "
        f"[corroboration: {len(f.source_urls)}] [sources: {', '.join(f.source_urls) or '(none)'}]"
        for i, f in enumerate(extraction_result.facts)
    )
    quotes_text = "\n".join(
        f'[{i + 1}] "{q.text}" — {q.speaker} ({q.context}) '
        f"[corroboration: {len(q.source_urls)}] [sources: {', '.join(q.source_urls) or '(none)'}]"
        for i, q in enumerate(extraction_result.quotes)
    )
    keywords_text = ", ".join(extraction_result.keywords)

    material = (
        f"TOPIC: {topic}\n\n"
        f"AVAILABLE FACTS:\n{facts_text or '(none)'}\n\n"
        f"AVAILABLE QUOTES:\n{quotes_text or '(none)'}\n\n"
        f"KEYWORDS: {keywords_text}"
    )
    if article_template:
        material += f"\n\n### TEMPLATE INSTRUCTIONS:\n{article_template}"
    if additional_instructions:
        material += f"\n\n### Additional Instructions and Context:\n{additional_instructions}\nThey are very important and must be included."

    if _agent is not None:
        _t0 = time.perf_counter()
        result = await _agent.run(material)
        _model_used = config.model
    else:

        def _factory(m: str) -> tuple[Agent[Any, Any], str]:
            sys_prompt = render_prompt(
                _PROMPTS_DIR / "instructions.j2",
                domain_name=domain.name,
                guidelines=domain.guidelines,
                html_format=domain.html_format,
                max_facts=domain.max_facts_in_article,
                max_quotes=domain.max_quotes_in_article,
                target_word_count=domain.target_word_count,
                language=domain.language,
                format_style=model_format_style(m),
            )
            return Agent(m, output_type=WritingBrief), sys_prompt

        _t0 = time.perf_counter()
        result, _model_used = await run_with_fallback(
            (config.model, *config.fallback_models),
            agent_factory=_factory,
            user_prompt=material,
            agent_name="instructions",
        )
    _u = result.usage
    record_agent_call(
        "instructions",
        _model_used,
        _u.input_tokens or 0,
        _u.output_tokens or 0,
        (time.perf_counter() - _t0) * 1000,
    )
    return result.output
