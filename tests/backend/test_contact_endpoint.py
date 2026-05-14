from __future__ import annotations

import httpx as _httpx
import pytest
import respx
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backend.main import app

    return TestClient(app)


def test_contact_missing_fields(client):
    res = client.post("/v2/contact", json={})
    assert res.status_code == 422


def test_contact_invalid_email(client):
    res = client.post(
        "/v2/contact", json={"name": "Test", "email": "not-an-email", "message": "Hello"}
    )
    assert res.status_code == 422


def test_contact_name_too_long(client):
    res = client.post(
        "/v2/contact", json={"name": "x" * 201, "email": "test@example.com", "message": "Hello"}
    )
    assert res.status_code == 422


def test_contact_message_too_long(client):
    res = client.post(
        "/v2/contact", json={"name": "Test", "email": "test@example.com", "message": "x" * 4001}
    )
    assert res.status_code == 422


def test_contact_no_api_key(client, monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    res = client.post(
        "/v2/contact", json={"name": "Jan", "email": "jan@example.com", "message": "Test"}
    )
    assert res.status_code == 503


@respx.mock
def test_contact_success(client, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    respx.post("https://api.resend.com/emails").mock(
        return_value=_httpx.Response(200, json={"id": "fake-id"})
    )
    res = client.post(
        "/v2/contact",
        json={
            "name": "Jan Kowalski",
            "email": "jan@example.com",
            "company": "ACME",
            "message": "Chcę demo.",
        },
    )
    assert res.status_code == 200
    assert res.json() == {"ok": True}


@respx.mock
def test_contact_resend_failure(client, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    respx.post("https://api.resend.com/emails").mock(
        return_value=_httpx.Response(500, json={"error": "server error"})
    )
    res = client.post(
        "/v2/contact", json={"name": "Jan", "email": "jan@example.com", "message": "Test"}
    )
    assert res.status_code == 500
