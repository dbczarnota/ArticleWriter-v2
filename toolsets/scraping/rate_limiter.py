from __future__ import annotations
import asyncio

_semaphore: asyncio.Semaphore | None = None


def get_jina_semaphore(max_concurrent: int = 8) -> asyncio.Semaphore:
    """Return global Jina Reader semaphore — process-level singleton.

    max_concurrent=8 at avg 1s/request ≈ 480 RPM (free tier limit: 500 RPM).
    """
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(max_concurrent)
    return _semaphore


def reset_jina_semaphore() -> None:
    """Reset singleton — for test isolation only."""
    global _semaphore
    _semaphore = None
