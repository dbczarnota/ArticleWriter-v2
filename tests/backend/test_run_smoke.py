"""Smoke test for run.py — the offline CLI entrypoint.

run.py executes asyncio.run(main()) at import time, so we can't `import run`
directly. Instead we verify:

1. run.py is syntactically valid (AST parse).
2. The deferred imports inside main() resolve in the current Python env.
3. With DB_BACKEND=null + AUTH_BACKEND=null, the persistence layer that
   run_pipeline depends on is NullArticleRepository (no DB needed).

Catches regressions where a refactor accidentally breaks the offline path.
"""

from __future__ import annotations

import ast
from pathlib import Path

_RUN_PY = Path(__file__).resolve().parents[2] / "run.py"


def test_run_py_parses():
    src = _RUN_PY.read_text(encoding="utf-8")
    ast.parse(src)


def test_run_py_deferred_imports_resolve():
    """The imports inside main() must be importable in this env."""
    from agents._base.config import SearchAgentConfig  # noqa: F401
    from agents.pipeline.runner import run_pipeline  # noqa: F401
    from backend.config import AppSettings  # noqa: F401
    from backend.domain import get_domain_config  # noqa: F401


def test_run_py_offline_uses_null_repos(monkeypatch):
    """With DB_BACKEND=null, get_article_repo() must return NullArticleRepository
    so run.py works without a Postgres container."""
    monkeypatch.setenv("DB_BACKEND", "null")

    from backend.repositories import (
        get_article_repo,
        get_org_repo,
        reset_repo_cache,
    )
    from backend.repositories.null import NullArticleRepository, NullOrgRepository

    reset_repo_cache()
    try:
        assert isinstance(get_article_repo(), NullArticleRepository)
        assert isinstance(get_org_repo(), NullOrgRepository)
    finally:
        reset_repo_cache()


async def test_null_repo_create_running_no_db(monkeypatch):
    """create_running on NullArticleRepository returns a UUID without touching a DB."""
    monkeypatch.setenv("DB_BACKEND", "null")
    from uuid import UUID

    from backend.repositories.null import NullArticleRepository

    repo = NullArticleRepository()
    article_id = await repo.create_running(
        org_code="__local_dev__",
        author_user_id="local-dev",
        domain_name="styl_fm",
        topic="Smoke topic",
    )
    assert isinstance(article_id, UUID)
