"""Smoke tests for PostgresDiscoveryRepository against a real Postgres
instance via testcontainers (mirrors test_repositories_postgres.py)."""

from __future__ import annotations

import os
from datetime import UTC

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")


import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from testcontainers.postgres import PostgresContainer

import backend.db.models  # noqa: F401  ensure metadata loaded

docker = pytest.importorskip("docker", reason="docker SDK not installed")

try:
    docker.from_env().ping()
    _docker_available = True
except Exception:
    _docker_available = False

pytestmark = [
    pytest.mark.requires_docker,
    pytest.mark.skipif(not _docker_available, reason="Docker daemon not reachable"),
]


@pytest_asyncio.fixture
async def session_maker():
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url().replace("psycopg2", "asyncpg")
        engine = create_async_engine(url, future=True)
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        await engine.dispose()


@pytest_asyncio.fixture
async def org(session_maker):
    from backend.db.models import Org

    o = Org(code="org_test", domain_name="test", name="Test Org")
    async with session_maker() as session:
        session.add(o)
        await session.commit()
        await session.refresh(o)
    return o


@pytest.mark.asyncio
async def test_upsert_feed_idempotent(session_maker, org):
    from backend.repositories.discovery import PostgresDiscoveryRepository

    repo = PostgresDiscoveryRepository(session_maker)
    f1 = await repo.upsert_feed(org_code=org.code, feed_url="https://example.com/rss")
    f2 = await repo.upsert_feed(org_code=org.code, feed_url="https://example.com/rss")
    assert f1.id == f2.id
    assert f1.feed_url == "https://example.com/rss"


@pytest.mark.asyncio
async def test_record_feed_run_resets_errors(session_maker, org):
    from backend.repositories.discovery import PostgresDiscoveryRepository

    repo = PostgresDiscoveryRepository(session_maker)
    f = await repo.upsert_feed(org_code=org.code, feed_url="https://example.com/rss")
    await repo.record_feed_error(f.id, error_message="boom")
    await repo.record_feed_error(f.id, error_message="boom")
    feeds = await repo.list_feeds_for_org(org.code)
    assert feeds[0].error_count == 2

    await repo.record_feed_run(
        f.id, last_etag='"abc"', last_modified="Wed, 21 Oct 2026 07:28:00 GMT"
    )
    feeds = await repo.list_feeds_for_org(org.code)
    assert feeds[0].error_count == 0
    assert feeds[0].last_etag == '"abc"'


@pytest.mark.asyncio
async def test_record_feed_error_disables_after_threshold(session_maker, org):
    from backend.repositories.discovery import PostgresDiscoveryRepository

    repo = PostgresDiscoveryRepository(session_maker)
    f = await repo.upsert_feed(org_code=org.code, feed_url="https://example.com/rss")
    for _ in range(10):
        await repo.record_feed_error(f.id, error_message="boom", disable_threshold=10)
    feeds = await repo.list_feeds_for_org(org.code)
    assert feeds[0].disabled is True


@pytest.mark.asyncio
async def test_reset_feed_errors_clears_disabled(session_maker, org):
    from backend.repositories.discovery import PostgresDiscoveryRepository

    repo = PostgresDiscoveryRepository(session_maker)
    f = await repo.upsert_feed(org_code=org.code, feed_url="https://example.com/rss")
    for _ in range(10):
        await repo.record_feed_error(f.id, error_message="boom", disable_threshold=10)
    await repo.reset_feed_errors(f.id)
    feeds = await repo.list_feeds_for_org(org.code)
    assert feeds[0].disabled is False
    assert feeds[0].error_count == 0


@pytest.mark.asyncio
async def test_upsert_item_then_get_by_url(session_maker, org):
    from backend.db.models import DiscoveryItem
    from backend.repositories.discovery import PostgresDiscoveryRepository

    repo = PostgresDiscoveryRepository(session_maker)
    item = DiscoveryItem(
        org_code=org.code,
        canonical_url="https://example.com/x",
        title="X",
        categories=["Sport"],
    )
    await repo.upsert_item(item)
    found = await repo.get_item_by_url(org_code=org.code, canonical_url="https://example.com/x")
    assert found is not None
    assert found.title == "X"
    assert found.categories == ["Sport"]


