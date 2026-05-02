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
    additional_instructions: str | None = None,
    _agent: Agent[Any, Any] | None = None,
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
    if additional_instructions:
        material += f"\n\n### Additional Instructions and Context:\n{additional_instructions}\nThey are very important and must be included."

    if _agent is not None:
        _t0 = time.perf_counter()
        result = await _agent.run(material)
        _model_used = config.model
    else:

        def _factory(m: str):
            return Agent(
                m,
                output_type=WritingBrief,
                system_prompt=render_prompt(
                    _PROMPTS_DIR / "instructions.j2",
                    domain_name=domain.name,
                    guidelines=domain.guidelines,
                    max_facts=domain.max_facts_in_article,
                    max_quotes=domain.max_quotes_in_article,
                    target_word_count=domain.target_word_count,
                    language=domain.language,
                    format_style=model_format_style(m),
                ),
            )

        _t0 = time.perf_counter()
        result, _model_used = await run_with_fallback(
            (config.model, *config.fallback_models),
            agent_factory=_factory,
            user_prompt=material,
            agent_name="instructions",
        )
    _u = result.usage()
    record_agent_call(
        "instructions",
        _model_used,
        _u.input_tokens or 0,
        _u.output_tokens or 0,
        (time.perf_counter() - _t0) * 1000,
    )
    return result.output
