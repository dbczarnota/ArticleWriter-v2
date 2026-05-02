# tests/backend/test_main.py
from fastapi.testclient import TestClient


def test_health_returns_ok():
    from backend.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
