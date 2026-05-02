# tests/backend/test_v2.py
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from agents._base.types import ArticleOutput
from backend.secrets import Secrets, get_secrets

_MOCK_OUTPUT = ArticleOutput(
    html="<h1>Test</h1><p>Content</p>",
    alternative_titles=["Alt title"],
    followup_topics=["Follow-up topic"],
    used_facts=["Fakt 1"],
    used_quotes=["Cytat 1"],
    sources=["https://example.com"],
)

_FAKE_SECRETS = Secrets(serper_api_key="test-serper-key", jina_api_key=None)


@pytest.fixture(autouse=True)
def override_secrets():
    from backend.main import app

    app.dependency_overrides[get_secrets] = lambda: _FAKE_SECRETS
    yield
    app.dependency_overrides.clear()


def test_write_article_returns_200():
    from backend.main import app

    with patch("backend.api.v2.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = _MOCK_OUTPUT
        client = TestClient(app)
        response = client.post(
            "/v2/write_article",
            json={"id": "1", "topic": "Dawid Podsiadło"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["html"] == "<h1>Test</h1><p>Content</p>"
    assert data["alternative_titles"] == ["Alt title"]
    assert data["sources"] == ["https://example.com"]


def test_write_article_unknown_domain_returns_422():
    from backend.main import app

    with patch("backend.api.v2.run_pipeline", new_callable=AsyncMock):
        client = TestClient(app)
        response = client.post(
            "/v2/write_article",
            json={"id": "1", "topic": "topic", "domain": "nonexistent_domain"},
        )
    assert response.status_code == 422
    assert "nonexistent_domain" in response.json()["detail"]


def test_write_article_passes_topic_to_pipeline():
    from backend.main import app

    with patch("backend.api.v2.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = _MOCK_OUTPUT
        client = TestClient(app)
        client.post(
            "/v2/write_article",
            json={"id": "1", "topic": "Konkretny temat"},
        )
    mock_pipeline.assert_called_once()
    assert mock_pipeline.call_args.args[0] == "Konkretny temat"
