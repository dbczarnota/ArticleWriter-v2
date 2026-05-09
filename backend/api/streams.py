"""Stream subscription API — subscribe/unsubscribe + SSE + polling."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import logfire
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import select

from backend.auth.deps import get_current_org
from backend.database import get_db_backend, get_session_maker
from backend.db.models import Org, StreamChunk, StreamDigest, StreamSubscription
from backend.services.stream_manager import get_stream_manager

router = APIRouter(prefix="/v2/streams", tags=["streams"])
_log = logging.getLogger(__name__)


class SubscriptionCreate(BaseModel):
    name: str
    stream_url: str
    chunk_duration_seconds: int = 120


class SubscriptionResponse(BaseModel):
    id: UUID
    org_code: str
    name: str
    stream_url: str
    status: str
    chunk_duration_seconds: int
    created_at: datetime
    started_at: datetime | None = None
    stopped_at: datetime | None = None


def _sub_to_response(sub: StreamSubscription) -> SubscriptionResponse:
    return SubscriptionResponse(
        id=sub.id,
        org_code=sub.org_code,
        name=sub.name,
        stream_url=sub.stream_url,
        status=sub.status,
        chunk_duration_seconds=sub.chunk_duration_seconds,
        created_at=sub.created_at,
        started_at=sub.started_at,
        stopped_at=sub.stopped_at,
    )


@router.post("/subscriptions", status_code=201, response_model=SubscriptionResponse)
async def create_subscription(
    body: SubscriptionCreate,
    org: Org = Depends(get_current_org),
) -> SubscriptionResponse:
    now = datetime.now(UTC)
    if get_db_backend() != "postgres":
        # NullRepo mode — in-memory stub (no DB persistence)
        sub = StreamSubscription(
            id=uuid4(),
            org_code=org.code,
            name=body.name,
            stream_url=body.stream_url,
            status="active",
            chunk_duration_seconds=body.chunk_duration_seconds,
            created_at=now,
            started_at=now,
        )
    else:
        sm = get_session_maker()
        sub = StreamSubscription(
            org_code=org.code,
            name=body.name,
            stream_url=body.stream_url,
            status="active",
            chunk_duration_seconds=body.chunk_duration_seconds,
            started_at=now,
        )
        async with sm() as session:  # type: ignore[union-attr]
            session.add(sub)
            await session.commit()
            await session.refresh(sub)

    manager = get_stream_manager()
    await manager.start(sub.id, sub.stream_url, sub.chunk_duration_seconds, org.code)
    logfire.info("stream.subscribed", subscription_id=str(sub.id), org_code=org.code)
    return _sub_to_response(sub)


@router.get("/subscriptions", response_model=list[SubscriptionResponse])
async def list_subscriptions(org: Org = Depends(get_current_org)) -> list[SubscriptionResponse]:
    if get_db_backend() != "postgres":
        return []
    sm = get_session_maker()
    async with sm() as session:  # type: ignore[union-attr]
        result = await session.execute(
            select(StreamSubscription).where(StreamSubscription.org_code == org.code)  # type: ignore[arg-type]
        )
        return [_sub_to_response(s) for s in result.scalars().all()]


@router.delete("/subscriptions/{subscription_id}", status_code=204)
async def delete_subscription(
    subscription_id: UUID,
    org: Org = Depends(get_current_org),
) -> Response:
    if get_db_backend() == "postgres":
        sm = get_session_maker()
        async with sm() as session:  # type: ignore[union-attr]
            sub = await session.get(StreamSubscription, subscription_id)
            if sub is None or sub.org_code != org.code:
                raise HTTPException(status_code=404, detail="Subscription not found")
            sub.status = "stopped"
            sub.stopped_at = datetime.now(UTC)
            session.add(sub)
            await session.commit()

    manager = get_stream_manager()
    await manager.stop(subscription_id)
    logfire.info("stream.unsubscribed", subscription_id=str(subscription_id), org_code=org.code)
    return Response(status_code=204)


@router.get("/subscriptions/{subscription_id}/results")
async def get_results(
    subscription_id: UUID,
    org: Org = Depends(get_current_org),
    since_chunk_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict]:
    if get_db_backend() != "postgres":
        return []
    sm = get_session_maker()
    async with sm() as session:  # type: ignore[union-attr]
        sub = await session.get(StreamSubscription, subscription_id)
        if sub is None or sub.org_code != org.code:
            raise HTTPException(status_code=404, detail="Subscription not found")

        since_start: float | None = None
        if since_chunk_id is not None:
            anchor = await session.get(StreamChunk, since_chunk_id)
            if anchor is not None:
                since_start = anchor.chunk_start_seconds

        stmt = select(StreamChunk).where(
            StreamChunk.subscription_id == subscription_id  # type: ignore[arg-type]
        )
        if since_start is not None:
            stmt = stmt.where(StreamChunk.chunk_start_seconds > since_start)  # type: ignore[arg-type]
        stmt = stmt.order_by(StreamChunk.chunk_start_seconds).limit(limit)  # type: ignore[arg-type]
        result = await session.execute(stmt)
        chunks = result.scalars().all()
        return [
            {
                "chunk_id": str(c.id),
                "chunk_start": c.chunk_start_seconds,
                "chunk_end": c.chunk_end_seconds,
                "speakers": c.speakers_detected,
                "topics": c.topics,
                "facts": c.facts,
                "quotes": c.quotes,
                "raw_transcript": c.raw_transcript,
                "processed_at": c.processed_at.isoformat(),
            }
            for c in chunks
        ]


@router.get("/subscriptions/{subscription_id}/results/stream")
async def stream_results(
    subscription_id: UUID,
    org: Org = Depends(get_current_org),
) -> StreamingResponse:
    """SSE endpoint — pushes new chunk events as they arrive."""
    manager = get_stream_manager()
    queue = manager.register_sse_queue(subscription_id)

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    event_type = event.get("type", "chunk")
                    data = json.dumps(event)
                    event_id = event.get("chunk_id") or event.get("digest_id") or ""
                    yield f"event: {event_type}\nid: {event_id}\ndata: {data}\n\n"
                except TimeoutError:
                    yield "event: keepalive\ndata: {}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            manager.unregister_sse_queue(subscription_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/subscriptions/{subscription_id}/digests")
async def get_digests(
    subscription_id: UUID,
    org: Org = Depends(get_current_org),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict]:
    if get_db_backend() != "postgres":
        return []
    sm = get_session_maker()
    async with sm() as session:  # type: ignore[union-attr]
        sub = await session.get(StreamSubscription, subscription_id)
        if sub is None or sub.org_code != org.code:
            raise HTTPException(status_code=404, detail="Subscription not found")

        stmt = (
            select(StreamDigest)
            .where(StreamDigest.subscription_id == subscription_id)  # type: ignore[arg-type]
            .order_by(StreamDigest.window_start_seconds)  # type: ignore[arg-type]
            .limit(limit)
        )
        result = await session.execute(stmt)
        digests = result.scalars().all()
        return [
            {
                "digest_id": str(d.id),
                "window_start": d.window_start_seconds,
                "window_end": d.window_end_seconds,
                "chunk_count": d.chunk_count,
                "stories": d.stories,
                "processed_at": d.processed_at.isoformat(),
            }
            for d in digests
        ]
