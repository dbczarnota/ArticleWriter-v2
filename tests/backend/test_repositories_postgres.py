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
    org = await repo.create_from_jwt(code="org_test1", name="Test Org")
    assert org.code == "org_test1"
    assert org.name == "Test Org"
    assert org.domain_name == "org_test1"  # auto-mapped to code
    assert org.kinde_org_id == "org_test1"

    # Idempotent: second call with a different name returns the existing row
    # unchanged. Names are user-owned via Settings UI.
    org2 = await repo.create_from_jwt(code="org_test1", name="Renamed In Kinde")
    assert org2.name == "Test Org"

    fetched = await repo.get("org_test1")
    assert fetched is not None
    assert fetched.name == "Test Org"


async def test_article_lifecycle_create_complete_get(session_maker):
    from backend.db.models import Fact, Quote
    from backend.repositories.postgres import PostgresArticleRepository, PostgresOrgRepository

    org_repo = PostgresOrgRepository(session_maker)
    await org_repo.create_from_jwt(code="org_a", name="Org A")

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
    await org_repo.create_from_jwt(code="org_a", name="Org A")
    await org_repo.create_from_jwt(code="org_b", name="Org B")

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
    await org_repo.create_from_jwt(code="org_x", name="Org X")

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


async def test_orgconfig_create_default_inserts_row_with_model_defaults(session_maker):
    from backend.repositories.postgres import (
        PostgresOrgConfigRepository,
        PostgresOrgRepository,
    )

    org_repo = PostgresOrgRepository(session_maker)
    await org_repo.create_from_jwt(code="org_cfg_new", name="New")

    cfg_repo = PostgresOrgConfigRepository(session_maker)
    cfg = await cfg_repo.create_default("org_cfg_new")
    assert cfg.org_code == "org_cfg_new"
    assert cfg.language == "pl"
    assert cfg.target_word_count == 600
    # Polish onboarding defaults — non-empty so the writer can produce
    # something usable on the very first article without manual setup.
    assert "Wytyczne redakcyjne" in cfg.guidelines
    assert "<h1>" in cfg.html_format
    assert cfg.description.startswith("Polski portal")

    fetched = await cfg_repo.get("org_cfg_new")
    assert fetched is not None
    assert fetched.org_code == "org_cfg_new"


async def test_orgconfig_create_default_is_idempotent(session_maker):
    from backend.repositories.postgres import (
        PostgresOrgConfigRepository,
        PostgresOrgRepository,
    )

    org_repo = PostgresOrgRepository(session_maker)
    await org_repo.create_from_jwt(code="org_cfg_idem", name="Idem")

    cfg_repo = PostgresOrgConfigRepository(session_maker)
    first = await cfg_repo.create_default("org_cfg_idem")

    # Mutate via upsert: a second create_default must not overwrite.
    first.guidelines = "user-edited"
    await cfg_repo.upsert(first)

    second = await cfg_repo.create_default("org_cfg_idem")
    assert second.guidelines == "user-edited"


async def test_create_running_emits_article_created_event(session_maker, monkeypatch):
    from unittest.mock import MagicMock

    import logfire

    from backend.repositories.postgres import (
        PostgresArticleRepository,
        PostgresOrgRepository,
    )

    org_repo = PostgresOrgRepository(session_maker)
    await org_repo.create_from_jwt(code="org_evt1", name="Org Evt1")

    info_mock = MagicMock()
    monkeypatch.setattr(logfire, "info", info_mock)

    repo = PostgresArticleRepository(session_maker)
    await repo.create_running(
        org_code="org_evt1",
        author_user_id="user_x",
        author_email="x@example.com",
        author_name="X",
        domain_name="org_evt1",
        topic="Hello world topic",
    )

    info_mock.assert_called_once()
    args, kwargs = info_mock.call_args
    assert args[0] == "article.created"
    assert kwargs["org_code"] == "org_evt1"
    assert kwargs["topic_length"] == len("Hello world topic")
    assert kwargs["has_urls"] is False
    assert kwargs["has_instructions"] is False


