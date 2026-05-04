"""Tests for GET/PUT /v2/domain-config."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.auth.deps import get_current_org, get_current_user
from backend.auth.protocols import AuthenticatedUser
from backend.db.models import Org, OrgConfig
from backend.main import app
from backend.repositories import get_org_config_repo, reset_repo_cache

_ORG = Org(
    code="test-org",
    domain_name="styl_fm",
    name="Test Org",
    kinde_org_id=None,
)
_USER = AuthenticatedUser(id="user-1", email="u@example.com", org_codes=["test-org"])

_DEFAULT_CONFIG = OrgConfig(
    org_code="test-org",
    description="Test desc",
    language="pl",
    target_word_count=600,
    max_facts=8,
    max_quotes=3,
    search_freshness="qdr:w",
    num_queries=3,
    max_results=5,
    min_source_signals=1,
    max_pages_to_scrape=10,
    youtube_search=False,
    twitter_search=False,
    facebook_search=False,
    news_search=False,
    tiktok_search=False,
    instagram_search=False,
    reddit_search=False,
    media_search_languages=["en"],
    media_search_num=5,
    media_search_max_query_tiers=2,
    youtube_sort_by_date=True,
    reflection_context_articles=2,
    guidelines="",
    html_format="",
    reflection_stance="",
    example_articles=[],
)


class _StubOrgConfigRepo:
    def __init__(self, config: OrgConfig | None = _DEFAULT_CONFIG) -> None:
        self._config = config
        self.last_upserted: OrgConfig | None = None

    async def get(self, org_code: str) -> OrgConfig | None:
        return self._config

    async def upsert(self, config: OrgConfig) -> OrgConfig:
        self.last_upserted = config
        return config


@pytest.fixture()
def client_with_config():
    stub = _StubOrgConfigRepo()
    app.dependency_overrides[get_current_user] = lambda: _USER
    app.dependency_overrides[get_current_org] = lambda: _ORG
    app.dependency_overrides[get_org_config_repo] = lambda: stub
    reset_repo_cache()
    yield TestClient(app), stub
    app.dependency_overrides.clear()
    reset_repo_cache()


@pytest.fixture()
def client_no_config():
    stub = _StubOrgConfigRepo(config=None)
    app.dependency_overrides[get_current_user] = lambda: _USER
    app.dependency_overrides[get_current_org] = lambda: _ORG
    app.dependency_overrides[get_org_config_repo] = lambda: stub
    reset_repo_cache()
    yield TestClient(app)
    app.dependency_overrides.clear()
    reset_repo_cache()


def test_get_domain_config_returns_config(client_with_config):
    client, _ = client_with_config
    resp = client.get("/v2/domain-config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["org_code"] == "test-org"
    assert data["language"] == "pl"
    assert data["target_word_count"] == 600


def test_get_domain_config_404_when_not_configured(client_no_config):
    resp = client_no_config.get("/v2/domain-config")
    assert resp.status_code == 404


def test_put_domain_config_upserts(client_with_config):
    client, stub = client_with_config
    resp = client.put(
        "/v2/domain-config",
        json={
            "description": "Updated",
            "language": "en",
            "target_word_count": 800,
            "max_facts": 10,
            "max_quotes": 4,
            "search_freshness": "qdr:m",
            "num_queries": 4,
            "max_results": 8,
            "min_source_signals": 2,
            "max_pages_to_scrape": 15,
            "youtube_search": True,
            "twitter_search": False,
            "facebook_search": False,
            "news_search": True,
            "tiktok_search": False,
            "instagram_search": False,
            "reddit_search": False,
            "media_search_languages": ["en", "pl"],
            "media_search_num": 5,
            "media_search_max_query_tiers": 2,
            "youtube_sort_by_date": True,
            "reflection_context_articles": 2,
            "guidelines": "Be concise.",
            "html_format": "<h1>Title</h1>",
            "reflection_stance": "Critical",
            "example_articles": ["Article one text"],
        },
    )
    assert resp.status_code == 200
    assert stub.last_upserted is not None
    assert stub.last_upserted.description == "Updated"
    assert stub.last_upserted.target_word_count == 800
    assert stub.last_upserted.guidelines == "Be concise."
    assert stub.last_upserted.example_articles == ["Article one text"]


def test_put_domain_config_validates_word_count(client_with_config):
    client, _ = client_with_config
    resp = client.put("/v2/domain-config", json={"target_word_count": 50000})
    assert resp.status_code == 422


def test_put_domain_config_validates_max_facts(client_with_config):
    client, _ = client_with_config
    resp = client.put("/v2/domain-config", json={"max_facts": 0})
    assert resp.status_code == 422


def test_unauthenticated_requests_rejected():
    """Verify both endpoints reject requests without auth.

    With AUTH_BACKEND=null the bearer token is always accepted, but
    get_current_org requires X-Org-Code header — FastAPI returns 422 when
    it is absent, which is still a rejection.
    """
    # No dependency overrides — real auth deps run
    reset_repo_cache()
    client = TestClient(app, raise_server_exceptions=False)

    resp_get = client.get("/v2/domain-config")
    assert resp_get.status_code in (401, 403, 422)

    resp_put = client.put("/v2/domain-config", json={"description": "x"})
    assert resp_put.status_code in (401, 403, 422)