@pytest.mark.asyncio
async def test_add_item_to_feed_link_idempotent(session_maker, org):
    from backend.db.models import DiscoveryItem
    from backend.repositories.discovery import PostgresDiscoveryRepository

    repo = PostgresDiscoveryRepository(session_maker)
    feed = await repo.upsert_feed(org_code=org.code, feed_url="https://example.com/rss")
    item = DiscoveryItem(
        org_code=org.code, canonical_url="https://example.com/x", title="X", categories=[]
    )
    await repo.upsert_item(item)
    await repo.add_item_to_feed_link(item_id=item.id, feed_id=feed.id)
    await repo.add_item_to_feed_link(item_id=item.id, feed_id=feed.id)  # duplicate ignored


@pytest.mark.asyncio
async def test_create_topic_and_attach_unions_categories(session_maker, org):
    from backend.db.models import DiscoveryItem
    from backend.repositories.discovery import PostgresDiscoveryRepository

    repo = PostgresDiscoveryRepository(session_maker)
    topic = await repo.create_topic(
        org_code=org.code, title="T", blurb="B", categories=["Polityka"]
    )
    assert topic.categories == ["Polityka"]

    item = DiscoveryItem(
        org_code=org.code, canonical_url="https://e.com/1", title="X", categories=["Lokalne"]
    )
    await repo.upsert_item(item)
    updated = await repo.attach_item_to_topic(
        item_id=item.id, topic_id=topic.id, item_categories=["Lokalne"]
    )
    assert sorted(updated.categories) == ["Lokalne", "Polityka"]


@pytest.mark.asyncio
async def test_list_active_topics_honors_window(session_maker, org):
    from datetime import datetime as dt
    from datetime import timedelta as td

    from sqlalchemy import update as sqla_update

    from backend.db.models import DiscoveryTopic
    from backend.repositories.discovery import PostgresDiscoveryRepository

    repo = PostgresDiscoveryRepository(session_maker)
    fresh = await repo.create_topic(org_code=org.code, title="fresh", blurb="b", categories=[])
    stale = await repo.create_topic(org_code=org.code, title="stale", blurb="b", categories=[])

    # Push stale's last_activity_at back 10 days
    async with session_maker() as session:
        await session.execute(
            sqla_update(DiscoveryTopic)
            .where(DiscoveryTopic.id == stale.id)  # type: ignore[arg-type]
            .values(last_activity_at=dt.now(UTC) - td(days=10))
        )
        await session.commit()

    active = await repo.list_active_topics(org_code=org.code, window_days=3)
    assert {t.id for t in active} == {fresh.id}


@pytest.mark.asyncio
async def test_mark_topic_consumed_and_resurface(session_maker, org):
    from datetime import datetime as dt

    from backend.db.models import Article, DiscoveryItem
    from backend.repositories.discovery import PostgresDiscoveryRepository

    repo = PostgresDiscoveryRepository(session_maker)
    topic = await repo.create_topic(org_code=org.code, title="T", blurb="B", categories=[])

    # Pre-consume: 2 items
    async with session_maker() as session:
        article = Article(
            org_code=org.code,
            author_user_id="u1",
            domain_name="test",
            topic="T",
            status="done",
        )
        session.add(article)
        await session.commit()
        await session.refresh(article)

    for i in range(2):
        item = DiscoveryItem(
            org_code=org.code,
            canonical_url=f"https://e.com/{i}",
            title=f"X{i}",
            categories=[],
            topic_id=topic.id,
        )
        await repo.upsert_item(item)

    await repo.mark_topic_consumed(topic_id=topic.id, article_id=article.id, items_at_consume=2)

    # No new items yet
    flipped = await repo.check_resurface(topic_id=topic.id, threshold=3)
    assert flipped is False

    # Add 3 new items, pretend they were fetched after consumed_at
    later = dt.now(UTC)
    for i in range(2, 5):
        item = DiscoveryItem(
            org_code=org.code,
            canonical_url=f"https://e.com/{i}",
            title=f"X{i}",
            categories=[],
            topic_id=topic.id,
            fetched_at=later,
        )
        await repo.upsert_item(item)

    flipped = await repo.check_resurface(topic_id=topic.id, threshold=3)
    assert flipped is True
    found = await repo.get_topic(topic_id=topic.id, org_code=org.code)
    assert found is not None
    assert found.status == "resurfaced"


