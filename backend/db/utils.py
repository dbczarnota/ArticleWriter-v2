"""DB-layer utility helpers.

Single source for `utcnow()`. Repos and models previously each defined
their own `_utcnow()` returning `datetime.now(UTC)` — four identical
copies. Centralizing it makes future tz/precision adjustments a one-edit
change.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return the current UTC time as a tz-aware datetime."""
    return datetime.now(UTC)
