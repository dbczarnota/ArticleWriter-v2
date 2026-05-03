import pytest

from backend.domain import DomainConfig


def test_defaults():
    d = DomainConfig(name="test", description="Test domain")
    assert d.language == "pl"
    assert d.target_word_count == 600
    assert d.youtube_search is False
    assert d.media_search_languages == ("en",)
    assert d.example_articles == ()


def test_frozen():
    import dataclasses

    d = DomainConfig(name="test", description="Test")
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        d.language = "en"  # type: ignore[misc]


def test_custom_values():
    d = DomainConfig(
        name="test",
        description="Test domain",
        language="en",
        target_word_count=1200,
        youtube_search=True,
    )
    assert d.language == "en"
    assert d.target_word_count == 1200
    assert d.youtube_search is True


def test_immutable_tuple_fields():
    from backend.domain import DomainConfig

    d = DomainConfig(name="t", description="t", media_search_languages=("en", "pl"))
    assert isinstance(d.media_search_languages, tuple)
    assert d.media_search_languages == ("en", "pl")
