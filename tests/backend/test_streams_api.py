from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

ORG = "__local_dev__"


@pytest.fixture
def client():
    """TestClient with mocked stream manager.

    Patch the get_stream_manager function as imported in the streams router,
    not the module-level _manager variable — the FastAPI lifespan calls
    init_stream_manager() which overwrites _manager during TestClient startup.
    """
    mock_manager = MagicMock()
    mock_manager.start = AsyncMock()
    mock_manager.stop = AsyncMock()
    mock_manager.register_sse_queue = MagicMock(return_value=asyncio.Queue())
    mock_manager.unregister_sse_queue = MagicMock()

    with patch("backend.api.streams.get_stream_manager", return_value=mock_manager):
        from backend.main import app

        with TestClient(app) as c:
            yield c, mock_manager


def test_create_subscription_returns_201(client):
    c, _manager = client
    resp = c.post(
        "/v2/streams/subscriptions",
        json={"name": "TOK FM", "stream_url": "http://example.com/stream.mp3"},
        headers={"X-Org-Code": ORG},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "TOK FM"
    assert data["status"] == "active"
    assert "id" in data


def test_list_subscriptions(client):
    c, _ = client
    resp = c.get("/v2/streams/subscriptions", headers={"X-Org-Code": ORG})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_delete_subscription_returns_204(client):
    c, manager = client
    create = c.post(
        "/v2/streams/subscriptions",
        json={"name": "TOK FM", "stream_url": "http://example.com/stream.mp3"},
        headers={"X-Org-Code": ORG},
    )
    sub_id = create.json()["id"]

    resp = c.delete(f"/v2/streams/subscriptions/{sub_id}", headers={"X-Org-Code": ORG})
    assert resp.status_code == 204
    manager.stop.assert_called_once()


def test_get_results_empty(client):
    c, _ = client
    fake_id = str(uuid4())
    resp = c.get(f"/v2/streams/subscriptions/{fake_id}/results", headers={"X-Org-Code": ORG})
    assert resp.status_code in (200, 404)
