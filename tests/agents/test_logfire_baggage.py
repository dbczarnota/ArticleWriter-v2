"""Verify OpenTelemetry baggage set via logfire.set_baggage propagates to
nested spans automatically — including auto-instrumented spans."""

from __future__ import annotations

import logfire
from logfire.testing import TestExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor


def test_baggage_attributes_appear_on_nested_spans():
    """set_baggage(...) on the outer scope -> attributes on every inner span."""
    exporter = TestExporter()
    logfire.configure(
        send_to_logfire=False,
        additional_span_processors=[
            SimpleSpanProcessor(exporter),
        ],
        console=False,
    )

    with (
        logfire.set_baggage(article_id="abc-123", org_code="org_test"),
        logfire.span("outer"),
        logfire.span("inner"),
    ):
        pass

    spans = exporter.exported_spans_as_dict()
    assert len(spans) >= 2, f"expected outer+inner spans, got {len(spans)}"
    for span in spans:
        # Baggage values surface as span attributes prefixed with the key.
        attrs = span.get("attributes", {})
        assert attrs.get("article_id") == "abc-123", (
            f"span {span['name']!r} missing baggage article_id; attrs={attrs}"
        )
        assert attrs.get("org_code") == "org_test"
