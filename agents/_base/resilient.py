# agents/_base/resilient.py
from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from typing import Any

import logfire
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage

from agents._base.messaging import prepend_system
from agents._base.run_context import record_fallback


class AllModelsFailedError(Exception):
    """Raised when every model in the fallback list fails."""

    def __init__(self, errors: list[tuple[str, Exception]]) -> None:
        self.errors = errors
        summary = "; ".join(f"{m}: {type(e).__name__}({e})" for m, e in errors)
        super().__init__(f"All {len(errors)} model(s) failed — {summary}")


class InsufficientSourcesError(Exception):
    """Raised when the pipeline produced too few extracted facts/quotes to write a grounded article.

    Trips on any upstream collapse: Serper (search API) credits exhausted or auth failed,
    Jina (scraper) credits exhausted or timed out for all URLs, parser yielded 0 articles,
    extraction returned empty. The pipeline bails BEFORE the writer is invoked, rather
    than letting it hallucinate from no source material.

    `upstream_errors` lists the per-stage errors collected during the run so the caller can
    distinguish "Serper auth failed" from "all pages timed out in Jina" etc.
    """

    def __init__(
        self,
        facts_count: int,
        quotes_count: int,
        min_required: int,
        upstream_errors: list[dict[str, str]] | None = None,
    ) -> None:
        self.facts_count = facts_count
        self.quotes_count = quotes_count
        self.min_required = min_required
        self.upstream_errors = upstream_errors or []
        upstream_summary = (
            "; ".join(f"{e.get('stage', '?')}: {e.get('error', '')}" for e in self.upstream_errors)
            if self.upstream_errors
            else "no upstream errors recorded — extraction likely returned empty"
        )
        super().__init__(
            f"Insufficient source material to write article: "
            f"{facts_count} facts + {quotes_count} quotes "
            f"(required at least {min_required} signal). "
            f"Refusing to invoke writer to prevent hallucination. "
            f"Upstream: {upstream_summary}"
        )


async def run_with_fallback(
    model_list: Sequence[str],
    *,
    agent_factory: Callable[[str], tuple[Agent[Any, Any], str]],
    user_prompt: str,
    message_history: list[ModelMessage] | None = None,
    timeout: float = 300.0,
    agent_name: str = "",
) -> tuple[Any, str]:
    """Try each model in order. Return (RunResult, model_used) on first success.

    `agent_factory(model_name)` must return `(agent, system_prompt)`. The agent
    must NOT have `system_prompt=` set — we inject it as the first message_history
    item to avoid pydantic-ai's system-prompt-collision bug when prior history
    is passed in. See agents/_base/messaging.py for the rationale.

    Falls back silently to the next model on any exception.
    Raises AllModelsFailedError only after exhausting the entire list.
    """
    errors: list[tuple[str, Exception]] = []

    for model in model_list:
        try:
            agent, system_prompt = agent_factory(model)
            full_history = prepend_system(system_prompt, message_history)
            result = await asyncio.wait_for(
                agent.run(user_prompt, message_history=full_history),
                timeout=timeout,
            )
            return result, model
        except Exception as exc:
            errors.append((model, exc))
            record_fallback(agent_name, model, type(exc).__name__, str(exc))
            remaining = len(model_list) - len(errors)
            if remaining > 0:
                logfire.warn(
                    "agent_fallback",
                    agent=agent_name,
                    failed_model=model,
                    error_type=type(exc).__name__,
                    models_remaining=remaining,
                )

    raise AllModelsFailedError(errors)
