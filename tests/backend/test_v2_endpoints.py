"""GET /v2/* endpoint integration tests with multi-tenant isolation.

These exercise the FastAPI routes through TestClient with stub repos + a stub
authenticated user injected via dependency_overrides. Real Postgres is not
required — multi-tenancy is enforced in the route layer, not at the DB.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from backend.auth.deps import get_current_org, get_current_user
from backend.auth.protocols import AuthenticatedUser
from backend.db.models import Article, Fact, Org, Quote
from backend.repositories import get_article_repo, get_org_repo


def _org(code: str, domain: str = "styl_fm", name: str | None = None) -> Org:
    now = datetime.now(UTC)
    return Org(
        code=code,
        domain_name=domain,
        name=name or f"Org {code}",
        kinde_org_id=f"kinde_{code}",
        created_at=now,
        updated_at=now,
    )


class _StubArticleRepo:
    """In-memory ArticleRepository — enforces tenant filter in get/list."""

    def __init__(self) -> None:
        self.articles: dict[UUID, Article] = {}

    def add(self, article: Article) -> None:
        self.articles[article.id] = article

    async def get(self, article_id: UUID, *, org_code: str) -> Article | None:
        a = self.articles.get(article_id)
        if a is None or a.org_code != org_code:
            return None
        return a

    async def list_by_org(
        self, *, org_code: str, limit: int = 20, offset: int = 0
    ) -> list[Article]:
        rows = [a for a in self.articles.values() if a.org_code == org_code]
        rows.sort(key=lambda a: a.created_at or datetime.now(UTC), reverse=True)
        return rows[offset : offset + limit]

    # Write-side stubs — create_running returns a fresh UUID so write_article works.
    async def create_running(self, **_kw) -> UUID:
        article_id = uuid4()
        return article_id

    async def complete(self, *_a, **_kw):  # pragma: no cover
        raise NotImplementedError

    async def mark_failed(self, *_a, **_kw):  # pragma: no cover
        raise NotImplementedError


class _StubOrgRepo:
    def __init__(self, orgs: list[Org]) -> None:
        self._by_code = {o.code: o for o in orgs}

    async def get(self, code: str) -> Org | None:
        return self._by_code.get(code)

    async def list_for_user(self, user_org_codes: list[str]) -> list[Org]:
        return [self._by_code[c] for c in user_org_codes if c in self._by_code]

    async def create_from_jwt(self, **_kw) -> Org:  # pragma: no cover
        raise NotImplementedError

    async def set_domain_name(self, code: str, domain_name: str) -> None:
        org = self._by_code.get(code)
        if org is not None:
            org.domain_name = domain_name


def _make_article(*, org_code: str, topic: str = "T", status: str = "done") -> Article:
    """Build a fully-populated Article (with one fact + one quote) for fixture use."""
    article_id = uuid4()
    now = datetime.now(UTC)
    a = Article(
        id=article_id,
        org_code=org_code,
        author_user_id="user_1",
        domain_name="styl_fm",
        topic=topic,
        status=status,
        html="<h1>Hi</h1>",
        alternative_titles=["Alt"],
        followup_topics=["FU"],
        sources=["https://a.example/1"],
        pipeline_timing={"research": 100.0},
        errors=[],
        total_duration_ms=1234.5,
        created_at=now,
        completed_at=now,
    )
    a.facts = [
        Fact(
            article_id=article_id,
            text="F",
            context="c",
            source_url="https://a.example/1",
            source_title="A",
        )
    ]
    a.quotes = [
        Quote(
            article_id=article_id,
            text="Q",
            speaker="X",
            context="c",
            source_url="https://a.example/1",
        )
    ]
    a.embed_candidates = []
    a.usage_events = []
    a.fallback_events = []
    return a


@pytest.fixture
def org_a() -> Org:
    return _org("org_a", name="Org A")


@pytest.fixture
def org_b() -> Org:
    return _org("org_b", name="Org B")


@pytest.fixture
def stub_article_repo() -> _StubArticleRepo:
    return _StubArticleRepo()


@pytest.fixture
def stub_org_repo(org_a: Org, org_b: Org) -> _StubOrgRepo:
    return _StubOrgRepo([org_a, org_b])


@pytest.fixture
def client_as(stub_article_repo, stub_org_repo):
    """Yields a factory: client_as(user, org) -> TestClient with deps overridden."""
    from backend.main import app

    def _factory(*, user: AuthenticatedUser, org: Org | None) -> TestClient:
        app.dependency_overrides[get_current_user] = lambda: user
        if org is not None:
            app.dependency_overrides[get_current_org] = lambda: org
        app.dependency_overrides[get_article_repo] = lambda: stub_article_repo
        app.dependency_overrides[get_org_repo] = lambda: stub_org_repo
        return TestClient(app)

    yield _factory
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# /v2/me
# ---------------------------------------------------------------------------


def test_get_me_returns_current_user(client_as):
    user = AuthenticatedUser(id="u1", email="u1@example.com", org_codes=["org_a"])
    client = client_as(user=user, org=None)
    r = client.get("/v2/me")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "u1"
    assert body["email"] == "u1@example.com"
    assert body["org_codes"] == ["org_a"]


# ---------------------------------------------------------------------------
# /v2/orgs
# ---------------------------------------------------------------------------


def test_list_orgs_returns_only_users_orgs(client_as, org_a):
    user = AuthenticatedUser(id="u1", email=None, org_codes=["org_a"])
    client = client_as(user=user, org=None)
    r = client.get("/v2/orgs")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["code"] == "org_a"
    assert body[0]["domain_name"] == "styl_fm"


# ---------------------------------------------------------------------------
# /v2/articles (list) — tenant filter
# ---------------------------------------------------------------------------


def test_list_articles_only_returns_current_org(client_as, stub_article_repo, org_a, org_b):
    stub_article_repo.add(_make_article(org_code="org_a", topic="A1"))
    stub_article_repo.add(_make_article(org_code="org_a", topic="A2"))
    stub_article_repo.add(_make_article(org_code="org_b", topic="B1"))

    user = AuthenticatedUser(id="u1", email=None, org_codes=["org_a", "org_b"])
    client = client_as(user=user, org=org_a)
    r = client.get("/v2/articles")
    assert r.status_code == 200
    topics = {row["topic"] for row in r.json()}
    assert topics == {"A1", "A2"}


def test_list_articles_pagination(client_as, stub_article_repo, org_a):
    for i in range(5):
        stub_article_repo.add(_make_article(org_code="org_a", topic=f"T{i}"))

    user = AuthenticatedUser(id="u1", email=None, org_codes=["org_a"])
    client = client_as(user=user, org=org_a)
    r = client.get("/v2/articles?limit=2&offset=0")
    assert r.status_code == 200
    assert len(r.json()) == 2


# ---------------------------------------------------------------------------
# /v2/articles/{id} — tenant isolation
# ---------------------------------------------------------------------------


def test_get_article_happy_path(client_as, stub_article_repo, org_a):
    article = _make_article(org_code="org_a", topic="hello")
    stub_article_repo.add(article)

    user = AuthenticatedUser(id="u1", email=None, org_codes=["org_a"])
    client = client_as(user=user, org=org_a)
    r = client.get(f"/v2/articles/{article.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(article.id)
    assert body["topic"] == "hello"
    assert body["html"] == "<h1>Hi</h1>"
    assert len(body["facts"]) == 1
    assert len(body["quotes"]) == 1


def test_get_article_other_org_returns_404_no_existence_leak(
    client_as, stub_article_repo, org_a, org_b
):
    """An article that exists for org_a must look identical to a non-existent id when
    queried through org_b — same 404, no special-casing the existence."""
    article_a = _make_article(org_code="org_a", topic="secret")
    stub_article_repo.add(article_a)

    user = AuthenticatedUser(id="u1", email=None, org_codes=["org_a", "org_b"])
    client = client_as(user=user, org=org_b)

    r_existing_other_tenant = client.get(f"/v2/articles/{article_a.id}")
    r_random_id = client.get(f"/v2/articles/{uuid4()}")

    assert r_existing_other_tenant.status_code == 404
    assert r_random_id.status_code == 404
    assert r_existing_other_tenant.json() == r_random_id.json()


def test_get_article_invalid_uuid_returns_422(client_as, org_a):
    user = AuthenticatedUser(id="u1", email=None, org_codes=["org_a"])
    client = client_as(user=user, org=org_a)
    r = client.get("/v2/articles/not-a-uuid")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# /v2/write_article — response shape
# ---------------------------------------------------------------------------


def test_write_article_response_includes_id(client_as, org_a):
    """write_article returns 202 with {id, status, topic} so the frontend can poll."""
    from backend.repositories import get_org_config_repo
    from backend.repositories.null import NullOrgConfigRepository

    user = AuthenticatedUser(id="u1", email=None, org_codes=["org_a"])
    app = __import__("backend.main", fromlist=["app"]).app
    app.dependency_overrides[get_org_config_repo] = lambda: NullOrgConfigRepository()

    with patch("backend.api.v2.run_pipeline", new=AsyncMock()):
        client = client_as(user=user, org=org_a)
        r = client.post(
            "/v2/write_article",
            json={"topic": "Test topic"},
        )

    assert r.status_code == 202, r.text
    body = r.json()
    assert "id" in body, f"'id' key missing from response: {list(body.keys())}"
    UUID(body["id"])  # must be a valid UUID
    assert body["status"] == "running"
    assert body["topic"] == "Test topic"
