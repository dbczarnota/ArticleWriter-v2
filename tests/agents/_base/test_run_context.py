# tests/agents/_base/test_run_context.py
import pytest
import asyncio
from agents._base.run_context import init_collector, record_agent_call, AgentCallRecord, _collector


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
