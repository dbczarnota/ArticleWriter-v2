# agents/_base/run_context.py
from __future__ import annotations

import contextvars
from dataclasses import dataclass


@dataclass
class AgentCallRecord:
    agent: str
    model: str
    input_tokens: int
    output_tokens: int
    duration_ms: float


@dataclass
class FallbackEvent:
    agent: str
    failed_model: str
    error_type: str
    error_message: str


_collector: contextvars.ContextVar[list[AgentCallRecord] | None] = contextvars.ContextVar(
    "_run_collector", default=None
)

_fallback_collector: contextvars.ContextVar[list[FallbackEvent] | None] = contextvars.ContextVar(
    "_fallback_collector", default=None
)

_serper_counter: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar(
    "_serper_counter", default=None
)


def init_collector() -> list[AgentCallRecord]:
    """Create fresh collectors for this async context. Call once per pipeline run."""
    records: list[AgentCallRecord] = []
    _collector.set(records)
    fallback_records: list[FallbackEvent] = []
    _fallback_collector.set(fallback_records)
    _serper_counter.set([])
    return records


def record_agent_call(
    agent: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: float,
) -> None:
    """Append one LLM-call record. No-op when called outside a pipeline run."""
    records = _collector.get()
    if records is not None:
        records.append(AgentCallRecord(agent, model, input_tokens, output_tokens, duration_ms))


def record_fallback(agent: str, failed_model: str, error_type: str, error_message: str) -> None:
    """Record a failed model attempt. No-op when called outside a pipeline run."""
    records = _fallback_collector.get()
    if records is not None:
        records.append(FallbackEvent(agent, failed_model, error_type, error_message))


def get_fallback_events() -> list[FallbackEvent]:
    """Return all fallback events recorded in this async context."""
    return _fallback_collector.get() or []


def record_serper_query(endpoint: str) -> None:
    """Count one Serper API call. No-op outside a pipeline context."""
    queries = _serper_counter.get()
    if queries is not None:
        queries.append(endpoint)


def get_serper_queries() -> list[str]:
    """Return all Serper endpoints called in this async context."""
    return _serper_counter.get() or []
