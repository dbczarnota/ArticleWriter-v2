"""Postgres repository integration tests.

Skips gracefully when Docker isn't running — these tests should never break
the rest of the suite for missing Docker. Use `pytest -m "not requires_docker"`
to run everything else when you don't have Docker available.

Pattern:
- Session-scoped Postgres testcontainer with pgvector image
- Apply Alembic head migration once
- Each test gets its own DB transaction... actually for simplicity, full rollback
  via tearing down rows between tests
"""

from __future__ import annotations

import os

import pytest

# Disable testcontainers' Ryuk reaper sidecar — it tries to bind port 8080 and
# conflicts when other tests in the suite have left state around. Container
# cleanup still happens via the explicit `container.stop()` in the fixture.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

# Probe Docker once for the entire module. If it's missing/down, skip everything.
docker = pytest.importorskip("docker", reason="docker SDK not installed")
testcontainers_postgres = pytest.importorskip(
    "testcontainers.postgres", reason="testcontainers[postgres] not installed"
)

try:
    docker.from_env().ping()
    _docker_available = True
except Exception:
    _docker_available = False

pytestmark = [
    pytest.mark.requires_docker,
    pytest.mark.skipif(not _docker_available, reason="Docker daemon not reachable"),
]


@pytest.fixture(scope="session")
def postgres_url():
    """Spin up a temporary Postgres+pgvector container for the test session.

    We explicitly set the port (PostgresContainer default in some testcontainers
    versions guesses wrong) and use the standard postgres user/db so the URL
    parsing is predictable.
    """
    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer(
        "pgvector/pgvector:pg16",
        username="test",
        password="test",
        dbname="test",
        port=5432,
    )
    container.start()
    try:
        url = container.get_connection_url()
        # Container yields a psycopg URL; SQLAlchemy needs asyncpg driver.
        url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
        if "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://")
        yield url
    finally:
        container.stop()


@pytest.fixture(scope="session", autouse=True)
def apply_migrations(postgres_url):
    """Run alembic upgrade head against the test DB."""
    import os

    os.environ["DATABASE_URL"] = postgres_url
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", postgres_url)
    command.upgrade(cfg, "head")
    yield


@pytest.fixture
async def session_maker(postgres_url):
    """Yield an async_sessionmaker bound to the test container.

    Cleans tables between tests via cascade-deleting articles + orgs.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlmodel import delete

    engine = create_async_engine(postgres_url, echo=False)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    yield sm
    # Cleanup
    from backend.db.models import Article, Org

    async with sm() as s:
        await s.execute(delete(Article))
        await s.execute(delete(Org))
        await s.commit()
    await engine.dispose()


async def test_org_upsert_creates_then_updates(session_maker):
    from backend.repositories.postgres import PostgresOrgRepository

    repo = PostgresOrgRepository(session_maker)
    org = await repo.upsert_from_kinde(
        kinde_org_id="org_test1",
        code="org_test1",
        name="Test Org",
        domain_name="styl_fm",
    )
    assert org.code == "org_test1"
    assert org.name == "Test Org"

    # Update path
    org2 = await repo.upsert_from_kinde(
        kinde_org_id="org_test1",
        code="org_test1",
        name="Test Org Renamed",
        domain_name="styl_fm",
    )
    assert org2.name == "Test Org Renamed"

    fetched = await repo.get("org_test1")
    assert fetched is not None
    assert fetched.name == "Test Org Renamed"


async def test_article_lifecycle_create_complete_get(session_maker):
    from backend.db.models import Fact, Quote
    from backend.repositories.postgres import PostgresArticleRepository, PostgresOrgRepository

    org_repo = PostgresOrgRepository(session_maker)
    await org_repo.upsert_from_kinde(
        kinde_org_id="org_a",
        code="org_a",
        name="Org A",
        domain_name="styl_fm",
    )

    repo = PostgresArticleRepository(session_maker)
    article_id = await repo.create_running(
        org_code="org_a",
        author_user_id="user_1",
        domain_name="styl_fm",
        topic="Test topic",
    )
    assert article_id is not None

    # Complete with two facts and one quote
    fact = Fact(
        article_id=article_id,
        text="Fact text",
        context="ctx",
        source_url="https://a.example/1",
        source_title="A",
    )
    quote = Quote(
        article_id=article_id,
        text="Quote",
        speaker="X",
        context="ctx",
        source_url="https://a.example/1",
    )
    await repo.complete(
        article_id,
        html="<h1>Hello</h1>",
        alternative_titles=["Alt"],
        followup_topics=["FU"],
        sources=["https://a.example/1"],
        facts=[fact],
        quotes=[quote],
        embed_candidates=[],
        usage_events=[],
        fallback_events=[],
        pipeline_timing={"research": 100.0},
        errors=[],
        total_duration_ms=1234.5,
    )

    fetched = await repo.get(article_id, org_code="org_a")
    assert fetched is not None
    assert fetched.status == "done"
    assert fetched.html == "<h1>Hello</h1>"
    assert len(fetched.facts) == 1
    assert fetched.facts[0].text == "Fact text"
    assert len(fetched.quotes) == 1


async def test_article_tenant_isolation(session_maker):
    """Org A's article is invisible from Org B's repository view."""
    from backend.repositories.postgres import PostgresArticleRepository, PostgresOrgRepository

    org_repo = PostgresOrgRepository(session_maker)
    await org_repo.upsert_from_kinde(
        kinde_org_id="org_a", code="org_a", name="Org A", domain_name="styl_fm"
    )
    await org_repo.upsert_from_kinde(
        kinde_org_id="org_b", code="org_b", name="Org B", domain_name="styl_fm"
    )

    repo = PostgresArticleRepository(session_maker)
    a_id = await repo.create_running(
        org_code="org_a", author_user_id="u_a", domain_name="styl_fm", topic="A"
    )

    # Org B cannot see Org A's article — even with the right id.
    fetched = await repo.get(a_id, org_code="org_b")
    assert fetched is None

    # Org A can see it.
    fetched = await repo.get(a_id, org_code="org_a")
    assert fetched is not None

    # list_by_org also tenant-filters
    assert len(await repo.list_by_org(org_code="org_a")) == 1
    assert len(await repo.list_by_org(org_code="org_b")) == 0


async def test_mark_failed_records_status_and_detail(session_maker):
    from backend.repositories.postgres import PostgresArticleRepository, PostgresOrgRepository

    org_repo = PostgresOrgRepository(session_maker)
    await org_repo.upsert_from_kinde(
        kinde_org_id="org_x", code="org_x", name="Org X", domain_name="styl_fm"
    )

    repo = PostgresArticleRepository(session_maker)
    article_id = await repo.create_running(
        org_code="org_x", author_user_id="u", domain_name="styl_fm", topic="t"
    )
    await repo.mark_failed(
        article_id,
        error_status="insufficient_sources",
        errors=[{"stage": "search", "error": "Serper 401"}],
        insufficient_sources_detail={
            "facts_count": 0,
            "quotes_count": 0,
            "min_required": 4,
        },
    )
    fetched = await repo.get(article_id, org_code="org_x")
    assert fetched is not None
    assert fetched.status == "insufficient_sources"
    assert fetched.insufficient_sources_detail == {
        "facts_count": 0,
        "quotes_count": 0,
        "min_required": 4,
    }
