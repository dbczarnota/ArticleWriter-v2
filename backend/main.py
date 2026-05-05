# backend/main.py
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from logging import basicConfig

# Suppress JWKS auto-spans before instrument_httpx() runs. Kinde's
# scripts.kinde.com/.well-known/jwks.json is fetched a handful of times
# per day (cached in process), carries no per-user info, and only matters
# if Kinde itself is down — which we'd notice via 401s on /v2/me. The
# OTEL httpx instrumentation reads this env var on init.
os.environ.setdefault(
    "OTEL_PYTHON_HTTPX_EXCLUDED_URLS",
    r"scripts\.kinde\.com/\.well-known/jwks",
)

import logfire  # noqa: E402  must come after the env var above
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import update

from backend.api.v2 import router as v2_router
from backend.database import close_db, get_db_backend, get_session_maker, init_db
from backend.db.models import Article

_log = logging.getLogger(__name__)

_PROMPT_FALSE_POSITIVES = {
    "cookie",  # parser prompt: "remove cookie banners"
    "auth",  # filter prompt: "AUTHORITY — established outlets..." / "authoritative"
}


def _scrub_callback(m: logfire.ScrubMatch):
    # Whitelist words that appear in legitimate prompt content. password/token/secret/
    # credentials/api_key/etc. stay scrubbed by default.
    if m.pattern_match.group(0).lower() in _PROMPT_FALSE_POSITIVES:
        return m.value
    return None


logfire.configure(
    send_to_logfire="if-token-present",
    service_name="articlewriter-v2",
    console=logfire.ConsoleOptions(min_log_level="warn"),
    scrubbing=logfire.ScrubbingOptions(callback=_scrub_callback),
)
logfire.instrument_pydantic_ai()
logfire.instrument_httpx()
basicConfig(handlers=[logfire.LogfireLoggingHandler()])


async def _fail_running_articles_on_shutdown() -> None:
    """Flip every in-flight article to 'failed' before the pod exits.

    Pipeline state lives in this process's event loop; once we exit,
    nothing advances it and the UI would spin forever on a 'running' row.
    Assumes replicas=1 — marking ALL running rows is safe because no other
    pod could have owned them. When we move to multiple replicas this needs
    a per-pod owner column or a job queue.
    """
    if get_db_backend() != "postgres":
        return
    sm = get_session_maker()
    if sm is None:
        return
    try:
        async with sm() as session:
            stmt = (
                update(Article)
                .where(Article.status == "running")  # type: ignore[arg-type]
                .values(
                    status="failed",
                    completed_at=datetime.now(UTC),
                    errors=[
                        {
                            "stage": "shutdown",
                            "error": "backend pod terminated mid-pipeline",
                        }
                    ],
                )
            )
            result = await session.execute(stmt)
            await session.commit()
            rowcount = getattr(result, "rowcount", 0) or 0
            if rowcount:
                logfire.warn(
                    "pipeline.shutdown_marked_failed",
                    rowcount=rowcount,
                )
    except Exception as exc:  # never block pod shutdown on this
        logfire.warn(
            "pipeline.shutdown_marked_failed",
            rowcount=0,
            error=str(exc),
            error_type=type(exc).__name__,
        )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Verify DB connectivity at startup when DB_BACKEND=postgres; no-op otherwise.
    await init_db()
    try:
        yield
    finally:
        await _fail_running_articles_on_shutdown()
        await close_db()


app = FastAPI(title="ArticleWriter v2", version="2.0", lifespan=lifespan)
# Quiet the noisy paths from auto-tracing:
# - /health: K8s liveness/readiness probe, fires every few seconds.
# - /v2/articles and /v2/articles/{id}: list refreshes + article switches
#   on the frontend. The interesting writes (POST /v2/write_article,
#   PATCH mark-done) emit explicit `article.created` / `article.marked_done`
#   events from the repository, so the FastAPI span is redundant.
logfire.instrument_fastapi(
    app,
    excluded_urls=["/health", "/v2/articles(/.*)?$"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v2_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
