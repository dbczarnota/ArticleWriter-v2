# tests/backend/test_metrics.py
from backend.services.metrics import (
    record_error,
    record_pipeline_run,
    record_stage,
)


def test_record_pipeline_run_does_not_raise():
    record_pipeline_run(domain="styl_fm", status="ok", duration_ms=1234.5)


def test_record_stage_does_not_raise():
    record_stage(stage="search", duration_ms=500.0, domain="styl_fm")


def test_record_error_does_not_raise():
    record_error(stage="scraping")
