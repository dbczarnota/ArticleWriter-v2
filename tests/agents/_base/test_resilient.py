# tests/agents/_base/test_resilient.py
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from pydantic import BaseModel
from agents._base.resilient import AllModelsFailedError, run_with_fallback


class _Out(BaseModel):
    value: str


def _make_test_agent(model_str: str) -> Agent:
    """Factory that ignores model_str and returns a TestModel agent."""
    return Agent(TestModel(custom_output_args={"value": "ok"}), output_type=_Out)


async def test_run_with_fallback_succeeds_on_first_model():
    result, model_used = await run_with_fallback(
        ["google-gla:gemini-2.5-flash", "openai:gpt-4o-mini"],
        agent_factory=_make_test_agent,
        user_prompt="hello",
    )
    assert result.output.value == "ok"
    assert model_used == "google-gla:gemini-2.5-flash"


async def test_run_with_fallback_falls_back_on_error():
    call_count = 0

    def _factory(m: str) -> Agent:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            agent = MagicMock(spec=Agent)
            agent.run = AsyncMock(side_effect=ValueError("model overloaded"))
            return agent
        return Agent(TestModel(custom_output_args={"value": "fallback_ok"}), output_type=_Out)

    result, model_used = await run_with_fallback(
        ["bad-model", "good-model"],
        agent_factory=_factory,
        user_prompt="hello",
    )
    assert result.output.value == "fallback_ok"
    assert model_used == "good-model"
    assert call_count == 2


async def test_run_with_fallback_raises_all_models_failed():
    def _failing_factory(m: str) -> Agent:
        agent = MagicMock(spec=Agent)
        agent.run = AsyncMock(side_effect=RuntimeError(f"{m} failed"))
        return agent

    with pytest.raises(AllModelsFailedError) as exc_info:
        await run_with_fallback(
            ["model-a", "model-b"],
            agent_factory=_failing_factory,
            user_prompt="hello",
        )

    err = exc_info.value
    assert len(err.errors) == 2
    assert err.errors[0][0] == "model-a"
    assert err.errors[1][0] == "model-b"
    assert isinstance(err.errors[0][1], RuntimeError)


async def test_all_models_failed_error_message_contains_model_names():
    errors = [("model-a", ValueError("err a")), ("model-b", ValueError("err b"))]
    exc = AllModelsFailedError(errors)
    msg = str(exc)
    assert "model-a" in msg
    assert "model-b" in msg


async def test_run_with_fallback_passes_message_history():
    received_history = []

    def _factory(m: str) -> Agent:
        agent = MagicMock(spec=Agent)
        async def _run(prompt, message_history=None, **kwargs):
            received_history.extend(message_history or [])
            result = MagicMock()
            result.output = _Out(value="ok")
            result.usage = MagicMock(return_value=MagicMock(input_tokens=1, output_tokens=1))
            result.all_messages = MagicMock(return_value=[])
            return result
        agent.run = _run
        return agent

    sentinel = object()
    await run_with_fallback(
        ["model-a"],
        agent_factory=_factory,
        user_prompt="hello",
        message_history=[sentinel],
    )
    assert sentinel in received_history


async def test_run_with_fallback_timeout_triggers_fallback():
    import asyncio

    async def _slow(*args, **kwargs):
        await asyncio.sleep(999)

    call_count = 0

    def _factory(_m: str) -> Agent:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            agent = MagicMock(spec=Agent)
            agent.run = _slow
            return agent
        return Agent(TestModel(custom_output_args={"value": "after_timeout"}), output_type=_Out)

    result, model_used = await run_with_fallback(
        ["slow-model", "fast-model"],
        agent_factory=_factory,
        user_prompt="hello",
        timeout=0.05,  # 50ms — times out the 999s sleep but allows TestModel to respond
    )
    assert result.output.value == "after_timeout"
    assert model_used == "fast-model"
