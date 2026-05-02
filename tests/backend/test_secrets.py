# tests/backend/test_secrets.py
import pytest


def test_get_secrets_reads_env_vars(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "serper-test-key")
    monkeypatch.setenv("JINA_API_KEY", "jina-test-key")

    from backend.secrets import get_secrets

    get_secrets.cache_clear()
    secrets = get_secrets()
    assert secrets.serper_api_key == "serper-test-key"
    assert secrets.jina_api_key == "jina-test-key"
    get_secrets.cache_clear()


def test_get_secrets_jina_optional(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "serper-key")
    monkeypatch.delenv("JINA_API_KEY", raising=False)

    from backend.secrets import get_secrets

    get_secrets.cache_clear()
    secrets = get_secrets()
    assert secrets.jina_api_key is None
    get_secrets.cache_clear()


def test_get_secrets_raises_without_serper_key(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)

    from backend.secrets import get_secrets

    get_secrets.cache_clear()
    with pytest.raises(RuntimeError, match="SERPER_API_KEY"):
        get_secrets()
    get_secrets.cache_clear()
