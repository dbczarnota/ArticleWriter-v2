from dataclasses import replace

import pytest

from backend.config import AppSettings, PipelineFlags


def test_pipeline_flags_defaults():
    flags = PipelineFlags()
    assert flags.llm_knowledge is False
    assert flags.adaptive_search is True
    assert flags.reflection is True
    assert flags.followup is True


def test_pipeline_flags_is_frozen():
    flags = PipelineFlags()
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        flags.reflection = False  # type: ignore[misc] — testing frozen behavior


def test_app_settings_defaults():
    s = AppSettings()
    assert s.domain == "styl_fm"
    assert s.writer.model == "google-gla:gemini-2.5-pro"
    assert s.pipeline.adaptive_search is True
    assert s.scraping.max_concurrent_jina == 8


def test_app_settings_is_frozen():
    s = AppSettings()
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        s.domain = "other"  # type: ignore[misc] — testing frozen behavior


def test_app_settings_replace_writer_model():
    s = AppSettings()
    new_writer = replace(s.writer, model="google-gla:gemini-2.5-flash")
    s2 = replace(s, writer=new_writer)
    assert s2.writer.model == "google-gla:gemini-2.5-flash"
    assert s.writer.model == "google-gla:gemini-2.5-pro"  # oryginał niezmieniony


def test_available_models_not_empty():
    from backend.config import AVAILABLE_MODELS

    assert len(AVAILABLE_MODELS) >= 4
    assert all("id" in m and "label" in m for m in AVAILABLE_MODELS)


def test_from_request_empty_overrides():
    from backend.api.schemas import ArticleRequest

    req = ArticleRequest(topic="Dawid Podsiadło")
    s = AppSettings.from_request(req)
    assert s.domain == "styl_fm"
    assert s.writer.model == "google-gla:gemini-2.5-pro"


def test_from_request_model_override():
    from backend.api.schemas import ArticleRequest

    req = ArticleRequest(
        topic="Test",
        agents={"writer": {"model": "google-gla:gemini-2.5-flash"}},
    )
    s = AppSettings.from_request(req)
    assert s.writer.model == "google-gla:gemini-2.5-flash"
    assert s.instructions.model == "google-gla:gemini-2.5-pro"  # niezmienione


def test_from_request_pipeline_override():
    from backend.api.schemas import ArticleRequest

    req = ArticleRequest(
        topic="Test",
        pipeline={"reflection": False},
    )
    s = AppSettings.from_request(req)
    assert s.pipeline.reflection is False
    assert s.pipeline.adaptive_search is True  # niezmienione


def test_from_request_domain_override():
    from backend.api.schemas import ArticleRequest

    req = ArticleRequest(topic="Test", domain="the_economist")
    s = AppSettings.from_request(req)
    assert s.domain == "the_economist"


def test_from_request_invalid_agent_fields_ignored():
    from backend.api.schemas import ArticleRequest

    req = ArticleRequest(
        topic="Test",
        agents={"writer": {"nonexistent_field": "value", "model": "google-gla:gemini-2.5-flash"}},
    )
    s = AppSettings.from_request(req)
    assert s.writer.model == "google-gla:gemini-2.5-flash"
