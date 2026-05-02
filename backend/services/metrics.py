# backend/services/metrics.py
from __future__ import annotations

import logfire

_pipeline_runs = logfire.metric_counter(
    "articlewriter.pipeline.runs",
    unit="{run}",
    description="Total pipeline runs by domain and status",
)
_pipeline_duration = logfire.metric_histogram(
    "articlewriter.pipeline.duration_ms",
    unit="ms",
    description="Total pipeline run duration in milliseconds",
)
_stage_duration = logfire.metric_histogram(
    "articlewriter.stage.duration_ms",
    unit="ms",
    description="Per-stage duration in milliseconds",
)
_pipeline_errors = logfire.metric_counter(
    "articlewriter.pipeline.errors",
    unit="{error}",
    description="Pipeline stage errors by stage name",
)


def record_pipeline_run(domain: str, status: str, duration_ms: float) -> None:
    _pipeline_runs.add(1, {"domain": domain, "status": status})
    _pipeline_duration.record(duration_ms, {"domain": domain, "status": status})


def record_stage(stage: str, duration_ms: float, domain: str) -> None:
    _stage_duration.record(duration_ms, {"stage": stage, "domain": domain})


def record_error(stage: str) -> None:
    _pipeline_errors.add(1, {"stage": stage})
