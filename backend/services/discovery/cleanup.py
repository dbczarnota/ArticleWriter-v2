"""Daily cleanup of stale discovery + stream rows.

Each org has two retention windows on its DomainConfig:
- discovery_retention_days: cutoff for RSS items + topics (last_activity_at,
  fetched_at). Articles already published from those topics are NOT touched —
  only the discovery-layer metadata.
- stream_retention_days: cutoff for stream_topics (last_seen_at).

Runs once a day from the discovery scheduler. Soft-fails per-org so a bad
config or transient DB error doesn't block other orgs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import logfire
import sqlalchemy as sa

from backend.database import get_db_backend, get_session_maker
from backend.db.models import DiscoveryItem, DiscoveryTopic, StreamSubscription, StreamTopic
from backend.repositories import get_org_config_repo, get_org_repo


async def cleanup_for_org(org_code: str, domain_name: str) -> dict:
    """Delete rows older than the org's retention windows. Returns a dict
    with counts (items, topics, stream_topics) for telemetry."""
    if get_db_backend() != "postgres":
        return {"items": 0, "topics": 0, "stream_topics": 0}

    from backend.domain import get_domain_config

    domain = await get_domain_config(org_code, domain_name, get_org_config_repo())
    if domain is None:
        return {"items": 0, "topics": 0, "stream_topics": 0}

    now = datetime.now(UTC)
    rss_cutoff = now - timedelta(days=domain.discovery_retention_days)
    stream_cutoff = now - timedelta(days=domain.stream_retention_days)

    sm = get_session_maker()
    async with sm() as session:  # type: ignore[union-attr]
        items_res = await session.execute(
            sa.delete(DiscoveryItem).where(
                DiscoveryItem.org_code == org_code,  # type: ignore[arg-type]
                DiscoveryItem.fetched_at < rss_cutoff,  # type: ignore[arg-type]
            )
        )
        topics_res = await session.execute(
            sa.delete(DiscoveryTopic).where(
                DiscoveryTopic.org_code == org_code,  # type: ignore[arg-type]
                DiscoveryTopic.last_activity_at < rss_cutoff,  # type: ignore[arg-type]
            )
        )
        sub_ids_res = await session.execute(
            sa.select(StreamSubscription.id).where(StreamSubscription.org_code == org_code)  # type: ignore[arg-type]
        )
        sub_ids = [row[0] for row in sub_ids_res.all()]
        stream_count = 0
        if sub_ids:
            stream_res = await session.execute(
                sa.delete(StreamTopic).where(
                    StreamTopic.subscription_id.in_(sub_ids),  # type: ignore[arg-type]
                    StreamTopic.last_seen_at < stream_cutoff,  # type: ignore[arg-type]
                )
            )
            stream_count = stream_res.rowcount or 0
        await session.commit()

    return {
        "items": items_res.rowcount or 0,
        "topics": topics_res.rowcount or 0,
        "stream_topics": stream_count,
    }


async def cleanup_tick() -> None:
    """One pass over every org. Logs per-org outcomes."""
    if get_db_backend() != "postgres":
        return
    org_repo = get_org_repo()
    try:
        orgs = await org_repo.list_all()
    except Exception as e:
        logfire.warn(
            "discovery.cleanup.list_orgs_failed",
            error_type=type(e).__name__,
            error_message=str(e)[:500],
        )
        return

    for org in orgs:
        try:
            counts = await cleanup_for_org(org.code, org.domain_name)
            if counts["items"] or counts["topics"] or counts["stream_topics"]:
                logfire.info(
                    "discovery.cleanup.org_done",
                    org_code=org.code,
                    items=counts["items"],
                    topics=counts["topics"],
                    stream_topics=counts["stream_topics"],
                )
        except Exception as e:
            logfire.warn(
                "discovery.cleanup.org_failed",
                org_code=org.code,
                error_type=type(e).__name__,
                error_message=str(e)[:500],
            )
