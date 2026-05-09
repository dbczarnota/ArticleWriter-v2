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
    ) -> None:
        """Start pipeline task for subscription_id. Idempotent."""
        if subscription_id in self._tasks and not self._tasks[subscription_id].done():
            return
        task = asyncio.create_task(
            run_subscription_pipeline(
                subscription_id, stream_url, chunk_duration_seconds, org_code
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

        from backend.db.models import StreamSubscription

        result = await session.execute(
            select(StreamSubscription).where(StreamSubscription.status == "active")  # type: ignore[arg-type]
        )
        subs = result.scalars().all()
        for sub in subs:
            await self.start(sub.id, sub.stream_url, sub.chunk_duration_seconds, sub.org_code)
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
