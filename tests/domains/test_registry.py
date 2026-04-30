# tests/domains/test_registry.py
import pytest
from domains.registry import load_domain
from domains._base.config import DomainConfig


def test_load_domain_returns_styl_fm():
    domain = load_domain("styl_fm")
    assert isinstance(domain, DomainConfig)
    assert domain.name == "styl_fm"


def test_load_domain_raises_for_unknown():
    with pytest.raises(KeyError, match="unknown_domain"):
        load_domain("unknown_domain")


def test_load_domain_error_message_lists_available():
    with pytest.raises(KeyError, match="styl_fm"):
        load_domain("nonexistent")
