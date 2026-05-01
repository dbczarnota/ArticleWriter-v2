# agents/usage_tracking/agent.py
from __future__ import annotations
import time
from pydantic import BaseModel
from pydantic_ai import Agent
from agents._base.config import UsageTrackingAgentConfig
from agents._base.run_context import record_agent_call
from agents.extraction.agent import ExtractionResult
from agents.writer.agent import ArticleHtml


class _UsageOutput(BaseModel):
    used_facts: list[str]
    used_quotes: list[str]


async def run_usage_tracking_agent(
    article: ArticleHtml,
    *,
    extraction_result: ExtractionResult,
    config: UsageTrackingAgentConfig,
    _agent: Agent | None = None,
) -> tuple[list[str], list[str]]:
    """Identify which facts and quotes from extraction actually appear in the article."""
    if not extraction_result.facts and not extraction_result.quotes:
        return [], []

    facts_text = "\n".join(f"- {f.text}" for f in extraction_result.facts)
    quotes_text = "\n".join(f'- "{q.text}" — {q.speaker}' for q in extraction_result.quotes)

    user_prompt = (
        f"ARTICLE:\n{article.html}\n\n"
        f"FACTS:\n{facts_text or '(none)'}\n\n"
        f"QUOTES:\n{quotes_text or '(none)'}"
    )

    agent = _agent or Agent(
        config.model,
        output_type=_UsageOutput,
        system_prompt=(
            "You receive an article and two lists: FACTS and QUOTES. "
            "Return exactly which fact texts and quote texts appear (verbatim or nearly verbatim) in the article. "
            "Return only items from the provided lists — no additions."
        ),
    )

    _t0 = time.perf_counter()
    result = await agent.run(user_prompt)
    _u = result.usage()
    record_agent_call("usage_tracking", config.model, _u.input_tokens or 0, _u.output_tokens or 0,
                      (time.perf_counter() - _t0) * 1000)
    return result.output.used_facts, result.output.used_quotes
