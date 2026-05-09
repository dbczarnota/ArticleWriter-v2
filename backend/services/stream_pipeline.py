"""FFmpeg-based audio stream pipeline.

Pulls a live HTTP audio stream via FFmpeg subprocess, collects chunks
in memory, sends each to StreamAnalysisAgent, writes results to DB,
and broadcasts via StreamSessionManager SSE queues.

Intended to run as a long-lived asyncio.Task per StreamSubscription.
"""

from __future__ import annotations

import asyncio
import io
import logging
from uuid import UUID

import logfire
from sqlalchemy.ext.asyncio import AsyncSession

from agents.stream_analysis.agent import StreamChunkResult, run_stream_analysis_agent
from agents.stream_analysis.config import StreamAnalysisAgentConfig
from backend.database import get_session_maker

_log = logging.getLogger(__name__)

_RECONNECT_DELAYS = [1.0, 2.0, 4.0, 8.0, 16.0]


async def collect_chunk(reader: asyncio.StreamReader, duration_s: float) -> bytes:
    """Read from reader for duration_s seconds, return accumulated bytes."""
    buf = io.BytesIO()
    loop = asyncio.get_event_loop()
    deadline = loop.time() + duration_s
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            break
        try:
            data = await asyncio.wait_for(reader.read(4096), timeout=min(remaining, 2.0))
            if not data:
                break
            buf.write(data)
        except TimeoutError:
            break
    return buf.getvalue()


async def _run_ffmpeg(stream_url: str) -> asyncio.subprocess.Process:
    """Start FFmpeg subprocess pulling stream_url as mono 16kHz MP3 on stdout."""
    return await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-reconnect",
        "1",
        "-reconnect_streamed",
        "1",
        "-reconnect_delay_max",
        "5",
        "-i",
        stream_url,
        "-f",
        "mp3",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-loglevel",
        "error",
        "pipe:1",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )


async def _save_chunk(
    session: AsyncSession,
    subscription_id: UUID,
    chunk_start: float,
    chunk_end: float,
    result: StreamChunkResult,
) -> UUID:
    from backend.db.models import StreamChunk

    chunk = StreamChunk(
        subscription_id=subscription_id,
        chunk_start_seconds=chunk_start,
        chunk_end_seconds=chunk_end,
        raw_transcript=result.raw_transcript,
        speakers_detected=[s.model_dump() for s in result.speakers],
        topics=[t.model_dump() for t in result.topics],
        facts=[f.model_dump() for f in result.facts],
        quotes=[q.model_dump() for q in result.quotes],
    )
    session.add(chunk)
    await session.commit()
    await session.refresh(chunk)
    return chunk.id


async def run_subscription_pipeline(
    subscription_id: UUID,
    stream_url: str,
    chunk_duration_seconds: int,
    org_code: str,
) -> None:
    """Long-running pipeline task for one subscription.

    Loops: connect FFmpeg → collect chunks → analyze → save → broadcast.
    On FFmpeg failure: exponential backoff, up to 5 retries, then marks paused.
    Cancelled externally by StreamSessionManager.stop().
    """
    from backend.services.stream_manager import get_stream_manager

    config = StreamAnalysisAgentConfig()
    sm = get_session_maker()
    manager = get_stream_manager()

    chunk_start = 0.0
    attempt = 0
    proc: asyncio.subprocess.Process | None = None

    with logfire.span("stream.pipeline", subscription_id=str(subscription_id), org_code=org_code):
        while True:
            try:
                proc = await _run_ffmpeg(stream_url)
                assert proc.stdout is not None
                attempt = 0  # reset on successful connect
                logfire.info("stream.connected", subscription_id=str(subscription_id))

                while True:
                    audio = await collect_chunk(proc.stdout, chunk_duration_seconds)
                    if not audio:
                        logfire.warn("stream.empty_chunk", subscription_id=str(subscription_id))
                        break

                    chunk_end = chunk_start + chunk_duration_seconds
                    result = await run_stream_analysis_agent(
                        audio_bytes=audio,
                        chunk_start_seconds=chunk_start,
                        config=config,
                    )

                    chunk_id: UUID | None = None
                    if sm is not None:
                        async with sm() as session:
                            chunk_id = await _save_chunk(
                                session, subscription_id, chunk_start, chunk_end, result
                            )

                    event = {
                        "chunk_id": str(chunk_id) if chunk_id else None,
                        "chunk_start": chunk_start,
                        "chunk_end": chunk_end,
                        "speakers": [s.model_dump() for s in result.speakers],
                        "topics": [t.model_dump() for t in result.topics],
                        "facts": [f.model_dump() for f in result.facts],
                        "quotes": [q.model_dump() for q in result.quotes],
                        "raw_transcript": result.raw_transcript,
                    }
                    await manager.broadcast(subscription_id, event)
                    chunk_start = chunk_end

            except asyncio.CancelledError:
                if proc is not None and proc.returncode is None:
                    proc.kill()
                raise

            except Exception as exc:
                logfire.warn(
                    "stream.ffmpeg_error",
                    subscription_id=str(subscription_id),
                    error=str(exc),
                    attempt=attempt,
                )
                if attempt >= len(_RECONNECT_DELAYS):
                    await _mark_paused(subscription_id, sm)
                    return
                delay = _RECONNECT_DELAYS[attempt]
                attempt += 1
                await asyncio.sleep(delay)


async def _mark_paused(subscription_id: UUID, sm: object) -> None:
    if sm is None:
        return
    from backend.db.models import StreamSubscription

    async with sm() as session:  # type: ignore[attr-defined]
        sub = await session.get(StreamSubscription, subscription_id)
        if sub:
            sub.status = "paused"
            session.add(sub)
            await session.commit()
    logfire.warn("stream.marked_paused", subscription_id=str(subscription_id))
