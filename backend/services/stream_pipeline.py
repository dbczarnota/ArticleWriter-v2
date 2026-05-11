"""FFmpeg-based audio stream pipeline.

Pulls a live HTTP audio stream via FFmpeg subprocess, collects chunks
in memory, sends each to StreamAnalysisAgent, writes results to DB,
and broadcasts via StreamSessionManager SSE queues.

Intended to run as a long-lived asyncio.Task per StreamSubscription.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import logfire
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from agents.stream_analysis.agent import StreamChunkResult, run_stream_analysis_agent
from agents.stream_analysis.config import StreamAnalysisAgentConfig
from agents.stream_digest.agent import (
    ChunkSummary,
    StreamDigestResult,
    TopicContext,
    run_stream_digest_agent,
)
from agents.stream_digest.config import StreamDigestAgentConfig
from backend.database import get_db_backend, get_session_maker

_log = logging.getLogger(__name__)

_RECONNECT_DELAYS = [1.0, 2.0, 4.0, 8.0, 16.0]


def _extract_field(data: Any, field_path: str) -> str:
    """Extract a value from a nested dict using dot-notation path (e.g. 'data.url')."""
    for key in field_path.split("."):
        if not isinstance(data, dict):
            raise ValueError(f"Expected dict at '{key}', got {type(data).__name__}")
        data = data[key]
    if not isinstance(data, str):
        raise ValueError(f"Expected str at '{field_path}', got {type(data).__name__}")
    return data


async def _resolve_stream_url(
    stream_url: str,
    url_refresh_url: str | None,
    url_refresh_headers: dict,
    url_refresh_field: str,
) -> str:
    """Return a fresh stream URL. If url_refresh_url is set, fetches it; otherwise returns stream_url as-is."""
    if not url_refresh_url:
        return stream_url
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url_refresh_url, headers=url_refresh_headers)
            resp.raise_for_status()
            return _extract_field(resp.json(), url_refresh_field)
    except Exception as exc:
        _log.warning("stream.url_refresh_failed: %s — falling back to stored URL", exc)
        return stream_url


async def _run_ffmpeg(stream_url: str, stream_type: str) -> asyncio.subprocess.Process:
    """Start FFmpeg subprocess. TV streams get -vn (skip video decoding)."""
    extra: list[str] = ["-vn"] if stream_type == "tv" else []
    hls_opts = ["-live_start_index", "-1"] if stream_url.endswith(".m3u8") else []
    return await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-reconnect",
        "1",
        "-reconnect_streamed",
        "1",
        "-reconnect_delay_max",
        "5",
        *hls_opts,
        "-i",
        stream_url,
        *extra,
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
        stderr=asyncio.subprocess.PIPE,
    )


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
            continue
    return buf.getvalue()


async def _save_chunk(
    session: AsyncSession,
    subscription_id: UUID,
    chunk_start: float,
    chunk_end: float,
    result: StreamChunkResult,
) -> UUID:
    from backend.db.models import StreamChunk

    # Flatten facts/quotes from nested topics for backward-compat columns
    all_facts = [f.model_dump() | {"topic_title": t.title} for t in result.topics for f in t.facts]
    all_quotes = [
        q.model_dump() | {"topic_title": t.title} for t in result.topics for q in t.quotes
    ]

    chunk = StreamChunk(
        subscription_id=subscription_id,
        chunk_start_seconds=chunk_start,
        chunk_end_seconds=chunk_end,
        raw_transcript=result.raw_transcript,
        speakers_detected=[s.model_dump() for s in result.speakers],
        topics=[t.model_dump() for t in result.topics],  # nested with facts/quotes
        facts=all_facts,
        quotes=all_quotes,
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




async def _get_historical_topics(
    session: AsyncSession,
    subscription_id: UUID,
    window_hours: int,
    now_utc: datetime,
) -> list[TopicContext]:
    from backend.db.models import StreamTopic

    cutoff = now_utc - timedelta(hours=window_hours)
    result = await session.execute(
        sa.select(StreamTopic)
        .where(
            StreamTopic.subscription_id == subscription_id,  # type: ignore[arg-type]
            StreamTopic.last_seen_at >= cutoff,  # type: ignore[operator]
        )
        .order_by(sa.asc(StreamTopic.last_seen_at))  # type: ignore[arg-type]
    )
    rows = result.scalars().all()
    return [
        TopicContext(
            topic_id=str(row.id),
            title=row.title,
            is_news=row.is_news,
            first_seen_at=row.first_seen_at.strftime("%Y-%m-%d %H:%M UTC"),
            last_seen_at=row.last_seen_at.strftime("%Y-%m-%d %H:%M UTC"),
            summary=row.summary,
            speakers=row.speakers,
            facts=row.facts,
            quotes=row.quotes,
            window_start_seconds=row.window_start_seconds,
            window_end_seconds=row.window_end_seconds,
        )
        for row in rows
    ]


def _story_window(story_start_s: float, story_end_s: float, now: datetime) -> dict:
    """Compute absolute {start_at, end_at} for a DigestStory using now ≈ digest time."""
    stream_start = now - timedelta(seconds=story_end_s)
    start_at = stream_start + timedelta(seconds=story_start_s)
    end_at = stream_start + timedelta(seconds=story_end_s)
    return {"start_at": start_at.isoformat(), "end_at": end_at.isoformat()}


async def _upsert_stream_topics(
    session: AsyncSession,
    subscription_id: UUID,
    digest: StreamDigestResult,
    now: datetime,
    stream_started_at: datetime | None = None,
) -> None:
    from backend.db.models import StreamTopic

    for story in digest.stories:
        survivor: StreamTopic | None = None
        merged = False
        # Per-story last_seen_at: when in the stream this topic actually ended,
        # so different stories in the same digest get different timestamps.
        # Falls back to now (digest processing time) if stream_started_at unknown.
        story_seen_at = (
            stream_started_at + timedelta(seconds=story.end_seconds)
            if stream_started_at is not None
            else now
        )

        if story.source_topic_ids:
            source_uuids = []
            for sid in story.source_topic_ids:
                try:
                    from uuid import UUID as _UUID
                    source_uuids.append(_UUID(sid))
                except ValueError:
                    continue

            if source_uuids:
                result = await session.execute(
                    sa.select(StreamTopic).where(
                        StreamTopic.subscription_id == subscription_id,  # type: ignore[arg-type]
                        StreamTopic.id.in_(source_uuids),  # type: ignore[attr-defined]
                    )
                )
                matched = list(result.scalars().all())
                if matched:
                    matched.sort(key=lambda r: r.first_seen_at)
                    survivor = matched[0]
                    # Collect windows from all sources before deleting duplicates
                    all_windows = list(survivor.windows or [])
                    orphaned_topic_ids: list = []
                    for duplicate in matched[1:]:
                        all_windows.extend(duplicate.windows or [])
                        if survivor.topic_id is None and duplicate.topic_id is not None:
                            # Survivor had no discovery link — inherit from duplicate
                            survivor.topic_id = duplicate.topic_id
                        elif (
                            duplicate.topic_id is not None
                            and duplicate.topic_id != survivor.topic_id
                        ):
                            # Both had different discovery topics — the duplicate's
                            # DiscoveryTopic will lose its only stream source. Queue
                            # it for cleanup if it has no RSS items.
                            orphaned_topic_ids.append(duplicate.topic_id)
                        await session.delete(duplicate)
                    # Clean up any DiscoveryTopics that are now orphaned (0 RSS items,
                    # 0 remaining stream sources after the delete above).
                    if orphaned_topic_ids:
                        import sqlalchemy as _sa

                        from backend.db.models import DiscoveryItem, DiscoveryTopic
                        for dtid in orphaned_topic_ids:
                            has_items = await session.scalar(
                                _sa.select(_sa.func.count()).select_from(DiscoveryItem).where(
                                    DiscoveryItem.topic_id == dtid  # type: ignore[arg-type]
                                )
                            )
                            has_stream = await session.scalar(
                                _sa.select(_sa.func.count()).select_from(StreamTopic).where(
                                    StreamTopic.topic_id == dtid  # type: ignore[arg-type]
                                )
                            )
                            if not has_items and not has_stream:
                                dt = await session.get(DiscoveryTopic, dtid)
                                if dt is not None:
                                    await session.delete(dt)
                    # Add the new window and sort
                    all_windows.append(_story_window(story.start_seconds, story.end_seconds, now))
                    all_windows.sort(key=lambda w: w["start_at"])
                    survivor.windows = all_windows
                    merged = True

        if survivor is None:
            normalized_title = story.title.strip().lower()
            result = await session.execute(
                sa.select(StreamTopic).where(
                    StreamTopic.subscription_id == subscription_id,  # type: ignore[arg-type]
                    sa.func.lower(sa.func.trim(StreamTopic.title)) == normalized_title,  # type: ignore[arg-type]
                )
            )
            survivor = result.scalar_one_or_none()

        if survivor is not None:
            survivor.title = story.title
            survivor.is_news = story.is_news
            survivor.summary = story.summary
            survivor.speakers = [sp.model_dump() for sp in story.speakers]
            survivor.facts = [f.model_dump() for f in story.facts]
            survivor.quotes = [q.model_dump() for q in story.quotes]
            survivor.window_start_seconds = story.start_seconds
            survivor.window_end_seconds = story.end_seconds
            survivor.last_seen_at = story_seen_at
            if not merged:
                # Simple update: extend last window or replace with current
                survivor.windows = [_story_window(story.start_seconds, story.end_seconds, now)]
            if merged:
                # Re-classify after merge — content changed significantly
                survivor.classified_at = None
            session.add(survivor)
        else:
            topic = StreamTopic(
                subscription_id=subscription_id,
                title=story.title,
                is_news=story.is_news,
                summary=story.summary,
                speakers=[sp.model_dump() for sp in story.speakers],
                facts=[f.model_dump() for f in story.facts],
                quotes=[q.model_dump() for q in story.quotes],
                categories=[],
                classified_at=None,
                windows=[_story_window(story.start_seconds, story.end_seconds, now)],
                window_start_seconds=story.start_seconds,
                window_end_seconds=story.end_seconds,
                first_seen_at=story_seen_at,
                last_seen_at=story_seen_at,
            )
            session.add(topic)

    await session.commit()


async def run_subscription_pipeline(
    subscription_id: UUID,
    stream_url: str,
    chunk_duration_seconds: int,
    org_code: str,
    *,
    stream_type: str = "radio",
    url_refresh_url: str | None = None,
    url_refresh_headers: dict | None = None,
    url_refresh_field: str = "url",
    topic_merge_window_hours: int = 6,
) -> None:
    """Long-running pipeline task for one subscription."""
    from backend.services.stream_manager import get_stream_manager

    analysis_config = StreamAnalysisAgentConfig()
    digest_config = StreamDigestAgentConfig()
    _db = get_db_backend() == "postgres"
    manager = get_stream_manager()
    _refresh_headers = url_refresh_headers or {}

    chunk_start = 0.0
    chunk_count = 0
    digest_count = 0
    digest_buffer: list[ChunkSummary] = []
    digest_history: list[StreamDigestResult] = []
    stream_started_at = datetime.now().astimezone()
    attempt = 0
    proc: asyncio.subprocess.Process | None = None

    with logfire.span("stream.pipeline", subscription_id=str(subscription_id), org_code=org_code):
        while True:
            try:
                if proc is not None and proc.returncode is None:
                    proc.kill()
                    await proc.wait()
                active_url = await _resolve_stream_url(
                    stream_url, url_refresh_url, _refresh_headers, url_refresh_field
                )
                proc = await _run_ffmpeg(active_url, stream_type)
                assert proc.stdout is not None
                attempt = 0
                logfire.info("stream.connected", subscription_id=str(subscription_id))

                while True:
                    audio = await collect_chunk(proc.stdout, chunk_duration_seconds)
                    if not audio:
                        logfire.warn("stream.empty_chunk", subscription_id=str(subscription_id))
                        break

                    chunk_end = chunk_start + chunk_duration_seconds
                    chunk_start_at = stream_started_at + timedelta(seconds=chunk_start)
                    result = await run_stream_analysis_agent(
                        audio_bytes=audio,
                        chunk_start_seconds=chunk_start,
                        chunk_start_at=chunk_start_at,
                        stream_type=stream_type,
                        config=analysis_config,
                    )

                    chunk_id: UUID | None = None
                    if _db:
                        sm = get_session_maker()
                        async with sm() as session:  # type: ignore[union-attr]
                            chunk_id = await _save_chunk(
                                session, subscription_id, chunk_start, chunk_end, result
                            )

                    chunk_end_at = chunk_start_at + timedelta(seconds=chunk_duration_seconds)
                    chunk_event = {
                        "type": "chunk",
                        "chunk_id": str(chunk_id) if chunk_id else None,
                        "chunk_start": chunk_start,
                        "chunk_end": chunk_end,
                        "chunk_start_at": chunk_start_at.isoformat(),
                        "chunk_end_at": chunk_end_at.isoformat(),
                        "speakers": [s.model_dump() for s in result.speakers],
                        "topics": [t.model_dump() for t in result.topics],
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
                            topic_transitions=[t.model_dump() for t in result.topic_transitions],
                        )
                    )
                    chunk_count += 1
                    chunk_start = chunk_end

                    if chunk_count % digest_config.chunks_per_digest == 0:
                        window = list(digest_buffer)
                        digest_buffer.clear()
                        previous = digest_history[-digest_config.previous_digests_count :]

                        now_utc = datetime.now(UTC)
                        historical_topics: list[TopicContext] = []
                        if _db:
                            sm = get_session_maker()
                            async with sm() as session:  # type: ignore[union-attr]
                                historical_topics = await _get_historical_topics(
                                    session,
                                    subscription_id,
                                    topic_merge_window_hours,
                                    now_utc,
                                )

                        digest = await run_stream_digest_agent(
                            window,
                            config=digest_config,
                            previous_digests=previous if previous else None,
                            historical_topics=historical_topics,
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
                                    session, subscription_id, digest, len(window)
                                )
                            async with sm() as session:  # type: ignore[union-attr]
                                await _upsert_stream_topics(
                                    session, subscription_id, digest, datetime.now(UTC),
                                    stream_started_at=stream_started_at,
                                )

                        digest_event = {
                            "type": "digest",
                            "digest_id": str(digest_id) if digest_id else None,
                            "digest_number": digest_count,
                            "window_start": digest.window_start_seconds,
                            "window_end": digest.window_end_seconds,
                            "stories": [s.model_dump() for s in digest.stories],
                        }
                        await manager.broadcast(subscription_id, digest_event)

            except asyncio.CancelledError:
                if proc is not None and proc.returncode is None:
                    proc.kill()
                raise

            except Exception as exc:
                stderr_out = b""
                if proc is not None and proc.stderr is not None:
                    with contextlib.suppress(Exception):
                        stderr_out = await asyncio.wait_for(proc.stderr.read(2048), timeout=1.0)
                _log.error(
                    "stream.ffmpeg_error [sub=%s attempt=%d]: %s: %r%s",
                    subscription_id,
                    attempt,
                    type(exc).__name__,
                    exc,
                    f" | ffmpeg: {stderr_out.decode(errors='replace').strip()}" if stderr_out else "",
                )
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
