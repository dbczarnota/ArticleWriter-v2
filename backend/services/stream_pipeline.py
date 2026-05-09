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
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import logfire
from sqlalchemy.ext.asyncio import AsyncSession

from agents.stream_analysis.agent import StreamChunkResult, run_stream_analysis_agent
from agents.stream_analysis.config import StreamAnalysisAgentConfig
from agents.stream_digest.agent import ChunkSummary, StreamDigestResult, run_stream_digest_agent
from agents.stream_digest.config import StreamDigestAgentConfig
from backend.database import get_db_backend, get_session_maker

_log = logging.getLogger(__name__)

_RECONNECT_DELAYS = [1.0, 2.0, 4.0, 8.0, 16.0]


async def collect_chunk(reader: asyncio.StreamReader, duration_s: float) -> bytes:
    """Read from reader for duration_s seconds, return accumulated bytes."""
    buf = io.BytesIO()
    loop = asyncio.get_running_loop()
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
        topic_transitions=[t.model_dump() for t in result.topic_transitions],
    )
    session.add(chunk)
    await session.commit()
    await session.refresh(chunk)
    return chunk.id


async def _save_digest(
    session: AsyncSession,
    subscription_id: UUID,
    digest: StreamDigestResult,
    chunk_count: int,
) -> UUID:
    from backend.db.models import StreamDigest

    record = StreamDigest(
        subscription_id=subscription_id,
        window_start_seconds=digest.window_start_seconds,
        window_end_seconds=digest.window_end_seconds,
        stories=[s.model_dump() for s in digest.stories],
        chunk_count=chunk_count,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record.id


def _write_report(subscription_id: UUID, digest: StreamDigestResult, digest_number: int) -> Path:
    """Write/overwrite a markdown report with the latest cumulative digest state."""
    path = Path(f"stream_report_{str(subscription_id)[:8]}.md")
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = [
        "# Raport nasłuchu strumienia",
        "",
        f"**Subskrypcja:** `{subscription_id}`  ",
        f"**Wygenerowano:** {ts}  ",
        f"**Digest nr:** {digest_number}  ",
        f"**Pokryty czas:** {digest.window_start_seconds:.0f}s – {digest.window_end_seconds:.0f}s "
        f"({(digest.window_end_seconds - digest.window_start_seconds) / 60:.1f} min)",
        "",
    ]

    # Collect all unique speakers across stories
    all_speakers: dict[str, str | None] = {}
    for story in digest.stories:
        for sp in story.speakers:
            if sp.name_or_role not in all_speakers:
                all_speakers[sp.name_or_role] = sp.description

    if all_speakers:
        lines += ["## Zidentyfikowani rozmówcy", ""]
        for name, desc in all_speakers.items():
            lines.append(f"- **{name}**" + (f" — {desc}" if desc else ""))
        lines.append("")

    lines += [f"## Tematy ({len(digest.stories)})", ""]

    for i, story in enumerate(digest.stories, 1):
        lines.append(f"### {i}. {story.title}")
        lines.append(f"*Czas: {story.start_seconds:.0f}s – {story.end_seconds:.0f}s*")
        lines.append("")

        if story.speakers:
            speakers_str = ", ".join(
                sp.name_or_role + (f" ({sp.description})" if sp.description else "")
                for sp in story.speakers
            )
            lines.append(f"**Uczestnicy:** {speakers_str}")
            lines.append("")

        if story.summary:
            lines.append(story.summary)
            lines.append("")

        if story.facts:
            lines.append("**Fakty:**")
            for f in story.facts:
                who = f" *[{f.speaker}]*" if f.speaker else ""
                lines.append(f"- {f.text}{who}")
            lines.append("")

        if story.quotes:
            lines.append("**Cytaty:**")
            for q in story.quotes:
                who = f" — *{q.speaker}*" if q.speaker else ""
                lines.append(f'> "{q.text}"{who}')
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


async def run_subscription_pipeline(
    subscription_id: UUID,
    stream_url: str,
    chunk_duration_seconds: int,
    org_code: str,
) -> None:
    """Long-running pipeline task for one subscription.

    Loops: connect FFmpeg → collect chunks → analyze → save → broadcast.
    Every digest_config.chunks_per_digest chunks, runs StreamDigestAgent with
    rolling context from last previous_digests_count runs.
    On FFmpeg failure: exponential backoff, up to 5 retries, then marks paused.
    Cancelled externally by StreamSessionManager.stop().
    """
    from backend.services.stream_manager import get_stream_manager

    analysis_config = StreamAnalysisAgentConfig()
    digest_config = StreamDigestAgentConfig()
    _db = get_db_backend() == "postgres"
    manager = get_stream_manager()

    chunk_start = 0.0
    chunk_count = 0
    digest_count = 0
    digest_buffer: list[ChunkSummary] = []
    digest_history: list[StreamDigestResult] = []
    attempt = 0
    proc: asyncio.subprocess.Process | None = None

    with logfire.span("stream.pipeline", subscription_id=str(subscription_id), org_code=org_code):
        while True:
            try:
                if proc is not None and proc.returncode is None:
                    proc.kill()
                    await proc.wait()
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
                        config=analysis_config,
                    )

                    chunk_id: UUID | None = None
                    if _db:
                        sm = get_session_maker()
                        async with sm() as session:  # type: ignore[union-attr]
                            chunk_id = await _save_chunk(
                                session, subscription_id, chunk_start, chunk_end, result
                            )

                    chunk_event = {
                        "type": "chunk",
                        "chunk_id": str(chunk_id) if chunk_id else None,
                        "chunk_start": chunk_start,
                        "chunk_end": chunk_end,
                        "speakers": [s.model_dump() for s in result.speakers],
                        "topics": [t.model_dump() for t in result.topics],
                        "facts": [f.model_dump() for f in result.facts],
                        "quotes": [q.model_dump() for q in result.quotes],
                        "topic_transitions": [t.model_dump() for t in result.topic_transitions],
                        "raw_transcript": result.raw_transcript,
                    }
                    await manager.broadcast(subscription_id, chunk_event)

                    digest_buffer.append(
                        ChunkSummary(
                            chunk_start=chunk_start,
                            chunk_end=chunk_end,
                            raw_transcript=result.raw_transcript or "",
                            speakers=[s.model_dump() for s in result.speakers],
                            topics=[t.model_dump() for t in result.topics],
                            facts=[f.model_dump() for f in result.facts],
                            quotes=[q.model_dump() for q in result.quotes],
                            topic_transitions=[t.model_dump() for t in result.topic_transitions],
                        )
                    )
                    chunk_count += 1
                    chunk_start = chunk_end

                    if chunk_count % digest_config.chunks_per_digest == 0:
                        window = list(digest_buffer)
                        digest_buffer.clear()
                        previous = digest_history[-digest_config.previous_digests_count :]

                        digest = await run_stream_digest_agent(
                            window,
                            config=digest_config,
                            previous_digests=previous if previous else None,
                        )
                        digest_count += 1
                        logfire.info(
                            "stream.digest",
                            subscription_id=str(subscription_id),
                            digest_number=digest_count,
                            stories=len(digest.stories),
                        )

                        digest_history.append(digest)

                        digest_id: UUID | None = None
                        if _db:
                            sm = get_session_maker()
                            async with sm() as session:  # type: ignore[union-attr]
                                digest_id = await _save_digest(
                                    session,
                                    subscription_id,
                                    digest,
                                    len(window),
                                )

                        report_path = _write_report(subscription_id, digest, digest_count)
                        _log.info("stream.report written to %s", report_path)

                        digest_event = {
                            "type": "digest",
                            "digest_id": str(digest_id) if digest_id else None,
                            "digest_number": digest_count,
                            "window_start": digest.window_start_seconds,
                            "window_end": digest.window_end_seconds,
                            "stories": [s.model_dump() for s in digest.stories],
                            "report_path": str(report_path),
                        }
                        await manager.broadcast(subscription_id, digest_event)

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
                    await _mark_paused(subscription_id)
                    return
                delay = _RECONNECT_DELAYS[attempt]
                attempt += 1
                await asyncio.sleep(delay)


async def _mark_paused(subscription_id: UUID) -> None:
    logfire.warn("stream.marked_paused", subscription_id=str(subscription_id))
    if get_db_backend() != "postgres":
        return
    from backend.db.models import StreamSubscription

    sm = get_session_maker()
    async with sm() as session:  # type: ignore[union-attr]
        sub = await session.get(StreamSubscription, subscription_id)
        if sub:
            sub.status = "paused"
            session.add(sub)
            await session.commit()
