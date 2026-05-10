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
from datetime import UTC, datetime, timedelta
from pathlib import Path
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
        stderr=asyncio.subprocess.DEVNULL,
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
            break
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


def _format_chunk_result_verbose(
    chunk_start: float,
    chunk_end: float,
    result: StreamChunkResult,
    chunk_start_at: datetime | None = None,
) -> str:
    """Human-readable representation of a chunk result for console and report."""
    if chunk_start_at:
        chunk_end_at = chunk_start_at + timedelta(seconds=chunk_end - chunk_start)
        header = f"### Chunk [{chunk_start_at.strftime('%H:%M:%S')} – {chunk_end_at.strftime('%H:%M:%S')}]"
    else:
        header = f"### Chunk {chunk_start:.0f}s–{chunk_end:.0f}s"
    lines = [header]
    if result.raw_transcript:
        lines.append(f"**Transkrypcja:** {result.raw_transcript[:400]}")
    if result.speakers:
        lines.append(
            "**Mówcy:** " + ", ".join(f"[{s.label}] {s.description}" for s in result.speakers)
        )
    if result.topic_transitions:
        lines.append("**Zmiany tematu:**")
        for tr in result.topic_transitions:
            if chunk_start_at:
                tr_at = chunk_start_at + timedelta(seconds=tr.timestamp_offset_seconds)
                lines.append(f"  - [{tr_at.strftime('%H:%M:%S')}] {tr.description}")
            else:
                lines.append(
                    f"  - [{chunk_start + tr.timestamp_offset_seconds:.0f}s] {tr.description}"
                )
    if result.topics:
        for t in result.topics:
            if chunk_start_at:
                t_start_at = chunk_start_at + timedelta(seconds=t.start_offset_seconds)
                t_end_at = (
                    chunk_start_at + timedelta(seconds=t.end_offset_seconds)
                    if t.end_offset_seconds is not None
                    else chunk_end_at  # type: ignore[possibly-undefined]
                )
                time_range = f"{t_start_at.strftime('%H:%M:%S')}–{t_end_at.strftime('%H:%M:%S')}"
            else:
                abs_start = chunk_start + t.start_offset_seconds
                abs_end = (
                    chunk_start + t.end_offset_seconds
                    if t.end_offset_seconds is not None
                    else chunk_end
                )
                time_range = f"{abs_start:.0f}s–{abs_end:.0f}s"
            lines.append(f"**Temat [{time_range}]:** {t.title} ({t.confidence:.0%})")
            for f in t.facts:
                who = f" [{f.speaker_label}]" if f.speaker_label else ""
                if chunk_start_at:
                    f_at = chunk_start_at + timedelta(seconds=f.timestamp_offset_seconds)
                    ts = f" @{f_at.strftime('%H:%M:%S')}"
                else:
                    ts = f" @{chunk_start + f.timestamp_offset_seconds:.0f}s"
                lines.append(f"  💡 {f.text}{who}{ts}")
            for q in t.quotes:
                who = f" [{q.speaker_label}]" if q.speaker_label else ""
                lines.append(f'  💬 "{q.text}"{who}')
    if not result.topics and not result.raw_transcript:
        lines.append("_(pusty chunk — muzyka/reklamy)_")
    return "\n".join(lines)


def _write_report(
    subscription_id: UUID,
    digest: StreamDigestResult,
    digest_number: int,
    chunk_log: list[str],
    digest_log: list[str],
) -> Path:
    """Write/overwrite a full flow markdown report."""
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
        "---",
        "",
        "## Flow: Wyniki Chunk Agenta",
        "",
    ]
    lines.extend(chunk_log)

    lines += ["", "---", "", "## Flow: Przebiegi Digest Agenta", ""]
    lines.extend(digest_log)

    lines += ["", "---", "", "## Aktualny Stan Tematów", ""]

    all_speakers: dict[str, str | None] = {}
    for story in digest.stories:
        for sp in story.speakers:
            if sp.name_or_role not in all_speakers:
                all_speakers[sp.name_or_role] = sp.description

    if all_speakers:
        lines += ["### Zidentyfikowani rozmówcy", ""]
        for name, desc in all_speakers.items():
            lines.append(f"- **{name}**" + (f" — {desc}" if desc else ""))
        lines.append("")

    news_count = sum(1 for s in digest.stories if s.is_news)
    lines += [f"### Tematy ({len(digest.stories)}, w tym newsów: {news_count})", ""]
    for i, story in enumerate(digest.stories, 1):
        news_badge = "📰 NEWS" if story.is_news else "💬 nie-news"
        lines.append(f"#### {i}. {story.title} `[{news_badge}]`")
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


