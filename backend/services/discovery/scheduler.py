"""APScheduler hooks — start/stop discovery polling alongside FastAPI lifespan.

Design:
- A single master tick fires every minute. Each tick re-reads orgs and
  their DomainConfig, picks orgs whose discovery_enabled=True and whose
  last poll was at least `min(feed.poll_interval_min)` minutes ago, and
  dispatches one asyncio.Task per such org running poll_org_feeds.
- Re-reading on every tick means new orgs (created via JWT-bootstrap
  after startup), config edits (toggling discovery_enabled, changing
  feed list, changing interval), all become effective on the next tick
  with no restart needed.
- All dispatched tasks are tracked in a set so stop_scheduler can
  await them with a bounded timeout before close_db disposes the
  engine — eliminates the race where an in-flight poll writes to a
  closed engine.

Multi-replica safety lives one layer down inside poll_org_feeds via
pg_try_advisory_xact_lock per feed. The scheduler does not need its
own lock; if two replicas tick at the same wall-clock minute, both
will dispatch poll_org_feeds for the same orgs but the first to
acquire the per-feed advisory lock will do the work."""

from __future__ import annotations

import asyncio
import time

import logfire
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.repositories import get_discovery_repo, get_org_config_repo, get_org_repo
from backend.services.discovery.poller import poll_org_feeds

_MASTER_TICK_MINUTES = 1
"""How often the master job runs. Granularity ceiling — feeds with
poll_interval_min < this won't be checked more often than this."""

_SHUTDOWN_TIMEOUT_S = 30.0
"""Maximum time we wait for in-flight polls to drain before disposing
the DB engine. Beyond this, we proceed and risk asyncpg complaining."""


_scheduler: AsyncIOScheduler | None = None
_inflight: set[asyncio.Task[None]] = set()
_last_run_at: dict[str, float] = {}
"""org_code -> monotonic seconds of last completed poll dispatch."""


async def _poll_org_safely(org_code: str) -> None:
    """Wrap poll_org_feeds: load fresh config, run, never raise.

    Each org-tick is a fresh asyncio task (created in _master_tick) and
    therefore starts in a clean OTEL context. Setting baggage at the top
    here ensures any sub-spans the tick emits (config-load DB calls,
    upstream poll_org_feeds nested baggage, etc) inherit org_code so a
    Logfire query `WHERE attributes['org_code'] = X` returns the whole
    timeline."""
    with logfire.set_baggage(org_code=org_code):
        try:
            org_repo = get_org_repo()
            cfg_repo = get_org_config_repo()
            org = await org_repo.get(org_code)
            if org is None:
                return

            from backend.domain import get_domain_config

            domain = await get_domain_config(org_code, org.domain_name, cfg_repo)
            if domain is None or not domain.discovery_enabled:
                return
            await poll_org_feeds(
                org_code=org_code,
                domain=domain,
                repo=get_discovery_repo(),
            )
        except Exception as e:
            # Master tick must never propagate; one org's failure cannot
            # take down the scheduler thread.
            logfire.warn(
                "discovery.scheduler.org_tick_failed",
                org_code=org_code,
                error_type=type(e).__name__,
                error_message=str(e)[:500],
            )


async def _master_tick() -> None:
    """One tick: discover orgs, dispatch eligible ones."""
    org_repo = get_org_repo()
    cfg_repo = get_org_config_repo()
    try:
        orgs = await org_repo.list_all()
    except Exception as e:
        logfire.warn(
            "discovery.scheduler.list_orgs_failed",
            error_type=type(e).__name__,
            error_message=str(e)[:500],
        )
        return

    now = time.monotonic()
    for org in orgs:
        try:
            from backend.domain import get_domain_config

            domain = await get_domain_config(org.code, org.domain_name, cfg_repo)
        except Exception:
            continue
        if domain is None or not domain.discovery_enabled or not domain.discovery_feeds:
            continue
        # Eligibility check: respect per-feed minimum interval.
        interval_s = max(60, min(f.poll_interval_min for f in domain.discovery_feeds) * 60)
        last = _last_run_at.get(org.code)
        if last is not None and (now - last) < interval_s:
            continue
        # Mark optimistically — we'd rather skip a tick than over-poll.
        _last_run_at[org.code] = now
        # Dispatch. The set tracks the task for shutdown drain.
        task = asyncio.create_task(_poll_org_safely(org.code))
        _inflight.add(task)
        task.add_done_callback(_inflight.discard)


async def start_scheduler() -> None:
    """Boot the scheduler with a single master tick. Idempotent."""
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _master_tick,
        "interval",
        minutes=_MASTER_TICK_MINUTES,
        id="discovery_master_tick",
        replace_existing=True,
    )
    _scheduler.start()
    logfire.info(
        "discovery.scheduler.started",
        master_tick_minutes=_MASTER_TICK_MINUTES,
    )


async def stop_scheduler() -> None:
    """Stop the master tick and drain any in-flight polls. Bounded by
    _SHUTDOWN_TIMEOUT_S so a stuck poll cannot block shutdown forever."""
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None

    inflight = list(_inflight)
    if not inflight:
        return
    logfire.info(
        "discovery.scheduler.draining",
        inflight=len(inflight),
        timeout_s=_SHUTDOWN_TIMEOUT_S,
    )
    try:
        await asyncio.wait_for(
            asyncio.gather(*inflight, return_exceptions=True),
            timeout=_SHUTDOWN_TIMEOUT_S,
        )
    except TimeoutError:
        logfire.warn(
            "discovery.scheduler.drain_timeout",
            stuck=len([t for t in inflight if not t.done()]),
        )
