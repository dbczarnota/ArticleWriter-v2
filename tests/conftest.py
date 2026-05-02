import os

# Set LOGFIRE_TOKEN to empty BEFORE any import that may call load_dotenv().
# python-dotenv's default load_dotenv(override=False) won't overwrite an existing env var,
# so the empty string sticks. Then any logfire.configure(send_to_logfire="if-token-present")
# call later sees no token and runs offline — no spans ship to the Logfire backend.
os.environ["LOGFIRE_TOKEN"] = ""

import logfire

logfire.configure(send_to_logfire=False, console=False)

import pytest  # noqa: E402

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
