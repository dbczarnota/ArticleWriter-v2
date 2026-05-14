"""StreamSessionManager — lifecycle manager for stream subscription tasks.

Singleton pattern: module-level _manager, initialized via init_stream_manager()
in FastAPI lifespan. Pipeline and API router both call get_stream_manager().
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from uuid import UUID

import logfire
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.stream_pipeline import run_subscription_pipeline

_log = logging.getLogger(__name__)

_SHUTDOWN_TIMEOUT_S = 10.0

_manager: StreamSessionManager | None = None


def get_stream_manager() -> StreamSessionManager:
    if _manager is None:
        raise RuntimeError(
            "StreamSessionManager not initialized — call init_stream_manager() first"
        )
    return _manager


def init_stream_manager() -> StreamSessionManager:
    global _manager
    _manager = StreamSessionManager()
    return _manager


class StreamSessionManager:
    def __init__(self) -> None:
        self._tasks: dict[UUID, asyncio.Task[None]] = {}
        self._queues: dict[UUID, list[asyncio.Queue[dict]]] = {}

    async def start(
        self,
        subscription_id: UUID,
        stream_url: str,
        chunk_duration_seconds: int,
        org_code: str,
        *,
        stream_type: str = "radio",
        url_refresh_url: str | None = None,
        url_refresh_headers: dict | None = None,
        url_refresh_field: str = "url",
        topic_merge_window_hours: int = 6,
        agent_models: dict[str, str] | None = None,
        agent_fallback_models: dict[str, list[str]] | None = None,
    ) -> None:
        """Start pipeline task for subscription_id. Idempotent."""
        if subscription_id in self._tasks and not self._tasks[subscription_id].done():
            return
        task = asyncio.create_task(
            run_subscription_pipeline(
                subscription_id,
                stream_url,
                chunk_duration_seconds,
                org_code,
                stream_type=stream_type,
                url_refresh_url=url_refresh_url,
                url_refresh_headers=url_refresh_headers or {},
                url_refresh_field=url_refresh_field,
                topic_merge_window_hours=topic_merge_window_hours,
                agent_models=agent_models,
                agent_fallback_models=agent_fallback_models,
            ),
            name=f"stream-{subscription_id}",
        )
        self._tasks[subscription_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(subscription_id, None))
        logfire.info("stream.manager.started", subscription_id=str(subscription_id))

    async def stop(self, subscription_id: UUID) -> None:
        """Cancel pipeline task and wait for it to finish."""
        task = self._tasks.get(subscription_id)
        if task and not task.done():
            task.cancel()
            await asyncio.wait({task}, timeout=5.0)
        self._tasks.pop(subscription_id, None)
        logfire.info("stream.manager.stopped", subscription_id=str(subscription_id))

    async def stop_all(self) -> None:
        """Cancel all tasks. Called on server shutdown."""
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=_SHUTDOWN_TIMEOUT_S,
                )
        self._tasks.clear()

    async def resume_active(self, session: AsyncSession) -> None:
        """Re-start tasks for all subscriptions with status='active' in DB.
        Called once at server startup.
        """
        from sqlmodel import select

        from backend.db.models import OrgConfig, StreamSubscription

        result = await session.execute(
            select(StreamSubscription).where(StreamSubscription.status == "active")  # type: ignore[arg-type]
        )
        subs = result.scalars().all()
        # Batch-load OrgConfig rows to avoid N+1 queries.
        org_codes = {sub.org_code for sub in subs}
        cfg_result = await session.execute(
            select(OrgConfig).where(OrgConfig.org_code.in_(org_codes))  # type: ignore[arg-type]
        )
        org_configs: dict[str, OrgConfig] = {
            cfg.org_code: cfg for cfg in cfg_result.scalars().all()
        }

        for sub in subs:
            cfg = org_configs.get(sub.org_code)
            await self.start(
                sub.id,
                sub.stream_url,
                sub.chunk_duration_seconds,
                sub.org_code,
                stream_type=sub.stream_type,
                url_refresh_url=sub.url_refresh_url,
                url_refresh_headers=sub.url_refresh_headers,
                url_refresh_field=sub.url_refresh_field,
                topic_merge_window_hours=sub.topic_merge_window_hours,
                agent_models=dict(cfg.agent_models) if cfg and cfg.agent_models else None,
                agent_fallback_models={k: list(v) for k, v in cfg.agent_fallback_models.items()}
                if cfg and cfg.agent_fallback_models
                else None,
            )
        if subs:
            logfire.info("stream.manager.resumed", count=len(subs))

    def register_sse_queue(self, subscription_id: UUID) -> asyncio.Queue[dict]:
        q: asyncio.Queue[dict] = asyncio.Queue()
        self._queues.setdefault(subscription_id, []).append(q)
        return q

    def unregister_sse_queue(self, subscription_id: UUID, q: asyncio.Queue[dict]) -> None:
        queues = self._queues.get(subscription_id, [])
        with contextlib.suppress(ValueError):
            queues.remove(q)

    async def broadcast(self, subscription_id: UUID, event: dict) -> None:
        for q in self._queues.get(subscription_id, []):
            await q.put(event)
