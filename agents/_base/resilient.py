# agents/_base/resilient.py
from __future__ import annotations
import asyncio
from typing import Any, Callable, Sequence

import logfire
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage


class AllModelsFailedError(Exception):
    """Raised when every model in the fallback list fails."""

    def __init__(self, errors: list[tuple[str, Exception]]) -> None:
        self.errors = errors
        summary = "; ".join(f"{m}: {type(e).__name__}({e})" for m, e in errors)
        super().__init__(f"All {len(errors)} model(s) failed — {summary}")


async def run_with_fallback(
    model_list: Sequence[str],
    *,
    agent_factory: Callable[[str], Agent],
    user_prompt: str,
    message_history: list[ModelMessage] | None = None,
    timeout: float = 300.0,
) -> tuple[Any, str]:
    """Try each model in order. Return (RunResult, model_used) on first success.

    Falls back silently to the next model on any exception.
    Raises AllModelsFailedError only after exhausting the entire list.
    """
    errors: list[tuple[str, Exception]] = []

    for model in model_list:
        try:
            agent = agent_factory(model)
            result = await asyncio.wait_for(
                agent.run(user_prompt, message_history=message_history or []),
                timeout=timeout,
            )
            return result, model
        except Exception as exc:
            errors.append((model, exc))
            remaining = len(model_list) - len(errors)
            if remaining > 0:
                logfire.warn(
                    "agent_fallback",
                    failed_model=model,
                    error_type=type(exc).__name__,
                    models_remaining=remaining,
                )

    raise AllModelsFailedError(errors)
