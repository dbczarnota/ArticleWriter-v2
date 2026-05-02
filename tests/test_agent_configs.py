from dataclasses import FrozenInstanceError, replace

import pytest

from agents._base.config import (
    AgentConfig,
    FollowUpAgentConfig,
    ReflectionAgentConfig,
    ScrapingConfig,
    SearchAgentConfig,
    WriterAgentConfig,
)


def test_agent_config_defaults():
    cfg = AgentConfig(model="google-gla:gemini-2.5-flash")
    assert cfg.enabled is True
    assert cfg.thinking == "off"
    assert cfg.tool_call_budget == 3
    assert cfg.max_tokens is None


def test_agent_config_is_frozen():
    cfg = AgentConfig(model="google-gla:gemini-2.5-flash")
    with pytest.raises(FrozenInstanceError):
        cfg.model = "other"  # type: ignore[misc] — testing frozen behavior


def test_replace_creates_new_instance():
    cfg = AgentConfig(model="google-gla:gemini-2.5-flash")
    new = replace(cfg, model="google-gla:gemini-2.5-pro")
    assert new.model == "google-gla:gemini-2.5-pro"
    assert cfg.model == "google-gla:gemini-2.5-flash"


def test_search_agent_config_defaults():
    cfg = SearchAgentConfig()
    assert cfg.model == "google-gla:gemini-2.5-flash"
    assert cfg.num_queries == 3
    assert cfg.max_results == 5
    assert cfg.search_freshness == "qdr:w"


def test_writer_agent_config_defaults():
    cfg = WriterAgentConfig()
    assert cfg.model == "google-gla:gemini-2.5-pro"
    assert cfg.thinking == "medium"


def test_reflection_agent_enabled_by_default():
    cfg = ReflectionAgentConfig()
    assert cfg.enabled is True


def test_scraping_config_is_not_agent_config():
    cfg = ScrapingConfig()
    assert not isinstance(cfg, AgentConfig)
    assert cfg.max_concurrent_jina == 8


def test_followup_config_defaults():
    cfg = FollowUpAgentConfig()
    assert cfg.num_titles == 10
    assert cfg.num_topics == 5


def test_agent_config_has_fallback_models_field():
    cfg = SearchAgentConfig()
    assert hasattr(cfg, "fallback_models")
    assert cfg.fallback_models == ()


def test_agent_config_fallback_models_is_tuple():
    cfg = WriterAgentConfig(fallback_models=("openai:gpt-4o", "anthropic:claude-haiku-4-5"))
    assert cfg.fallback_models == ("openai:gpt-4o", "anthropic:claude-haiku-4-5")


def test_scraping_config_has_filter_fallback_models():
    cfg = ScrapingConfig()
    assert hasattr(cfg, "filter_fallback_models")
    assert cfg.filter_fallback_models == ()
