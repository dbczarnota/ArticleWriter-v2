"""Helpers for building pydantic-ai messages explicitly.

Why this module exists:

    pydantic-ai has a footgun where passing `system_prompt=...` to `Agent(...)`
    AND `message_history=[...]` to `agent.run()` can cause the LLM to see the
    *previous* agent's system prompt instead of the current one (because pydantic-ai
    keeps the SystemPromptPart from history alongside the new system_prompt).

    Workaround: never pass `system_prompt=` to Agent. Build the system prompt as a
    `ModelRequest(parts=[SystemPromptPart(...)])` and put it as the first element
    of `message_history` yourself. Then there is exactly one source of truth for
    the system prompt and the bug cannot occur.

    This pattern is used in prawnik-ai-v2 (reviewer/consolidator/researcher agents)
    for the same reason.
"""

from __future__ import annotations

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    SystemPromptPart,
    UserPromptPart,
)


def build_system_message(content: str) -> ModelRequest:
    """Wrap a system prompt as a ModelRequest so it can be the first message_history item.

    SystemPromptPart auto-generates its own timestamp via field(default_factory=_now_utc).
    """
    return ModelRequest(parts=[SystemPromptPart(content=content)])


def build_user_message(content: str) -> ModelRequest:
    """Wrap a user prompt as a ModelRequest (used when injecting historical user turns)."""
    return ModelRequest(parts=[UserPromptPart(content=content)])


def prepend_system(
    system_prompt: str,
    history: list[ModelMessage] | None = None,
) -> list[ModelMessage]:
    """Build [sys_msg, *history]. Pass the result as `message_history=` to agent.run().

    If `history` already begins with a system-prompt-only ModelRequest (e.g. it's the
    `result.all_messages()` from a PRIOR run of the same agent — happens in writer-reflection
    revision rounds), drop that leading message before prepending the new sys_msg. Otherwise
    every revision round would compound an extra system prompt and waste input tokens
    proportionally to the round count.
    """
    history = list(history or [])
    if history and isinstance(history[0], ModelRequest):
        first_parts = history[0].parts
        if first_parts and all(isinstance(p, SystemPromptPart) for p in first_parts):
            history = history[1:]
    return [build_system_message(system_prompt), *history]
