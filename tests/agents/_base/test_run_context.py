# tests/agents/_base/test_run_context.py
import pytest
import asyncio
from agents._base.run_context import (
    init_collector,
    record_agent_call,
    AgentCallRecord,
    _collector,
    record_fallback,
    get_fallback_events,
    FallbackEvent,
    _fallback_collector,
)


def test_init_collector_returns_empty_list():
    records = init_collector()
    assert records == []


def test_record_agent_call_appends_to_collector():
    records = init_collector()
    record_agent_call(
        agent="search",
        model="google-gla:gemini-2.5-flash",
        input_tokens=100,
        output_tokens=50,
        duration_ms=230.0,
    )
    assert len(records) == 1
    r = records[0]
    assert r.agent == "search"
    assert r.model == "google-gla:gemini-2.5-flash"
    assert r.input_tokens == 100
    assert r.output_tokens == 50
    assert r.duration_ms == pytest.approx(230.0)


def test_record_without_collector_does_not_raise():
    # contextvars default is None — recording outside a pipeline run must be a no-op
    _collector.set(None)
    record_agent_call("search", "model", 1, 1, 1.0)  # must not raise


async def test_collector_isolated_per_async_context():
    """Two concurrent async tasks must not share the same collector."""
    results: list[list[AgentCallRecord]] = []

    async def task(name: str) -> None:
        records = init_collector()
        await asyncio.sleep(0)  # yield to other task
        record_agent_call(name, "model", 1, 1, 1.0)
        results.append(list(records))

    await asyncio.gather(task("a"), task("b"))
    # Each task should see only its own record
    agents_seen = {r[0].agent for r in results}
    assert agents_seen == {"a", "b"}


def test_init_collector_also_resets_fallback_collector():
    """init_collector must reset both collectors atomically."""
    init_collector()
    record_fallback("search", "model-a", "ValueError", "boom")
    assert len(get_fallback_events()) == 1
    # Re-init must clear fallback events
    init_collector()
    assert get_fallback_events() == []


def test_record_fallback_appends_event():
    init_collector()
    record_fallback("writer", "openai:gpt-4o", "TimeoutError", "timed out after 300s")
    events = get_fallback_events()
    assert len(events) == 1
    e = events[0]
    assert isinstance(e, FallbackEvent)
    assert e.agent == "writer"
    assert e.failed_model == "openai:gpt-4o"
    assert e.error_type == "TimeoutError"
    assert e.error_message == "timed out after 300s"


def test_get_fallback_events_returns_empty_outside_init():
    """Calling get_fallback_events with no active collector must return []."""
    _fallback_collector.set(None)
    assert get_fallback_events() == []


def test_record_fallback_no_op_outside_init():
    """record_fallback must not raise when called outside a pipeline run."""
    _fallback_collector.set(None)
    record_fallback("search", "model", "Error", "msg")  # must not raise


def test_record_fallback_accumulates_multiple_events():
    init_collector()
    record_fallback("search", "model-a", "RateLimit", "429")
    record_fallback("search", "model-b", "RateLimit", "429")
    record_fallback("writer", "model-a", "Timeout", "300s")
    events = get_fallback_events()
    assert len(events) == 3
    assert events[0].agent == "search"
    assert events[2].agent == "writer"


async def test_fallback_collector_isolated_per_async_context():
    """Two concurrent async tasks must not share the same _fallback_collector."""
    results: list = []

    async def task(agent_name: str) -> None:
        init_collector()
        await asyncio.sleep(0)  # yield to other task
        record_fallback(agent_name, "model", "Error", "e")
        results.append(list(get_fallback_events()))

    await asyncio.gather(task("task_a"), task("task_b"))
    agents_seen = {r[0].agent for r in results}
    assert agents_seen == {"task_a", "task_b"}
