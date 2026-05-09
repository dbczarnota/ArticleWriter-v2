from __future__ import annotations

import asyncio

import pytest


@pytest.mark.asyncio
async def test_collect_chunk_reads_for_duration():
    """collect_chunk should stop reading after duration_s seconds."""
    from backend.services.stream_pipeline import collect_chunk

    reader = asyncio.StreamReader()

    async def _feed():
        for _ in range(1000):
            reader.feed_data(b"x" * 4096)
            await asyncio.sleep(0.001)

    feed_task = asyncio.create_task(_feed())
    data = await collect_chunk(reader, duration_s=0.05)
    feed_task.cancel()

    assert len(data) > 0


@pytest.mark.asyncio
async def test_collect_chunk_handles_eof():
    """collect_chunk returns what it got when stream closes early."""
    from backend.services.stream_pipeline import collect_chunk

    reader = asyncio.StreamReader()
    reader.feed_data(b"hello")
    reader.feed_eof()

    data = await collect_chunk(reader, duration_s=5.0)
    assert data == b"hello"
