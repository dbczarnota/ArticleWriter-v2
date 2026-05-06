"""HTTP-level tests for /v2/discovery/* endpoints.

Exercise routes via TestClient with stub repos and stub auth user/org
via FastAPI's dependency_overrides. Mirrors test_v2_endpoints.py."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.auth.deps import get_current_org, get_current_user
from backend.auth.protocols import AuthenticatedUser
from backend.db.models import DiscoveryItem, Org
from backend.main import app
from backend.repositories import get_discovery_repo
from backend.repositories.null import NullDiscoveryRepository


@pytest.fixture
def org() -> Org:
    return Org(code="org_t", domain_name="styl_fm", name="Test Org")


@pytest.fixture
def user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id="kp_test",
        email="t@example.com",
        org_codes=["org_t"],
        current_org_name="Test Org",
    )


@pytest.fixture
def discovery_repo() -> NullDiscoveryRepository:
    return NullDiscoveryRepository()


@pytest.fixture
def client(user, org, discovery_repo) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_org] = lambda: org
    app.dependency_overrides[get_discovery_repo] = lambda: discovery_repo
    yield_client = TestClient(app)
    yield yield_client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Task 20 — GET /v2/discovery/topics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_topics_returns_repo_rows(client, discovery_repo, org):
    await discovery_repo.create_topic(
        org_code=org.code, title="T1", blurb="B1", categories=["Sport"]
    )
    response = client.get("/v2/discovery/topics")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["title"] == "T1"
    assert rows[0]["categories"] == ["Sport"]
    assert rows[0]["status"] == "open"


@pytest.mark.asyncio
async def test_list_topics_filters_by_category(client, discovery_repo, org):
    a = await discovery_repo.create_topic(
        org_code=org.code, title="A", blurb="b", categories=["Polityka"]
    )
    await discovery_repo.create_topic(org_code=org.code, title="B", blurb="b", categories=["Sport"])
    response = client.get("/v2/discovery/topics", params={"category": "Polityka"})
    assert response.status_code == 200
    rows = response.json()
    assert {r["id"] for r in rows} == {str(a.id)}


# ---------------------------------------------------------------------------
# Task 21 — GET single topic + dismiss + restore
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_single_topic_with_items(client, discovery_repo, org):
    topic = await discovery_repo.create_topic(
        org_code=org.code, title="T", blurb="B", categories=[]
    )
    item = DiscoveryItem(
        org_code=org.code,
        canonical_url="https://x/1",
        title="Item",
        categories=[],
        topic_id=topic.id,
    )
    await discovery_repo.upsert_item(item)
    response = client.get(f"/v2/discovery/topics/{topic.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "T"
    assert len(body["items"]) == 1
    assert body["items"][0]["canonical_url"] == "https://x/1"


@pytest.mark.asyncio
async def test_get_topic_404_for_unknown(client):
    response = client.get(f"/v2/discovery/topics/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_dismiss_then_restore(client, discovery_repo, org):
    topic = await discovery_repo.create_topic(
        org_code=org.code, title="T", blurb="B", categories=[]
    )
    r1 = client.post(f"/v2/discovery/topics/{topic.id}/dismiss")
    assert r1.status_code == 200
    assert r1.json()["status"] == "dismissed"
    r2 = client.post(f"/v2/discovery/topics/{topic.id}/restore")
    assert r2.status_code == 200
    assert r2.json()["status"] == "open"


# ---------------------------------------------------------------------------
# Task 22 — POST /v2/discovery/topics/{id}/write_article
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_article_marks_topic_consumed(monkeypatch, user, org, discovery_repo):
    """Smoke: POST write_article should consume the topic and return a 202 with article_id.
    Mocks the background task to avoid actually running the pipeline."""
    from backend.repositories import get_article_repo, get_org_config_repo

    class _StubArticleRepo:
        async def create_running(self, **kwargs):
            return uuid4()

        async def get(self, *args, **kwargs):
            return None

    class _StubOrgConfigRepo:
        async def get(self, org_code):
            from backend.repositories.null import NullOrgConfigRepository

            return await NullOrgConfigRepository().get(org_code)

        async def upsert(self, cfg):
            return cfg

        async def create_default(self, org_code):
            from backend.db.models import OrgConfig

            return OrgConfig(org_code=org_code, language="pl")

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr("backend.api.v2._run_pipeline_background", _noop)

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_org] = lambda: org
    app.dependency_overrides[get_discovery_repo] = lambda: discovery_repo
    app.dependency_overrides[get_article_repo] = lambda: _StubArticleRepo()
    app.dependency_overrides[get_org_config_repo] = lambda: _StubOrgConfigRepo()

    try:
        topic = await discovery_repo.create_topic(
            org_code=org.code, title="T", blurb="B", categories=[]
        )
        item = DiscoveryItem(
            org_code=org.code,
            canonical_url="https://x/1",
            title="X",
            categories=[],
            topic_id=topic.id,
        )
        await discovery_repo.upsert_item(item)

        test_client = TestClient(app)
        response = test_client.post(f"/v2/discovery/topics/{topic.id}/write_article")
        assert response.status_code == 202
        body = response.json()
        assert body["topic_id"] == str(topic.id)
        assert "article_id" in body

        consumed = await discovery_repo.get_topic(topic_id=topic.id, org_code=org.code)
        assert consumed is not None
        assert consumed.status == "consumed"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_write_article_does_not_mark_consumed_until_task_runs(
    monkeypatch, user, org, discovery_repo
):
    """Endpoint returns 202 immediately; topic stays 'open' until the
    background task runs and marks it consumed. Simulating that the
    task never runs leaves the topic open."""
    from backend.repositories import get_article_repo, get_org_config_repo

    class _StubArticleRepo:
        async def create_running(self, **kwargs):
            return uuid4()

    class _StubOrgConfigRepo:
        async def get(self, org_code):
            from backend.repositories.null import NullOrgConfigRepository

            return await NullOrgConfigRepository().get(org_code)

        async def upsert(self, c):
            return c

        async def create_default(self, code):
            from backend.db.models import OrgConfig

            return OrgConfig(org_code=code, language="pl")

    # Simulate task scheduled but never runs (pod death scenario)
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr("backend.api.v2._run_pipeline_from_topic_background", _noop)

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_org] = lambda: org
    app.dependency_overrides[get_discovery_repo] = lambda: discovery_repo
    app.dependency_overrides[get_article_repo] = lambda: _StubArticleRepo()
    app.dependency_overrides[get_org_config_repo] = lambda: _StubOrgConfigRepo()

    try:
        topic = await discovery_repo.create_topic(
            org_code=org.code, title="T", blurb="B", categories=[]
        )
        test_client = TestClient(app)
        response = test_client.post(f"/v2/discovery/topics/{topic.id}/write_article")
        assert response.status_code == 202

        # Background task swapped to no-op; topic should still be 'open'.
        # The actual mark_consumed lives inside the wrapper which never ran.
        still_open = await discovery_repo.get_topic(topic_id=topic.id, org_code=org.code)
        assert still_open is not None
        assert still_open.status == "open"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Task 23 — feeds + categories endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_feeds_returns_runtime_state(client, discovery_repo, org):
    await discovery_repo.upsert_feed(org_code=org.code, feed_url="https://x/rss")
    response = client.get("/v2/discovery/feeds")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["feed_url"] == "https://x/rss"
    assert rows[0]["disabled"] is False


@pytest.mark.asyncio
async def test_reset_feed_clears_errors(client, discovery_repo, org):
    f = await discovery_repo.upsert_feed(org_code=org.code, feed_url="https://x/rss")
    await discovery_repo.record_feed_error(f.id, error_message="boom")
    response = client.post(f"/v2/discovery/feeds/{f.id}/reset")
    assert response.status_code == 200
    feeds_after = await discovery_repo.list_feeds_for_org(org.code)
    assert feeds_after[0].error_count == 0


@pytest.mark.asyncio
async def test_write_article_from_topic_with_zero_items(monkeypatch, user, org, discovery_repo):
    """Topic with no items: bridge still issues a 202; URLs list is empty
    so the pipeline falls back to its search stage (driven by topic.title
    alone). This is desired behavior — operators can request 'write about
    this trending topic' without curating URLs."""
    from backend.repositories import get_article_repo, get_org_config_repo

    class _StubArticleRepo:
        async def create_running(self, **kwargs):
            return uuid4()

    class _StubOrgConfigRepo:
        async def get(self, org_code):
            from backend.db.models import OrgConfig

            return OrgConfig(org_code=org_code, language="pl")

        async def upsert(self, c):
            return c

        async def create_default(self, code):
            from backend.db.models import OrgConfig

            return OrgConfig(org_code=code, language="pl")

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr("backend.api.v2._run_pipeline_from_topic_background", _noop)

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_org] = lambda: org
    app.dependency_overrides[get_discovery_repo] = lambda: discovery_repo
    app.dependency_overrides[get_article_repo] = lambda: _StubArticleRepo()
    app.dependency_overrides[get_org_config_repo] = lambda: _StubOrgConfigRepo()

    try:
        topic = await discovery_repo.create_topic(
            org_code=org.code, title="T", blurb="B", categories=[]
        )
        # Note: NO items attached to this topic
        test_client = TestClient(app)
        response = test_client.post(f"/v2/discovery/topics/{topic.id}/write_article")
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "running"
        assert body["topic_id"] == str(topic.id)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_categories_returns_domain_categories(monkeypatch, user, org, discovery_repo):
    """OrgConfigRepo stub so get_domain_config returns a DomainConfig.
    With styl_fm domain, discovery_categories will be whatever the domain defines."""
    from backend.repositories import get_org_config_repo

    class _Stub:
        async def get(self, org_code):
            from backend.repositories.null import NullOrgConfigRepository

            return await NullOrgConfigRepository().get(org_code)

        async def upsert(self, c):
            return c

        async def create_default(self, code):
            from backend.db.models import OrgConfig

            return OrgConfig(org_code=code, language="pl")

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_org] = lambda: org
    app.dependency_overrides[get_org_config_repo] = lambda: _Stub()
    try:
        test_client = TestClient(app)
        response = test_client.get("/v2/discovery/categories")
        assert response.status_code == 200
        # Result is a list; shape depends on domain config discovery_categories
        assert isinstance(response.json(), list)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_topics_filters_by_feed_id(client, discovery_repo, org):
    feed_a = await discovery_repo.upsert_feed(org_code=org.code, feed_url="https://a/rss")
    feed_b = await discovery_repo.upsert_feed(org_code=org.code, feed_url="https://b/rss")
    topic_a = await discovery_repo.create_topic(
        org_code=org.code, title="A", blurb="b", categories=[]
    )
    topic_b = await discovery_repo.create_topic(
        org_code=org.code, title="B", blurb="b", categories=[]
    )
    item_a = await discovery_repo.upsert_item(
        DiscoveryItem(
            org_code=org.code, canonical_url="https://a/x", title="x", topic_id=topic_a.id
        )
    )
    item_b = await discovery_repo.upsert_item(
        DiscoveryItem(
            org_code=org.code, canonical_url="https://b/y", title="y", topic_id=topic_b.id
        )
    )
    await discovery_repo.add_item_to_feed_link(item_id=item_a.id, feed_id=feed_a.id)
    await discovery_repo.add_item_to_feed_link(item_id=item_b.id, feed_id=feed_b.id)

    response = client.get("/v2/discovery/topics", params={"feed_id": str(feed_a.id)})
    assert response.status_code == 200
    rows = response.json()
    assert {r["id"] for r in rows} == {str(topic_a.id)}
