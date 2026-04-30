import pytest
from pydantic import ValidationError
from backend.api.schemas import ArticleRequest


def test_article_request_minimal():
    req = ArticleRequest(id="art-1", topic="Dawid Podsiadło")
    assert req.domain == "styl_fm"
    assert req.urls == []
    assert req.domains_filter == []
    assert req.agents == {}
    assert req.pipeline == {}
    assert req.additional_instructions is None


def test_article_request_requires_id_and_topic():
    with pytest.raises(ValidationError):
        ArticleRequest(topic="Test")

    with pytest.raises(ValidationError):
        ArticleRequest(id="test-1")


def test_article_request_with_overrides():
    req = ArticleRequest(
        id="art-2",
        topic="Test",
        domain="the_economist",
        agents={"writer": {"model": "google-gla:gemini-2.5-flash", "thinking": "high"}},
        pipeline={"reflection": False},
    )
    assert req.domain == "the_economist"
    assert req.agents["writer"]["model"] == "google-gla:gemini-2.5-flash"
    assert req.pipeline["reflection"] is False


def test_article_request_urls_as_list():
    req = ArticleRequest(
        id="art-3",
        topic="Test",
        urls=["https://example.com/1", "https://example.com/2"],
    )
    assert len(req.urls) == 2
