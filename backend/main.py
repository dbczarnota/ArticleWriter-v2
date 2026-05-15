# backend/main.py
import asyncio
import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from logging import basicConfig

# asyncio.create_subprocess_exec requires ProactorEventLoop on Windows.
# uvicorn --reload switches to SelectorEventLoop, breaking subprocess creation.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Suppress JWKS auto-spans before instrument_httpx() runs. Kinde's
# scripts.kinde.com/.well-known/jwks.json is fetched a handful of times
# per day (cached in process), carries no per-user info, and only matters
# if Kinde itself is down — which we'd notice via 401s on /v2/me. The
# OTEL httpx instrumentation reads this env var on init.
os.environ.setdefault(
    "OTEL_PYTHON_HTTPX_EXCLUDED_URLS",
    r"scripts\.kinde\.com/\.well-known/jwks",
)

import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import update

from backend.api.streams import router as streams_router
from backend.api.v2 import router as v2_router
from backend.database import close_db, get_db_backend, get_session_maker, init_db
from backend.db.models import Article
from tools.image_creator.routes import router as image_creator_router

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

# Trafilatura emits routine "wrong data type or not valid HTML" warnings
# every time tier-1 fails on a JS-only / paywall page — but the orchestrator
# already retries via Jina, so the warning is just noise. Drop it to ERROR
# so genuine library failures still surface.
logging.getLogger("trafilatura").setLevel(logging.ERROR)


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
    from backend.services.discovery.scheduler import start_scheduler, stop_scheduler
    from backend.services.stream_manager import init_stream_manager

    # Verify DB connectivity at startup when DB_BACKEND=postgres; no-op otherwise.
    await init_db()
    await start_scheduler()
    stream_manager = init_stream_manager()
    if get_db_backend() == "postgres":
        sm = get_session_maker()
        if sm is not None:
            async with sm() as session:
                await stream_manager.resume_active(session)
    try:
        yield
    finally:
        await stream_manager.stop_all()
        await stop_scheduler()
        await _fail_running_articles_on_shutdown()
        await close_db()


app = FastAPI(
    title="ArticleWriter v2",
    version="2.0",
    description=(
        "Backend for HeadlinesForge / Styl.fm — article-generation pipeline "
        "plus Discovery RSS-driven topic surfacing. All `/v2/*` endpoints are "
        "tenant-scoped via `X-Org-Code` + Kinde JWT."
    ),
    openapi_tags=[
        {"name": "articles", "description": "Article CRUD and generation entry point."},
        {"name": "discovery-topics", "description": "Discovery story-topic clustering."},
        {"name": "discovery-items", "description": "Raw RSS items pre-clustering."},
        {"name": "discovery-feeds", "description": "RSS feed runtime state and health."},
        {"name": "discovery-categories", "description": "Editor-defined classification tags."},
        {"name": "orgs", "description": "Tenant org bootstrap and listing."},
        {"name": "domain-config", "description": "Per-org editorial configuration."},
        {"name": "users", "description": "Caller identity."},
    ],
    lifespan=lifespan,
)
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

# CORS: default to wildcard for local dev. In prod, set CORS_ALLOWED_ORIGINS
# to a comma-separated list of frontend origins (e.g.
# "https://app.headlinesforge.com"). Wildcard means any page can trigger
# authenticated requests once the user is signed in via Kinde — fine for
# dev, dangerous for prod (LLM-cost amplification via CSRF-style attacks).
_cors_origins_env = os.environ.get("CORS_ALLOWED_ORIGINS", "*").strip()
_cors_origins: list[str] = (
    ["*"]
    if _cors_origins_env == "*"
    else [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    # Browsers reject credentials + wildcard origin combos. Only enable
    # credentials when the allowlist is explicit.
    allow_credentials=_cors_origins != ["*"],
)

app.include_router(v2_router)
app.include_router(streams_router)
app.include_router(image_creator_router, prefix="/v2")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
