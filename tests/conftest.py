import logfire
logfire.configure(send_to_logfire="never", console=False)

import pytest
from backend.api.schemas import ArticleRequest
from backend.config import AppSettings


@pytest.fixture
def default_settings() -> AppSettings:
    return AppSettings()


@pytest.fixture
def minimal_request() -> ArticleRequest:
    return ArticleRequest(id="test-fixture", topic="Dawid Podsiadło")


@pytest.fixture
def settings_from_minimal_request(minimal_request: ArticleRequest) -> AppSettings:
    return AppSettings.from_request(minimal_request)