async def _upsert_stream_topics(
    session: AsyncSession,
    subscription_id: UUID,
    digest: StreamDigestResult,
    now: datetime,
) -> None:
    from backend.db.models import StreamTopic

    for story in digest.stories:
        normalized_title = story.title.strip().lower()

        result = await session.execute(
            sa.select(StreamTopic).where(
                StreamTopic.subscription_id == subscription_id,  # type: ignore[arg-type]
                sa.func.lower(sa.func.trim(StreamTopic.title)) == normalized_title,  # type: ignore[arg-type]
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.is_news = story.is_news
            existing.summary = story.summary
            existing.speakers = [sp.model_dump() for sp in story.speakers]
            existing.facts = [f.model_dump() for f in story.facts]
            existing.quotes = [q.model_dump() for q in story.quotes]
            existing.window_end_seconds = story.end_seconds
            existing.last_seen_at = now
            session.add(existing)
        else:
            topic = StreamTopic(
                subscription_id=subscription_id,
                title=story.title,
                is_news=story.is_news,
                summary=story.summary,
                speakers=[sp.model_dump() for sp in story.speakers],
                facts=[f.model_dump() for f in story.facts],
                quotes=[q.model_dump() for q in story.quotes],
                window_start_seconds=story.start_seconds,
                window_end_seconds=story.end_seconds,
                first_seen_at=now,
                last_seen_at=now,
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
    chunk_log: list[str] = []
    digest_log: list[str] = []
    stream_started_at = datetime.now(UTC)
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

                    # Verbose console output
                    verbose_chunk = _format_chunk_result_verbose(
                        chunk_start, chunk_end, result, chunk_start_at
                    )
                    print(f"\n{'─' * 60}")
                    print(verbose_chunk)
                    chunk_log.append(verbose_chunk)
                    chunk_log.append("")

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

                        from agents.stream_digest.agent import (
                            _format_chunks,
                            _format_previous_digests,
                        )

                        digest_input_text = (
                            f"=== POPRZEDNIE DIGESRY ===\n\n{_format_previous_digests(previous)}\n\n"
                            f"=== NOWE CHUNKI ===\n\n{_format_chunks(window)}"
                        )

                        print(f"\n{'=' * 60}")
                        print(f"DIGEST #{digest_count + 1} — wejście do agenta:")
                        print(digest_input_text[:2000])
                        print("...")

                        now_utc = datetime.now(UTC)
                        historical_topics: list[TopicContext] = []
                        if _db:
                            sm = get_session_maker()
                            async with sm() as session:  # type: ignore[union-attr]
                                historical_topics = await _get_historical_topics(
                                    session,
                                    subscription_id,
                                    digest_config.topic_window_hours,
                                    now_utc,
                                )

                        digest = await run_stream_digest_agent(
                            window,
                            config=digest_config,
                            previous_digests=previous if previous else None,
                            historical_topics=historical_topics,
                        )
                        digest_count += 1

                        print(f"\nDIGEST #{digest_count} — wynik agenta:")
                        for s in digest.stories:
                            badge = "📰 NEWS" if s.is_news else "💬 nie-news"
                            print(
                                f"  [{s.start_seconds:.0f}s–{s.end_seconds:.0f}s] [{badge}] {s.title}"
                            )
                            for sp in s.speakers:
                                print(f"    Rozmówca: {sp.name_or_role}")
                            print(f"    Streszczenie: {s.summary}")

                        logfire.info(
                            "stream.digest",
                            subscription_id=str(subscription_id),
                            digest_number=digest_count,
                            stories=len(digest.stories),
                        )

                        digest_history.append(digest)

                        # Accumulate digest log for report
                        digest_log_entry = [
                            f"### Digest #{digest_count} "
                            f"({digest.window_start_seconds:.0f}s–{digest.window_end_seconds:.0f}s)",
                            "",
                            "**Wejście (chunki):**",
                            "",
                            "```",
                            digest_input_text[:3000],
                            "```"
                            if len(digest_input_text) <= 3000
                            else f"... [skrócono z {len(digest_input_text)} znaków]\n```",
                            "",
                            "**Wyjście (tematy):**",
                            "",
                        ]
                        for s in digest.stories:
                            digest_log_entry.append(
                                f"- **{s.title}** [{s.start_seconds:.0f}s–{s.end_seconds:.0f}s] — {s.summary}"
                            )
                        if not digest.stories:
                            digest_log_entry.append("_(brak tematów — muzyka/reklamy)_")
                        digest_log_entry.append("")
                        digest_log.extend(digest_log_entry)

                        digest_id: UUID | None = None
                        if _db:
                            sm = get_session_maker()
                            async with sm() as session:  # type: ignore[union-attr]
                                digest_id = await _save_digest(
                                    session, subscription_id, digest, len(window)
                                )
                            async with sm() as session:  # type: ignore[union-attr]
                                await _upsert_stream_topics(
                                    session, subscription_id, digest, datetime.now(UTC)
                                )

                        report_path = _write_report(
                            subscription_id,
                            digest,
                            digest_count,
                            list(chunk_log),
                            list(digest_log),
                        )
                        print(f"\n📄 Raport zapisany: {report_path}")

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
