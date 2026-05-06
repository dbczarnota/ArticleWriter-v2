"""Repository factory + FastAPI dependency wrappers.

Picks the right implementation based on DB_BACKEND env:
- "postgres" -> Postgres-backed repos (B4), session_maker from backend.database
- "null" (default) -> Null repos (B5), no DB needed

Cached at module level so a single ArticleRepository instance is reused
across requests (sessions are per-call).
"""

from __future__ import annotations

from functools import lru_cache

from backend.database import get_db_backend, get_session_maker
from backend.repositories.discovery import PostgresDiscoveryRepository
from backend.repositories.null import (
    NullArticleRepository,
    NullDiscoveryRepository,
    NullOrgConfigRepository,
    NullOrgRepository,
)
from backend.repositories.postgres import (
    PostgresArticleRepository,
    PostgresOrgConfigRepository,
    PostgresOrgRepository,
)
from backend.repositories.protocols import (
    ArticleRepository,
    DiscoveryRepository,
    OrgConfigRepository,
    OrgRepository,
)


@lru_cache(maxsize=1)
def get_article_repo() -> ArticleRepository:
    """Return the configured ArticleRepository. Cached for process lifetime.

    FastAPI usage: `repo = Depends(get_article_repo)` in route handlers.
    Direct usage (run.py): `repo = get_article_repo()`.
    """
    if get_db_backend() == "postgres":
        sm = get_session_maker()
        if sm is None:
            raise RuntimeError(
                "DB_BACKEND=postgres but DATABASE_URL is unset or get_engine() returned None."
            )
        return PostgresArticleRepository(sm)
    return NullArticleRepository()


@lru_cache(maxsize=1)
def get_org_repo() -> OrgRepository:
    """Return the configured OrgRepository. Cached for process lifetime."""
    if get_db_backend() == "postgres":
        sm = get_session_maker()
        if sm is None:
            raise RuntimeError(
                "DB_BACKEND=postgres but DATABASE_URL is unset or get_engine() returned None."
            )
        return PostgresOrgRepository(sm)
    return NullOrgRepository()


@lru_cache(maxsize=1)
def get_org_config_repo() -> OrgConfigRepository:
    """Return the configured OrgConfigRepository. Cached for process lifetime."""
    if get_db_backend() == "postgres":
        sm = get_session_maker()
        if sm is None:
            raise RuntimeError(
                "DB_BACKEND=postgres but DATABASE_URL is unset or get_engine() returned None."
            )
        return PostgresOrgConfigRepository(sm)
    return NullOrgConfigRepository()


@lru_cache(maxsize=1)
def get_discovery_repo() -> DiscoveryRepository:
    """Return the configured DiscoveryRepository. Cached per process."""
    if get_db_backend() == "postgres":
        sm = get_session_maker()
        if sm is None:
            raise RuntimeError(
                "DB_BACKEND=postgres but DATABASE_URL is unset or get_engine() returned None."
            )
        return PostgresDiscoveryRepository(sm)
    return NullDiscoveryRepository()


def reset_repo_cache() -> None:
    """Clear cached repos. Use in tests when toggling DB_BACKEND between cases."""
    get_article_repo.cache_clear()
    get_org_repo.cache_clear()
    get_org_config_repo.cache_clear()
    get_discovery_repo.cache_clear()


__all__ = [
    "ArticleRepository",
    "OrgConfigRepository",
    "OrgRepository",
    "get_article_repo",
    "get_org_config_repo",
    "get_org_repo",
    "reset_repo_cache",
]
