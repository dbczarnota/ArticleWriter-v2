import os

# Set LOGFIRE_TOKEN to empty BEFORE any import that may call load_dotenv().
# python-dotenv's default load_dotenv(override=False) won't overwrite an existing env var,
# so the empty string sticks. Then any logfire.configure(send_to_logfire="if-token-present")
# call later sees no token and runs offline — no spans ship to the Logfire backend.
os.environ["LOGFIRE_TOKEN"] = ""

# Force DB_BACKEND=null and clear DATABASE_URL so tests use NullArticleRepository
# regardless of what's in .env. Without this, every pipeline test would try to open
# asyncpg connections to localhost:5432 and crash with "Event loop is closed" at teardown.
os.environ["DB_BACKEND"] = "null"
os.environ["DATABASE_URL"] = ""
# Force AUTH_BACKEND=null so API tests get the NullAuthenticator (local-dev user)
# instead of trying to validate Kinde JWTs.
os.environ["AUTH_BACKEND"] = "null"

import logfire

logfire.configure(send_to_logfire=False, console=False)

import pytest  # noqa: E402

from backend.api.schemas import ArticleRequest  # noqa: E402
from backend.config import AppSettings  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_repo_factory_cache():
    """Repo factories use @lru_cache, so a test that mutates the in-memory
    state of a NullRepo would leak that state into the next test. Clear
    after each test so the next one gets a fresh repo. Cheap (cache_clear
    is O(1))."""
    yield
    from backend.repositories import reset_repo_cache

    reset_repo_cache()


@pytest.fixture
def default_settings() -> AppSettings:
    return AppSettings()


@pytest.fixture
def minimal_request() -> ArticleRequest:
    return ArticleRequest(topic="Dawid Podsiadło")


@pytest.fixture
def settings_from_minimal_request(minimal_request: ArticleRequest) -> AppSettings:
    return AppSettings.from_request(minimal_request)
