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


_collector: contextvars.ContextVar[list[AgentCallRecord] | None] = contextvars.ContextVar(
    "_run_collector", default=None
)


def init_collector() -> list[AgentCallRecord]:
    """Create a fresh collector for this async context. Call once per pipeline run."""
    records: list[AgentCallRecord] = []
    _collector.set(records)
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
