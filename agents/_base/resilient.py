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