@pytest.mark.asyncio
async def test_list_topics_for_ui_filters(session_maker, org):
    from backend.repositories.discovery import PostgresDiscoveryRepository

    repo = PostgresDiscoveryRepository(session_maker)
    a = await repo.create_topic(org_code=org.code, title="A", blurb="b", categories=["Polityka"])
    b = await repo.create_topic(org_code=org.code, title="B", blurb="b", categories=["Sport"])
    c = await repo.create_topic(
        org_code=org.code, title="C", blurb="b", categories=["Polityka", "Sport"]
    )

    # filter by single category
    rows = await repo.list_topics_for_ui(org_code=org.code, categories=["Polityka"])
    assert {t.id for t in rows} == {a.id, c.id}

    # filter by multiple categories (OR)
    rows = await repo.list_topics_for_ui(org_code=org.code, categories=["Polityka", "Sport"])
    assert {t.id for t in rows} == {a.id, b.id, c.id}

    # filter by status
    await repo.dismiss_topic(topic_id=a.id, org_code=org.code)
    rows = await repo.list_topics_for_ui(org_code=org.code, statuses=["dismissed"])
    assert {t.id for t in rows} == {a.id}


@pytest.mark.asyncio
async def test_dismiss_then_restore(session_maker, org):
    from backend.repositories.discovery import PostgresDiscoveryRepository

    repo = PostgresDiscoveryRepository(session_maker)
    t = await repo.create_topic(org_code=org.code, title="T", blurb="b", categories=[])
    await repo.dismiss_topic(topic_id=t.id, org_code=org.code)
    fetched = await repo.get_topic(topic_id=t.id, org_code=org.code)
    assert fetched is not None and fetched.status == "dismissed"

    await repo.restore_topic(topic_id=t.id, org_code=org.code)
    fetched = await repo.get_topic(topic_id=t.id, org_code=org.code)
    assert fetched is not None and fetched.status == "open"


@pytest.mark.asyncio
async def test_list_items_for_topic_is_tenant_isolated(session_maker, org):
    """A topic_id from org_a must not leak items via org_b's repo call."""
    from backend.db.models import DiscoveryItem, Org
    from backend.repositories.discovery import PostgresDiscoveryRepository

    # Create a second org
    org_b = Org(code="org_other", domain_name="other", name="Other")
    async with session_maker() as session:
        session.add(org_b)
        await session.commit()

    repo = PostgresDiscoveryRepository(session_maker)
    topic = await repo.create_topic(org_code=org.code, title="T", blurb="b", categories=[])
    item = DiscoveryItem(
        org_code=org.code,
        canonical_url="https://e.com/x",
        title="X",
        categories=[],
        topic_id=topic.id,
    )
    await repo.upsert_item(item)

    # Same topic_id, but other org_code → empty result
    items = await repo.list_items_for_topic(topic_id=topic.id, org_code="org_other")
    assert items == []

    # Correct org_code → finds item
    items = await repo.list_items_for_topic(topic_id=topic.id, org_code=org.code)
    assert len(items) == 1


@pytest.mark.asyncio
async def test_list_topics_for_ui_org_filtered(session_maker, org):
    """Topics from another org never surface in our UI list."""
    from backend.db.models import Org
    from backend.repositories.discovery import PostgresDiscoveryRepository

    other = Org(code="other_org", domain_name="other", name="Other")
    async with session_maker() as session:
        session.add(other)
        await session.commit()

    repo = PostgresDiscoveryRepository(session_maker)
    mine = await repo.create_topic(org_code=org.code, title="mine", blurb="b", categories=[])
    theirs = await repo.create_topic(org_code="other_org", title="theirs", blurb="b", categories=[])

    rows = await repo.list_topics_for_ui(org_code=org.code)
    ids = {t.id for t in rows}
    assert mine.id in ids
    assert theirs.id not in ids


