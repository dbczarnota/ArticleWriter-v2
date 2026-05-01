import pytest
from pydantic import ValidationError
from backend.api.schemas import ArticleRequest


def _base() -> dict:
    return {"id": "x", "topic": "Test topic", "domain": "styl_fm"}


def test_valid_request_passes():
    req = ArticleRequest(**_base())
    assert req.topic == "Test topic"


def test_topic_empty_fails():
    with pytest.raises(ValidationError):
        ArticleRequest(**{**_base(), "topic": ""})


def test_topic_whitespace_only_fails():
    with pytest.raises(ValidationError):
        ArticleRequest(**{**_base(), "topic": "   "})


def test_topic_too_long_fails():
    with pytest.raises(ValidationError):
        ArticleRequest(**{**_base(), "topic": "x" * 301})


def test_additional_instructions_too_long_fails():
    with pytest.raises(ValidationError):
        ArticleRequest(**{**_base(), "additional_instructions": "x" * 2001})


def test_additional_instructions_none_passes():
    req = ArticleRequest(**_base())
    assert req.additional_instructions is None


def test_topic_stripped():
    req = ArticleRequest(**{**_base(), "topic": "  Hello  "})
    assert req.topic == "Hello"
