import pytest
from dataclasses import FrozenInstanceError
from domains._base.config import DomainConfig
from domains.styl_fm.config import STYL_FM_DOMAIN


def test_domain_config_defaults():
    d = DomainConfig(name="test", description="Test domain")
    assert d.target_word_count == 600
    assert d.max_facts_in_article == 8
    assert d.max_quotes_in_article == 3
    assert d.default_search_freshness == "qdr:w"
    assert d.default_num_queries == 3
    assert d.default_max_results == 5
    assert d.youtube_search is False
    assert d.twitter_search is False
    assert d.facebook_search is False


def test_styl_fm_domain_has_name():
    assert STYL_FM_DOMAIN.name == "styl_fm"


def test_styl_fm_guidelines_loaded():
    assert len(STYL_FM_DOMAIN.guidelines) > 100


def test_styl_fm_has_example_articles():
    assert len(STYL_FM_DOMAIN.example_articles) >= 1


def test_domain_config_is_frozen():
    d = DomainConfig(name="test", description="Test")
    with pytest.raises(FrozenInstanceError):
        d.target_word_count = 999


def test_domain_config_language_default():
    d = DomainConfig(name="test", description="Test domain")
    assert d.language == "pl"


def test_styl_fm_language_is_polish():
    assert STYL_FM_DOMAIN.language == "pl"


def test_domain_config_new_flags():
    from domains._base.config import DomainConfig
    d = DomainConfig(name="test", description="t")
    assert d.news_search is False
    assert d.tiktok_search is False
    assert d.instagram_search is False
    assert d.reddit_search is False
