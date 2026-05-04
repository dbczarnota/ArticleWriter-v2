# tests/backend/test_v2.py
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from backend.secrets import Secrets, get_secrets

_FAKE_SECRETS = Secrets(serper_api_key="test-serper-key", jina_api_key=None)

# AUTH_BACKEND=null (forced in conftest) makes NullAuthenticator return a hardcoded
# user with org_codes=['__local_dev__']. Same value below for the X-Org-Code header.
_LOCAL_DEV_HEADERS = {"X-Org-Code": "__local_dev__"}


@pytest.fixture(autouse=True)
def override_secrets():
    from backend.main import app

    app.dependency_overrides[get_secrets] = lambda: _FAKE_SECRETS
    yield
    app.dependency_overrides.clear()


def test_write_article_returns_202():
    """write_article starts background generation and immediately returns 202 Accepted."""
    from backend.main import app

    with patch("backend.api.v2.run_pipeline", new_callable=AsyncMock):
        client = TestClient(app)
        response = client.post(
            "/v2/write_article",
            json={"topic": "Dawid Podsiadło"},
            headers=_LOCAL_DEV_HEADERS,
        )
    assert response.status_code == 202
    data = response.json()
    assert "id" in data
    UUID(data["id"])  # must be a valid UUID
    assert data["status"] == "running"
    assert data["topic"] == "Dawid Podsiadło"


def test_write_article_missing_org_header_returns_422():
    """Without X-Org-Code header FastAPI returns 422 (param-validation level)."""
    from backend.main import app

    with patch("backend.api.v2.run_pipeline", new_callable=AsyncMock):
        client = TestClient(app)
        response = client.post(
            "/v2/write_article",
            json={"topic": "topic"},
        )
    assert response.status_code == 422


def test_write_article_wrong_org_header_returns_403():
    """X-Org-Code that's not in the user's JWT claim is rejected with 403."""
    from backend.main import app

    with patch("backend.api.v2.run_pipeline", new_callable=AsyncMock):
        client = TestClient(app)
        response = client.post(
            "/v2/write_article",
            json={"topic": "topic"},
            headers={"X-Org-Code": "some_other_org_user_doesnt_belong_to"},
        )
    assert response.status_code == 403


def test_write_article_passes_topic_and_org_to_pipeline():
    from backend.main import app

    with patch("backend.api.v2.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
        client = TestClient(app)
        client.post(
            "/v2/write_article",
            json={"topic": "Konkretny temat"},
            headers=_LOCAL_DEV_HEADERS,
        )
    mock_pipeline.assert_called_once()
    assert mock_pipeline.call_args.args[0] == "Konkretny temat"
    assert mock_pipeline.call_args.kwargs["org_code"] == "__local_dev__"
    assert mock_pipeline.call_args.kwargs["author_user_id"] == "local-dev"
