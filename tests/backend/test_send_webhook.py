"""POST /v2/articles/{id}/send-webhook — happy path, error response, timeout, no-config, secret omission."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from backend.api.v2 import (
    get_article_repo,
    get_current_org,
    get_current_user,
    get_org_config_repo,
)
from backend.auth.protocols import AuthenticatedUser
from backend.db.models import Article, Org, OrgConfig


class _StubArticleRepo:
    def __init__(self) -> None:
        self.articles: dict[UUID, Article] = {}
        self.deliveries: list[tuple[UUID, str, dict]] = []

    def add(self, article: Article) -> None:
        self.articles[article.id] = article

    async def get(self, article_id: UUID, *, org_code: str) -> Article | None:
        a = self.articles.get(article_id)
        if a is None or a.org_code != org_code:
            return None
        return a

    async def record_webhook_delivery(
        self, article_id: UUID, *, org_code: str, entry: dict
    ) -> None:
        self.deliveries.append((article_id, org_code, entry))


class _StubOrgConfigRepo:
    def __init__(self, configs: dict[str, OrgConfig]) -> None:
        self._by_code = configs

    async def get(self, org_code: str) -> OrgConfig | None:
        return self._by_code.get(org_code)


def _make_article(org_code: str) -> Article:
    now = datetime.now(UTC)
    a = Article(
        id=uuid4(),
        org_code=org_code,
        author_user_id="u1",
        domain_name="styl_fm",
        topic="T",
        status="done",
        html="<h1>Hi</h1>",
        alternative_titles=["Alt"],
        followup_topics=["FU"],
        sources=[],
        generated_images=[],
        pipeline_timing={},
        errors=[],
        created_at=now,
        completed_at=now,
    )
    a.facts = []
    a.quotes = []
    return a


@pytest.fixture
def org() -> Org:
    return Org(code="org_a", domain_name="styl.fm", name="Org A")


@pytest.fixture
def article(org: Org) -> Article:
    return _make_article(org.code)


@pytest.fixture
def setup_client(org: Org, article: Article):
    """Build TestClient with overridden deps. Returns (client, article_repo, config)."""
    from backend.main import app

    article_repo = _StubArticleRepo()
    article_repo.add(article)
    user = AuthenticatedUser(id="u1", email="u1@example.com", org_codes=[org.code])

    def _setup(*, webhook_url: str | None, webhook_secret: str | None = None):
        config = OrgConfig(
            org_code=org.code, webhook_url=webhook_url, webhook_secret=webhook_secret
        )
        config_repo = _StubOrgConfigRepo({org.code: config})
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_current_org] = lambda: org
        app.dependency_overrides[get_article_repo] = lambda: article_repo
        app.dependency_overrides[get_org_config_repo] = lambda: config_repo
        return TestClient(app), article_repo, config

    yield _setup
    app.dependency_overrides.clear()


def test_send_webhook_success(setup_client, article):
    client, repo, _ = setup_client(webhook_url="https://hook.example/in", webhook_secret="sekret")
    with respx.mock(assert_all_called=True) as router:
        route = router.post("https://hook.example/in").mock(
            return_value=httpx.Response(202, json={"ok": True})
        )
        res = client.post(f"/v2/articles/{article.id}/send-webhook")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "success"
        assert body["http_status"] == 202
        sent = route.calls.last.request
        assert sent.headers.get("X-Webhook-Secret") == "sekret"
        sent_json = sent.content.decode()
        assert "article_id" in sent_json
        assert article.topic in sent_json
    # Delivery recorded
    assert len(repo.deliveries) == 1
    assert repo.deliveries[0][2]["status"] == "success"


def test_send_webhook_5xx_recorded_as_error(setup_client, article):
    client, repo, _ = setup_client(webhook_url="https://hook.example/in", webhook_secret=None)
    with respx.mock() as router:
        router.post("https://hook.example/in").mock(return_value=httpx.Response(500))
        res = client.post(f"/v2/articles/{article.id}/send-webhook")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "error"
        assert body["http_status"] == 500
        assert body["error"] == "http 500"
    assert repo.deliveries[0][2]["status"] == "error"


def test_send_webhook_timeout_recorded_as_error(setup_client, article):
    client, repo, _ = setup_client(webhook_url="https://hook.example/in")
    with respx.mock() as router:
        router.post("https://hook.example/in").mock(side_effect=httpx.TimeoutException("slow"))
        res = client.post(f"/v2/articles/{article.id}/send-webhook")
        body = res.json()
        assert body["status"] == "error"
        assert body["http_status"] is None
        assert body["error"] == "timeout"
    assert repo.deliveries[0][2]["error"] == "timeout"


def test_send_webhook_400_when_url_not_configured(setup_client, article):
    client, repo, _ = setup_client(webhook_url=None)
    res = client.post(f"/v2/articles/{article.id}/send-webhook")
    assert res.status_code == 400
    assert res.json()["detail"] == "Webhook not configured for this org"
    assert repo.deliveries == []


def test_send_webhook_400_when_url_is_http(setup_client, article):
    client, _repo, _ = setup_client(webhook_url="http://hook.example/in")
    res = client.post(f"/v2/articles/{article.id}/send-webhook")
    assert res.status_code == 400
    assert "https" in res.json()["detail"]


def test_send_webhook_secret_omitted_when_unset(setup_client, article):
    client, _repo, _ = setup_client(webhook_url="https://hook.example/in", webhook_secret=None)
    with respx.mock() as router:
        route = router.post("https://hook.example/in").mock(return_value=httpx.Response(200))
        client.post(f"/v2/articles/{article.id}/send-webhook")
        sent = route.calls.last.request
        assert "X-Webhook-Secret" not in sent.headers


def test_send_webhook_404_when_article_missing(setup_client):
    client, _repo, _ = setup_client(webhook_url="https://hook.example/in")
    res = client.post(f"/v2/articles/{uuid4()}/send-webhook")
    assert res.status_code == 404


# Suppress unused-Any-import lint
_: Any = None