async def test_complete_done_emits_article_completed_event(session_maker, monkeypatch):
    from unittest.mock import MagicMock

    import logfire

    from backend.repositories.postgres import (
        PostgresArticleRepository,
        PostgresOrgRepository,
    )

    org_repo = PostgresOrgRepository(session_maker)
    await org_repo.create_from_jwt(code="org_evt2", name="Org Evt2")

    repo = PostgresArticleRepository(session_maker)
    article_id = await repo.create_running(
        org_code="org_evt2",
        author_user_id="u",
        domain_name="org_evt2",
        topic="t",
    )

    info_mock = MagicMock()
    monkeypatch.setattr(logfire, "info", info_mock)

    await repo.complete(
        article_id,
        status="done",
        html="<h1>x</h1>",
        alternative_titles=[],
        followup_topics=[],
        sources=[],
        facts=[],
        quotes=[],
        embed_candidates=[],
        usage_events=[],
        fallback_events=[],
        pipeline_timing={},
        errors=[],
        total_duration_ms=42.0,
    )

    info_mock.assert_called_once()
    args, kwargs = info_mock.call_args
    assert args[0] == "article.completed"
    assert kwargs["status"] == "done"
    assert kwargs["duration_ms"] == 42.0
    assert kwargs["facts_count"] == 0
    assert kwargs["tokens_total"] == 0


async def test_complete_failed_status_emits_article_failed_event(session_maker, monkeypatch):
    from unittest.mock import MagicMock

    import logfire

    from backend.repositories.postgres import (
        PostgresArticleRepository,
        PostgresOrgRepository,
    )

    org_repo = PostgresOrgRepository(session_maker)
    await org_repo.create_from_jwt(code="org_evt3", name="Org Evt3")

    repo = PostgresArticleRepository(session_maker)
    article_id = await repo.create_running(
        org_code="org_evt3", author_user_id="u", domain_name="org_evt3", topic="t"
    )

    info_mock = MagicMock()
    monkeypatch.setattr(logfire, "info", info_mock)

    await repo.complete(
        article_id,
        status="failed",
        html="",
        alternative_titles=[],
        followup_topics=[],
        sources=[],
        facts=[],
        quotes=[],
        embed_candidates=[],
        usage_events=[],
        fallback_events=[],
        pipeline_timing={},
        errors=[{"stage": "writer", "error": "boom"}],
        total_duration_ms=10.0,
    )

    info_mock.assert_called_once()
    args, kwargs = info_mock.call_args
    assert args[0] == "article.failed"
    assert kwargs["status"] == "failed"
    assert kwargs["errors_count"] == 1


async def test_mark_failed_emits_article_failed_event(session_maker, monkeypatch):
    from unittest.mock import MagicMock

    import logfire

    from backend.repositories.postgres import (
        PostgresArticleRepository,
        PostgresOrgRepository,
    )

    org_repo = PostgresOrgRepository(session_maker)
    await org_repo.create_from_jwt(code="org_evt4", name="Org Evt4")

    repo = PostgresArticleRepository(session_maker)
    article_id = await repo.create_running(
        org_code="org_evt4", author_user_id="u", domain_name="org_evt4", topic="t"
    )

    warn_mock = MagicMock()
    monkeypatch.setattr(logfire, "warn", warn_mock)

    await repo.mark_failed(
        article_id,
        error_status="insufficient_sources",
        errors=[{"stage": "search", "error": "boom"}],
        insufficient_sources_detail={"facts_count": 0, "quotes_count": 0, "min_required": 4},
    )

    warn_mock.assert_called_once()
    args, kwargs = warn_mock.call_args
    assert args[0] == "article.failed"
    assert kwargs["error_status"] == "insufficient_sources"
    assert kwargs["errors_count"] == 1
    assert kwargs["has_insufficient_sources_detail"] is True


async def test_set_marked_done_emits_article_marked_done_event(session_maker, monkeypatch):
    from unittest.mock import MagicMock

    import logfire

    from backend.repositories.postgres import (
        PostgresArticleRepository,
        PostgresOrgRepository,
    )

    org_repo = PostgresOrgRepository(session_maker)
    await org_repo.create_from_jwt(code="org_evt5", name="Org Evt5")

    repo = PostgresArticleRepository(session_maker)
    article_id = await repo.create_running(
        org_code="org_evt5", author_user_id="u", domain_name="org_evt5", topic="t"
    )

    info_mock = MagicMock()
    monkeypatch.setattr(logfire, "info", info_mock)

    await repo.set_marked_done(
        article_id,
        org_code="org_evt5",
        marked_done=True,
        marked_done_by_name="Editor",
    )

    info_mock.assert_called_once()
    args, kwargs = info_mock.call_args
    assert args[0] == "article.marked_done"
    assert kwargs["marked_done"] is True
    assert kwargs["marked_done_by_name"] == "Editor"


