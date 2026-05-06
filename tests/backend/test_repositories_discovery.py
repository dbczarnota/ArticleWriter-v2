"""Smoke tests for PostgresDiscoveryRepository against a real Postgres
instance via testcontainers (mirrors test_repositories_postgres.py)."""

from __future__ import annotations

import os

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

    await repo.record_feed_run(f.id, last_etag='"abc"', last_modified="Wed, 21 Oct 2026 07:28:00 GMT")
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
    item = DiscoveryItem(org_code=org.code, canonical_url="https://example.com/x", title="X", categories=[])
    await repo.upsert_item(item)
    await repo.add_item_to_feed_link(item_id=item.id, feed_id=feed.id)
    await repo.add_item_to_feed_link(item_id=item.id, feed_id=feed.id)  # duplicate ignored
