import logfire

logfire.configure(send_to_logfire=False, console=False)

import pytest  # noqa: E402 — must follow logfire.configure()

from backend.api.schemas import ArticleRequest  # noqa: E402
from backend.config import AppSettings  # noqa: E402


@pytest.fixture
def default_settings() -> AppSettings:
    return AppSettings()


@pytest.fixture
def minimal_request() -> ArticleRequest:
    return ArticleRequest(id="test-fixture", topic="Dawid Podsiadło")


@pytest.fixture
def settings_from_minimal_request(minimal_request: ArticleRequest) -> AppSettings:
    return AppSettings.from_request(minimal_request)
