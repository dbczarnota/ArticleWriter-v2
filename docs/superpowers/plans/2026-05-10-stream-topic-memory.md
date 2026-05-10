# Stream Topic Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the digest agent a 6-hour persistent memory of topics (via `StreamTopic` DB table), and give the chunk agent accurate wall-clock timestamps so it can report when things happened in real time.

**Architecture:** `StreamTopic` is a DB table that stores the current state of each recognized topic for a subscription — upserted after every digest run (title-based matching). Before each digest the pipeline queries topics from the last 6 hours and passes them as `historical_topics` context to the digest agent alongside the fresh chunks. The chunk agent receives `chunk_start_at: datetime` so it can include real HH:MM timestamps in its analysis.

**Tech Stack:** Python 3.12, pydantic-ai, SQLModel + SQLAlchemy 2.0 async, Alembic, pytest-asyncio

---

## File Map

| File | What changes |
|------|-------------|
| `agents/stream_analysis/agent.py` | Add `chunk_start_at: datetime` param to `run_stream_analysis_agent` |
| `agents/stream_digest/agent.py` | Add `TopicContext` dataclass, `_format_historical_topics()`, `historical_topics` param |
| `agents/stream_digest/config.py` | Add `topic_window_hours: int = 6` |
| `backend/db/models.py` | Add `StreamTopic` SQLModel |
| `migrations/versions/d5e6f7a8b9c0_add_stream_topics.py` | New Alembic migration |
| `backend/services/stream_pipeline.py` | Track `stream_started_at`, pass `chunk_start_at`, query/upsert StreamTopics |
| `tests/agents/stream_analysis/test_agent.py` | Update for `chunk_start_at` param |
| `tests/agents/stream_digest/test_agent.py` | Update for `historical_topics` + `TopicContext` |

---

## Task 1: Wall-clock timestamps for the chunk agent

**Files:**
- Modify: `agents/stream_analysis/agent.py`
- Modify: `tests/agents/stream_analysis/test_agent.py`

The chunk agent currently only knows `chunk_start_seconds` (offset from stream start, e.g. 0, 120, 240…). We add `chunk_start_at: datetime` so it knows the real clock time and can say "at 14:35" instead of "at second 420".

- [ ] **Step 1: Update the test for the new param**

Open `tests/agents/stream_analysis/test_agent.py`. The test `test_run_stream_analysis_agent_returns_result` currently calls `run_stream_analysis_agent` without `chunk_start_at`. Add it:

```python
from datetime import UTC, datetime

# inside test_run_stream_analysis_agent_returns_result:
result = await run_stream_analysis_agent(
    audio_bytes=b"fake_audio",
    chunk_start_seconds=0.0,
    chunk_start_at=datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC),
    config=StreamAnalysisAgentConfig(),
)
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/agents/stream_analysis/test_agent.py -x -q
```
Expected: FAIL — `run_stream_analysis_agent() got an unexpected keyword argument 'chunk_start_at'`

- [ ] **Step 3: Add `chunk_start_at` to `run_stream_analysis_agent`**

In `agents/stream_analysis/agent.py`, change the function signature and user_prompt:

```python
from datetime import datetime

async def run_stream_analysis_agent(
    audio_bytes: bytes,
    chunk_start_seconds: float,
    *,
    chunk_start_at: datetime,
    config: StreamAnalysisAgentConfig,
) -> StreamChunkResult:
    """Analyze a single audio chunk. Returns StreamChunkResult. Soft-fails to empty result."""
    clock_str = chunk_start_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    user_prompt: list[Any] = [
        f"Fragment audio: {clock_str} (sekunda {chunk_start_seconds:.0f} od początku nasłuchu). Przeanalizuj:",
        BinaryContent(data=audio_bytes, media_type="audio/mp3"),
    ]
    # rest of function unchanged
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/agents/stream_analysis/ -x -q
```
Expected: all pass

- [ ] **Step 5: Commit**

```
git add agents/stream_analysis/agent.py tests/agents/stream_analysis/test_agent.py
git commit -m "feat(stream-analysis): add chunk_start_at datetime for wall-clock timestamps"
```

---