async def test_create_from_jwt_first_call_emits_org_bootstrapped(session_maker, monkeypatch):
    from unittest.mock import MagicMock

    import logfire

    from backend.repositories.postgres import PostgresOrgRepository

    info_mock = MagicMock()
    monkeypatch.setattr(logfire, "info", info_mock)

    repo = PostgresOrgRepository(session_maker)
    await repo.create_from_jwt(code="org_boot1", name="Bootstrapped")

    info_mock.assert_called_once()
    assert info_mock.call_args[0][0] == "org.bootstrapped"
    assert info_mock.call_args[1]["code"] == "org_boot1"
    assert info_mock.call_args[1]["name"] == "Bootstrapped"


async def test_create_from_jwt_idempotent_does_not_re_emit(session_maker, monkeypatch):
    from unittest.mock import MagicMock

    import logfire

    from backend.repositories.postgres import PostgresOrgRepository

    repo = PostgresOrgRepository(session_maker)
    await repo.create_from_jwt(code="org_boot2", name="First")

    info_mock = MagicMock()
    monkeypatch.setattr(logfire, "info", info_mock)

    # Second call should be idempotent and emit nothing.
    await repo.create_from_jwt(code="org_boot2", name="Different")

    info_mock.assert_not_called()


async def test_set_domain_name_emits_org_domain_renamed(session_maker, monkeypatch):
    from unittest.mock import MagicMock

    import logfire

    from backend.repositories.postgres import PostgresOrgRepository

    repo = PostgresOrgRepository(session_maker)
    await repo.create_from_jwt(code="org_rn1", name="N")

    info_mock = MagicMock()
    monkeypatch.setattr(logfire, "info", info_mock)

    await repo.set_domain_name("org_rn1", "new_name")

    info_mock.assert_called_once()
    assert info_mock.call_args[0][0] == "org.domain_renamed"
    assert info_mock.call_args[1]["code"] == "org_rn1"
    assert info_mock.call_args[1]["old_domain_name"] == "org_rn1"
    assert info_mock.call_args[1]["new_domain_name"] == "new_name"


async def test_create_default_first_call_emits_event(session_maker, monkeypatch):
    from unittest.mock import MagicMock

    import logfire

    from backend.repositories.postgres import (
        PostgresOrgConfigRepository,
        PostgresOrgRepository,
    )

    org_repo = PostgresOrgRepository(session_maker)
    await org_repo.create_from_jwt(code="org_cfg_evt", name="O")

    info_mock = MagicMock()
    monkeypatch.setattr(logfire, "info", info_mock)

    cfg_repo = PostgresOrgConfigRepository(session_maker)
    await cfg_repo.create_default("org_cfg_evt")

    info_mock.assert_called_once()
    assert info_mock.call_args[0][0] == "org_config.created_default"
    assert info_mock.call_args[1]["org_code"] == "org_cfg_evt"


async def test_orgconfig_upsert_emits_saved_event(session_maker, monkeypatch):
    from unittest.mock import MagicMock

    import logfire

    from backend.db.models import OrgConfig
    from backend.repositories.postgres import (
        PostgresOrgConfigRepository,
        PostgresOrgRepository,
    )

    org_repo = PostgresOrgRepository(session_maker)
    await org_repo.create_from_jwt(code="org_cfg_save", name="O")
    cfg_repo = PostgresOrgConfigRepository(session_maker)
    await cfg_repo.create_default("org_cfg_save")

    info_mock = MagicMock()
    monkeypatch.setattr(logfire, "info", info_mock)

    cfg = OrgConfig(org_code="org_cfg_save", language="en", target_word_count=800)
    await cfg_repo.upsert(cfg)

    info_mock.assert_called_once()
    assert info_mock.call_args[0][0] == "org_config.saved"
    assert info_mock.call_args[1]["org_code"] == "org_cfg_save"
    assert info_mock.call_args[1]["language"] == "en"
    assert info_mock.call_args[1]["target_word_count"] == 800
