"""APScheduler hooks — start/stop discovery polling jobs alongside FastAPI lifespan.

Uses AsyncIOScheduler so jobs share the FastAPI event loop and Logfire
baggage propagates naturally. Multi-replica safety relies on the per-feed
DB lock inside record_feed_run / record_feed_error — both replicas are
free to attempt the same poll, but only one will commit a given feed
row update at a time."""

from __future__ import annotations

import logfire
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.repositories import get_discovery_repo, get_org_config_repo, get_org_repo
from backend.services.discovery.poller import poll_org_feeds

_scheduler: AsyncIOScheduler | None = None


async def _poll_org_job(org_code: str) -> None:
    """One scheduler tick = one org. Loads fresh config every run so
    edits to DomainConfig take effect on the next tick."""
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


async def start_scheduler() -> None:
    """Boot the in-process scheduler and register one job per org with
    discovery_enabled=True."""
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler()
    org_repo = get_org_repo()
    cfg_repo = get_org_config_repo()
    orgs = await org_repo.list_all()
    for org in orgs:
        from backend.domain import get_domain_config

        domain = await get_domain_config(org.code, org.domain_name, cfg_repo)
        if domain is None or not domain.discovery_enabled or not domain.discovery_feeds:
            continue
        interval_min = max(
            1, min(f.poll_interval_min for f in domain.discovery_feeds)
        )
        _scheduler.add_job(
            _poll_org_job,
            "interval",
            minutes=interval_min,
            args=[org.code],
            id=f"discovery_{org.code}",
            replace_existing=True,
        )
        logfire.info(
            "discovery.scheduler.job_registered",
            org_code=org.code,
            interval_min=interval_min,
        )
    _scheduler.start()


async def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
