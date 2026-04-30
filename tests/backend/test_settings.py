# tests/backend/test_settings.py
import pytest


def test_get_settings_reads_env_vars(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "serper-test-key")
    monkeypatch.setenv("JINA_API_KEY", "jina-test-key")

    from backend.settings import get_settings
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.serper_api_key == "serper-test-key"
    assert settings.jina_api_key == "jina-test-key"
    get_settings.cache_clear()


def test_get_settings_jina_optional(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "serper-key")
    monkeypatch.delenv("JINA_API_KEY", raising=False)

    from backend.settings import get_settings
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.jina_api_key is None
    get_settings.cache_clear()


def test_get_settings_raises_without_serper_key(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)

    from backend.settings import get_settings
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="SERPER_API_KEY"):
        get_settings()
    get_settings.cache_clear()