## Task 2: `StreamTopic` DB model + migration

**Files:**
- Modify: `backend/db/models.py`
- Create: `migrations/versions/d5e6f7a8b9c0_add_stream_topics.py`

`StreamTopic` stores the latest known state of a topic for a subscription. One row per topic; upserted after each digest (matched by normalized title).

- [ ] **Step 1: Add `StreamTopic` to `backend/db/models.py`**

Add after the `StreamDigest` class (at the end of the file). Follow the exact pattern of the existing stream models — no `from __future__ import annotations` at top of file (already noted in the file's comment).

```python
class StreamTopic(SQLModel, table=True):
    __tablename__ = "stream_topics"  # type: ignore[assignment]
    __table_args__ = (
        Index("ix_stream_topics_sub_last_seen", "subscription_id", "last_seen_at"),
    )

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    subscription_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("stream_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    title: str = Field(max_length=512)
    is_news: bool = Field(default=True)
    summary: str = Field(default="", sa_column=Column(String, nullable=False))
    speakers: list[dict] = Field(default_factory=list, sa_column=Column(JSONB))
    facts: list[dict] = Field(default_factory=list, sa_column=Column(JSONB))
    quotes: list[dict] = Field(default_factory=list, sa_column=Column(JSONB))
    window_start_seconds: float = Field(sa_column=Column(Float, nullable=False))
    window_end_seconds: float = Field(sa_column=Column(Float, nullable=False))
    first_seen_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )
    last_seen_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )
```

- [ ] **Step 2: Write the Alembic migration**

Create `migrations/versions/d5e6f7a8b9c0_add_stream_topics.py`:

```python
"""add stream_topics table

Revision ID: d5e6f7a8b9c0
Revises: a1b2c3d4e5f6
Create Date: 2026-05-10 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "d5e6f7a8b9c0"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stream_topics",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "subscription_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("stream_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("is_news", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("summary", sa.String(), nullable=False, server_default=""),
        sa.Column("speakers", JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("facts", JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("quotes", JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("window_start_seconds", sa.Float(), nullable=False),
        sa.Column("window_end_seconds", sa.Float(), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_stream_topics_sub_last_seen",
        "stream_topics",
        ["subscription_id", "last_seen_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_stream_topics_sub_last_seen", table_name="stream_topics")
    op.drop_table("stream_topics")
```

- [ ] **Step 3: Verify migration syntax (no DB needed)**

```
python -c "import migrations.versions.d5e6f7a8b9c0_add_stream_topics"
```
Expected: no import error

- [ ] **Step 4: Commit**

```
git add backend/db/models.py migrations/versions/d5e6f7a8b9c0_add_stream_topics.py
git commit -m "feat(stream): add StreamTopic model and migration"
```

---

## Task 3: `TopicContext` + historical topics in the digest agent

**Files:**
- Modify: `agents/stream_digest/agent.py`
- Modify: `agents/stream_digest/config.py`
- Modify: `tests/agents/stream_digest/test_agent.py`

The digest agent gets a new optional parameter `historical_topics: list[TopicContext] | None`. When provided, they are formatted as a "long-term memory" section before the previous digests.

- [ ] **Step 1: Add `topic_window_hours` to config**

In `agents/stream_digest/config.py`:

```python
@dataclass(frozen=True)
class StreamDigestAgentConfig(AgentConfig):
    model: str = "google-gla:gemini-flash-latest"
    fallback_models: tuple[str, ...] = ("google-gla:gemini-2.0-flash",)
    chunks_per_digest: int = 5
    previous_digests_count: int = 2
    topic_window_hours: int = 6
```

- [ ] **Step 2: Write a failing test for `TopicContext` import and historical_topics param**

Add to `tests/agents/stream_digest/test_agent.py`:

```python
def test_config_topic_window_hours():
    cfg = StreamDigestAgentConfig()
    assert cfg.topic_window_hours == 6


@pytest.mark.asyncio
async def test_run_stream_digest_agent_with_historical_topics():
    from agents.stream_digest.agent import TopicContext, run_stream_digest_agent

    topic = TopicContext(
        topic_id="aaaaaaaa-0000-0000-0000-000000000000",
        title="Wybory samorządowe",
        is_news=True,
        first_seen_at="2026-05-10 10:00 UTC",
        last_seen_at="2026-05-10 10:10 UTC",
        summary="Omówienie wyników wyborów.",
        speakers=[{"name_or_role": "Prezenter"}],
        facts=[{"text": "Frekwencja 45%", "speaker": None}],
        quotes=[],
        window_start_seconds=0.0,
        window_end_seconds=600.0,
    )

    chunks = [_make_chunk(600.0, 720.0)]

    mock_result = MagicMock()
    mock_result.output = StreamDigestResult(
        stories=[
            DigestStory(
                title="Wybory samorządowe",
                is_news=True,
                start_seconds=0.0,
                end_seconds=720.0,
                summary="Kontynuacja tematu wyborów.",
            )
        ],
        window_start_seconds=0.0,
        window_end_seconds=720.0,
    )
    mock_result.usage.return_value = MagicMock(input_tokens=200, output_tokens=80)

    with patch(
        "agents.stream_digest.agent.run_with_fallback",
        new=AsyncMock(return_value=(mock_result, "google-gla:gemini-flash-latest")),
    ):
        result = await run_stream_digest_agent(
            chunks,
            config=StreamDigestAgentConfig(),
            historical_topics=[topic],
        )

    assert len(result.stories) == 1
```

- [ ] **Step 3: Run test to verify it fails**

```
pytest tests/agents/stream_digest/test_agent.py::test_run_stream_digest_agent_with_historical_topics -x -q
```
Expected: FAIL — `cannot import name 'TopicContext'`

- [ ] **Step 4: Add `TopicContext` dataclass and `_format_historical_topics()` to the agent**

In `agents/stream_digest/agent.py`, add after the imports (before `_SYSTEM_PROMPT`):

```python
from dataclasses import dataclass as _dataclass


@_dataclass
class TopicContext:
    """Snapshot of a StreamTopic row — passed as long-term memory to the digest agent."""
    topic_id: str
    title: str
    is_news: bool
    first_seen_at: str
    last_seen_at: str
    summary: str
    speakers: list[dict]
    facts: list[dict]
    quotes: list[dict]
    window_start_seconds: float
    window_end_seconds: float
```

Add `_format_historical_topics()` after `_format_previous_digests()`:

```python
def _format_historical_topics(topics: list[TopicContext]) -> str:
    if not topics:
        return "(brak tematów z ostatnich godzin)"
    parts: list[str] = []
    for t in topics:
        news_flag = "📰 NEWS" if t.is_news else "💬 nie-news"
        speakers = ", ".join(sp.get("name_or_role", "?") for sp in t.speakers) or "nieznani"
        facts = "\n".join(f"    - {f.get('text', '')}" for f in t.facts) or "    brak"
        quotes = (
            "\n".join(
                f'    "{q.get("text", "")}"'
                + (f" [{q.get('speaker', '')}]" if q.get("speaker") else "")
                for q in t.quotes
            )
            or "    brak"
        )
        parts.append(
            f"  [{news_flag}] Temat: {t.title} [ID: {t.topic_id}]\n"
            f"  Czas w strumieniu: {t.window_start_seconds:.0f}s – {t.window_end_seconds:.0f}s\n"
            f"  Pierwsze pojawienie: {t.first_seen_at} | Ostatnie: {t.last_seen_at}\n"
            f"  Rozmówcy: {speakers}\n"
            f"  Streszczenie: {t.summary or '(brak)'}\n"
            f"  Fakty:\n{facts}\n"
            f"  Cytaty:\n{quotes}"
        )
    return "\n\n".join(parts)
```

- [ ] **Step 5: Add `historical_topics` param to `run_stream_digest_agent` and update user_prompt**

Change the function signature and user_prompt construction:

```python
async def run_stream_digest_agent(
    chunks: list[ChunkSummary],
    *,
    config: StreamDigestAgentConfig,
    previous_digests: list[StreamDigestResult] | None = None,
    historical_topics: list[TopicContext] | None = None,
) -> StreamDigestResult:
    """Aggregate N chunks into a digest of stories, optionally updating previous digests."""
    if not chunks and not previous_digests and not historical_topics:
        return StreamDigestResult()

    prev = previous_digests or []
    window_start = prev[0].window_start_seconds if prev else (chunks[0].chunk_start if chunks else 0.0)
    window_end = chunks[-1].chunk_end if chunks else (prev[-1].window_end_seconds if prev else 0.0)

    hist_section = _format_historical_topics(historical_topics or [])
    prev_section = _format_previous_digests(prev)
    chunks_section = _format_chunks(chunks) if chunks else "(brak nowych chunków)"

    user_prompt = (
        f"=== ZNANE TEMATY Z OSTATNICH GODZIN (pamięć długoterminowa) ===\n\n"
        f"{hist_section}\n\n"
        f"=== POPRZEDNIE DIGESRY (ostatnie przebiegi) ===\n\n"
        f"{prev_section}\n\n"
        f"=== NOWE CHUNKI DO PRZEANALIZOWANIA ({len(chunks)} chunków, "
        f"{window_start:.0f}s–{window_end:.0f}s) ===\n\n"
        f"{chunks_section}"
    )
    # rest of function unchanged
```

Also add a new section to `_SYSTEM_PROMPT` to explain the three sections. Insert before "## Kluczowa zasada: selekcja tematów newsowych" in the system prompt... wait, that's in the digest agent. Add at the very start of the system prompt, updating the existing "Otrzymujesz dwa rodzaje danych" section:

```python
# Replace the opening description in _SYSTEM_PROMPT:
"""
Jesteś redaktorem analizującym transkrypcje polskiego radia informacyjnego.

Otrzymujesz trzy rodzaje danych:
1. ZNANE TEMATY Z OSTATNICH GODZIN — pamięć długoterminowa (tematy z ostatnich 6h, z ID).
2. POPRZEDNIE DIGESRY — wyniki ostatnich 2 przebiegów tego agenta (szczegółowe).
3. NOWE CHUNKI — świeże fragmenty audio (~10 minut) z częściową analizą.

Traktuj ZNANE TEMATY jako punkt wyjścia — jeśli nowy materiał dotyczy już istniejącego \
tematu, zaktualizuj go zamiast tworzyć nowy. Jeśli nie ma historii, zacznij od zera.
"""
```

- [ ] **Step 6: Run tests**

```
pytest tests/agents/stream_digest/ -x -q
```
Expected: all pass

- [ ] **Step 7: Commit**

```
git add agents/stream_digest/agent.py agents/stream_digest/config.py tests/agents/stream_digest/test_agent.py
git commit -m "feat(stream-digest): add TopicContext historical_topics param for 6h memory"
```

---

## Task 4: Pipeline — track `stream_started_at`, pass `chunk_start_at`, query/upsert topics

**Files:**
- Modify: `backend/services/stream_pipeline.py`

This is the glue layer. Three changes:
1. Track `stream_started_at = datetime.now(UTC)` at pipeline start → compute `chunk_start_at` per chunk
2. Before each digest: query `StreamTopic` rows from last `topic_window_hours` for this subscription → build `list[TopicContext]`
3. After each digest: upsert digest stories into `StreamTopic` (match by normalized title)

No tests for `stream_pipeline.py` directly — the integration is verified by running the pipeline manually.

- [ ] **Step 1: Add `stream_started_at` and `chunk_start_at` to the pipeline**

In `run_subscription_pipeline`, right after `chunk_start = 0.0`:

```python
from datetime import timedelta

stream_started_at = datetime.now(UTC)
```

Then in the chunk processing loop, where `run_stream_analysis_agent` is called, add `chunk_start_at`:

```python
chunk_start_at = stream_started_at + timedelta(seconds=chunk_start)
result = await run_stream_analysis_agent(
    audio_bytes=audio,
    chunk_start_seconds=chunk_start,
    chunk_start_at=chunk_start_at,
    config=analysis_config,
)
```

- [ ] **Step 2: Add `_get_historical_topics()` helper**

Add this function to `stream_pipeline.py` (before `run_subscription_pipeline`):

```python
from agents.stream_digest.agent import TopicContext

async def _get_historical_topics(
    session: AsyncSession,
    subscription_id: UUID,
    window_hours: int,
) -> list[TopicContext]:
    from backend.db.models import StreamTopic

    cutoff = datetime.now(UTC) - timedelta(hours=window_hours)
    result = await session.execute(
        sa.select(StreamTopic)
        .where(
            StreamTopic.subscription_id == subscription_id,
            StreamTopic.last_seen_at >= cutoff,
        )
        .order_by(StreamTopic.last_seen_at.asc())
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
```

You need to add `import sqlalchemy as sa` to the imports at the top of the file.

- [ ] **Step 3: Add `_upsert_stream_topics()` helper**

Add after `_get_historical_topics`:

```python
async def _upsert_stream_topics(
    session: AsyncSession,
    subscription_id: UUID,
    digest: StreamDigestResult,
) -> None:
    from backend.db.models import StreamTopic

    now = datetime.now(UTC)
    for story in digest.stories:
        normalized_title = story.title.strip().lower()

        result = await session.execute(
            sa.select(StreamTopic).where(
                StreamTopic.subscription_id == subscription_id,
                sa.func.lower(sa.func.trim(StreamTopic.title)) == normalized_title,
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
```

- [ ] **Step 4: Wire up query + upsert into the digest trigger block**

In `run_subscription_pipeline`, find the `if chunk_count % digest_config.chunks_per_digest == 0:` block. Before calling `run_stream_digest_agent`, query historical topics. After the digest, upsert stories:

```python
# --- BEFORE run_stream_digest_agent ---
historical_topics: list[TopicContext] = []
if _db:
    sm = get_session_maker()
    async with sm() as session:  # type: ignore[union-attr]
        historical_topics = await _get_historical_topics(
            session, subscription_id, digest_config.topic_window_hours
        )

digest = await run_stream_digest_agent(
    window,
    config=digest_config,
    previous_digests=previous if previous else None,
    historical_topics=historical_topics if historical_topics else None,
)
digest_count += 1

# --- AFTER run_stream_digest_agent (after the existing print block) ---
if _db:
    sm = get_session_maker()
    async with sm() as session:  # type: ignore[union-attr]
        await _upsert_stream_topics(session, subscription_id, digest)
```

The `_upsert_stream_topics` call goes right before `_save_digest` (or after — order doesn't matter since they're independent commits).

- [ ] **Step 5: Run linter + type checker**

```
ruff check backend/services/stream_pipeline.py && ruff format --check backend/services/stream_pipeline.py && pyright backend/services/stream_pipeline.py
```

Fix any errors before committing.

- [ ] **Step 6: Run full test suite**

```
pytest -x -q
```
Expected: all pass (the pipeline helpers are not unit-tested; integration happens at runtime)

- [ ] **Step 7: Commit**

```
git add backend/services/stream_pipeline.py
git commit -m "feat(stream): persistent 6h topic memory — query before digest, upsert after"
```

---

## Self-Review

**Spec coverage:**
- ✅ Chunk agent gets wall-clock timestamps (`chunk_start_at`)
- ✅ Digest agent receives topics from last 6 hours (`historical_topics`)
- ✅ 6h window is configurable (`topic_window_hours` in config)
- ✅ Topics persist to DB (`StreamTopic` table + migration)
- ✅ Upsert logic: update existing topics, insert new ones

**Placeholder scan:** None found.

**Type consistency:**
- `TopicContext` defined in Task 3, imported in Task 4 ✅
- `StreamTopic` model defined in Task 2, used in Tasks 4 ✅
- `chunk_start_at: datetime` param added in Task 1, passed from pipeline in Task 4 ✅
- `historical_topics: list[TopicContext] | None` defined in Task 3, passed from pipeline in Task 4 ✅

**One edge case:** `_get_historical_topics` uses `sa.select` — needs `import sqlalchemy as sa` in `stream_pipeline.py`. Noted in Task 4 Step 2.

**Null-DB fallback:** When `_db` is False (no Postgres), `historical_topics` stays `[]` and `_upsert_stream_topics` is skipped. The agent still receives `previous_digests` for short-term context. Graceful.
