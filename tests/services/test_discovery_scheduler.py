from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_master_tick_dispatches_eligible_orgs(monkeypatch):
    """Each master tick lists orgs, picks discovery-enabled ones, dispatches."""
    from backend.db.models import Org
    from backend.domain import DomainConfig, FeedConfig
    from backend.services.discovery import scheduler as sched

    org_a = Org(code="a", domain_name="d", name="A")
    org_b = Org(code="b", domain_name="d", name="B")  # disabled

    org_repo = AsyncMock()
    org_repo.list_all.return_value = [org_a, org_b]
    cfg_repo = AsyncMock()

    domain_a = DomainConfig(
        name="d", description="t",
        discovery_enabled=True,
        discovery_feeds=[FeedConfig(url="https://x/rss")],
    )
    domain_b = DomainConfig(name="d", description="t", discovery_enabled=False)

    async def _get_domain(code, _name, _cfg_repo):
        return domain_a if code == "a" else domain_b

    monkeypatch.setattr("backend.services.discovery.scheduler.get_org_repo", lambda: org_repo)
    monkeypatch.setattr("backend.services.discovery.scheduler.get_org_config_repo", lambda: cfg_repo)
    monkeypatch.setattr("backend.services.discovery.scheduler.get_discovery_repo", lambda: AsyncMock())
    monkeypatch.setattr("backend.domain.get_domain_config", _get_domain)

    poller = AsyncMock()
    monkeypatch.setattr("backend.services.discovery.scheduler.poll_org_feeds", poller)

    # Reset module state
    sched._last_run_at.clear()
    sched._inflight.clear()

    await sched._master_tick()

    # Drain dispatched tasks
    if sched._inflight:
        await asyncio.gather(*sched._inflight, return_exceptions=True)

    # Org A polled, B (disabled) skipped
    assert poller.await_count == 1
    assert poller.call_args.kwargs["org_code"] == "a"


@pytest.mark.asyncio
async def test_master_tick_respects_interval_eligibility(monkeypatch):
    """Same org polled twice in quick succession dispatches only once."""
    from backend.db.models import Org
    from backend.domain import DomainConfig, FeedConfig
    from backend.services.discovery import scheduler as sched

    org_a = Org(code="a", domain_name="d", name="A")
    org_repo = AsyncMock()
    org_repo.list_all.return_value = [org_a]

    domain_a = DomainConfig(
        name="d", description="t",
        discovery_enabled=True,
        discovery_feeds=[FeedConfig(url="https://x/rss", poll_interval_min=15)],
    )

    async def _get_domain(*_a, **_kw):
        return domain_a

    monkeypatch.setattr("backend.services.discovery.scheduler.get_org_repo", lambda: org_repo)
    monkeypatch.setattr("backend.services.discovery.scheduler.get_org_config_repo", lambda: AsyncMock())
    monkeypatch.setattr("backend.services.discovery.scheduler.get_discovery_repo", lambda: AsyncMock())
    monkeypatch.setattr("backend.domain.get_domain_config", _get_domain)

    poller = AsyncMock()
    monkeypatch.setattr("backend.services.discovery.scheduler.poll_org_feeds", poller)

    sched._last_run_at.clear()
    sched._inflight.clear()

    # First tick: dispatches
    await sched._master_tick()
    if sched._inflight:
        await asyncio.gather(*sched._inflight, return_exceptions=True)
    assert poller.await_count == 1

    # Second tick a moment later: still inside the 15-min window
    await sched._master_tick()
    if sched._inflight:
        await asyncio.gather(*sched._inflight, return_exceptions=True)
    assert poller.await_count == 1  # not re-dispatched


@pytest.mark.asyncio
async def test_stop_scheduler_drains_inflight(monkeypatch):
    """stop_scheduler waits for in-flight polls before returning."""
    from backend.services.discovery import scheduler as sched

    sched._last_run_at.clear()
    sched._inflight.clear()
    # Simulate a running scheduler via a mock so shutdown() doesn't raise.
    from unittest.mock import MagicMock

    mock_scheduler = MagicMock()
    sched._scheduler = mock_scheduler

    finished = asyncio.Event()

    async def _slow_poll() -> None:
        await asyncio.sleep(0.05)
        finished.set()

    task = asyncio.create_task(_slow_poll())
    sched._inflight.add(task)
    task.add_done_callback(sched._inflight.discard)

    await sched.stop_scheduler()
    assert finished.is_set()
