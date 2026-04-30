import pytest
from dataclasses import replace
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
        flags.reflection = False


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
        s.domain = "other"


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
