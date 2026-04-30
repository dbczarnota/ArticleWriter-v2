# agents/adaptive_search/agent.py
from __future__ import annotations
import pathlib
from pydantic import BaseModel
from pydantic_ai import Agent
from agents._base.config import AdaptiveSearchAgentConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents.extraction.agent import ExtractionResult

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"


class AdaptiveSearchDecision(BaseModel):
    needs_more_research: bool
    additional_queries: list[str] = []
    reasoning: str = ""


async def run_adaptive_search_agent(
    extraction_result: ExtractionResult,
    *,
    topic: str,
    config: AdaptiveSearchAgentConfig,
    _agent: Agent | None = None,
) -> AdaptiveSearchDecision:
    """Evaluate coverage and decide whether another search round is needed.

    Short-circuits to needs_more_research=True when extraction is empty — no LLM call needed.
    """
    if not extraction_result.facts and not extraction_result.quotes:
        return AdaptiveSearchDecision(
            needs_more_research=True,
            additional_queries=[],
            reasoning="No facts or quotes extracted.",
        )

    facts_text = "\n".join(
        f"- {f.text} [{f.context}]" for f in extraction_result.facts
    )
    quotes_text = "\n".join(
        f'- "{q.text}" — {q.speaker} ({q.context})'
        for q in extraction_result.quotes
    )
    summary = f"FACTS ({len(extraction_result.facts)}):\n{facts_text}\n\nQUOTES ({len(extraction_result.quotes)}):\n{quotes_text}"

    agent = _agent or Agent(
        config.model,
        output_type=AdaptiveSearchDecision,
        system_prompt=render_prompt(
            _PROMPTS_DIR / "adaptive.j2",
            topic=topic,
            format_style=model_format_style(config.model),
        ),
    )

    result = await agent.run(summary)
    return result.output