@pytest.mark.asyncio
async def test_try_acquire_feed_lock_basic(session_maker):
    """Lock acquisition succeeds for an unlocked feed_url."""
    from backend.repositories.discovery import PostgresDiscoveryRepository

    repo = PostgresDiscoveryRepository(session_maker)
    async with repo.try_acquire_feed_lock("https://example.com/rss") as acquired:
        assert acquired is True


@pytest.mark.asyncio
async def test_try_acquire_feed_lock_blocks_concurrent(session_maker):
    """A second concurrent attempt on the same feed_url returns False."""
    import asyncio

    from backend.repositories.discovery import PostgresDiscoveryRepository

    repo = PostgresDiscoveryRepository(session_maker)
    holder_started = asyncio.Event()
    holder_release = asyncio.Event()
    second_acquired: list[bool] = []

    async def hold_lock():
        async with repo.try_acquire_feed_lock("https://example.com/rss") as acquired:
            assert acquired is True
            holder_started.set()
            await holder_release.wait()

    holder_task = asyncio.create_task(hold_lock())
    await holder_started.wait()
    async with repo.try_acquire_feed_lock("https://example.com/rss") as acquired:
        second_acquired.append(acquired)
    holder_release.set()
    await holder_task
    assert second_acquired == [False]


@pytest.mark.asyncio
async def test_list_topics_for_ui_filters_by_feed_id(session_maker, org):
    from backend.db.models import DiscoveryItem
    from backend.repositories.discovery import PostgresDiscoveryRepository

    repo = PostgresDiscoveryRepository(session_maker)
    feed_a = await repo.upsert_feed(org_code=org.code, feed_url="https://a/rss")
    feed_b = await repo.upsert_feed(org_code=org.code, feed_url="https://b/rss")
    topic_a = await repo.create_topic(org_code=org.code, title="A", blurb="b", categories=[])
    topic_b = await repo.create_topic(org_code=org.code, title="B", blurb="b", categories=[])
    item_a = DiscoveryItem(
        org_code=org.code, canonical_url="https://a/x", title="x", topic_id=topic_a.id
    )
    item_a = await repo.upsert_item(item_a)
    item_b = DiscoveryItem(
        org_code=org.code, canonical_url="https://b/y", title="y", topic_id=topic_b.id
    )
    item_b = await repo.upsert_item(item_b)
    await repo.add_item_to_feed_link(item_id=item_a.id, feed_id=feed_a.id)
    await repo.add_item_to_feed_link(item_id=item_b.id, feed_id=feed_b.id)

    rows = await repo.list_topics_for_ui(org_code=org.code, feed_id=feed_a.id)
    assert {t.id for t in rows} == {topic_a.id}


@pytest.mark.asyncio
async def test_list_items_for_org_filters(session_maker, org):
    from backend.db.models import DiscoveryItem
    from backend.repositories.discovery import PostgresDiscoveryRepository

    repo = PostgresDiscoveryRepository(session_maker)
    feed_a = await repo.upsert_feed(org_code=org.code, feed_url="https://a/rss")
    feed_b = await repo.upsert_feed(org_code=org.code, feed_url="https://b/rss")
    item_a = await repo.upsert_item(
        DiscoveryItem(
            org_code=org.code,
            canonical_url="https://a/1",
            title="A",
            categories=["Polityka"],
        )
    )
    item_b = await repo.upsert_item(
        DiscoveryItem(
            org_code=org.code,
            canonical_url="https://b/1",
            title="B",
            categories=["Sport"],
        )
    )
    await repo.add_item_to_feed_link(item_id=item_a.id, feed_id=feed_a.id)
    await repo.add_item_to_feed_link(item_id=item_b.id, feed_id=feed_b.id)

    all_items = await repo.list_items_for_org(org_code=org.code)
    assert {it.id for it in all_items} == {item_a.id, item_b.id}

    by_feed = await repo.list_items_for_org(org_code=org.code, feed_id=feed_a.id)
    assert {it.id for it in by_feed} == {item_a.id}

    by_cat = await repo.list_items_for_org(org_code=org.code, categories=["Polityka"])
    assert {it.id for it in by_cat} == {item_a.id}
