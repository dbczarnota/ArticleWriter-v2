"""FastAPI routes for the Image Creator tool."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.auth.deps import get_current_org
from backend.database import get_session_maker
from backend.db.models import Org
from tools.image_creator import service
from tools.image_creator.config import PUBLIC_BASE_URL, WEBHOOK_PATH
from tools.image_creator.schemas import CreateJobRequest, CreateJobResponse, WebhookPayload

router = APIRouter(prefix="/tools/image-creator", tags=["image-creator"])


class _NullSession:
    """No-op session used when no real DB is available (SQLite dev mode)."""

    async def execute(self, *_a, **_kw):  # type: ignore[override]
        pass

    async def commit(self) -> None:
        pass


@router.post("/jobs", response_model=CreateJobResponse)
async def create_job(
    body: CreateJobRequest,
    org: Org = Depends(get_current_org),
) -> CreateJobResponse:
    """Submit an HTML template to htmltomedia and return the job_id."""
    callback_url = PUBLIC_BASE_URL + WEBHOOK_PATH
    job_id = await service.submit_job(
        html=body.html,
        article_id=body.article_id,
        org_code=org.code,
        template_name=body.template_name,
        callback_url=callback_url,
    )
    return CreateJobResponse(job_id=job_id)


@router.get("/jobs/{job_id}/stream")
async def stream_job(
    job_id: str,
    org: Org = Depends(get_current_org),
) -> StreamingResponse:
    """SSE stream that yields one event when the job completes."""
    return StreamingResponse(
        service.wait_for_result(job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/webhook")
async def webhook(body: WebhookPayload) -> dict:
    """Inbound callback from htmltomedia — notifies the waiting SSE stream."""
    sm = get_session_maker()
    if sm is not None:
        async with sm() as session:  # type: ignore[union-attr]
            await service.handle_webhook(body.job_id, body.status, body.url, body.error, session)
    else:
        await service.handle_webhook(body.job_id, body.status, body.url, body.error, _NullSession())
    return {"ok": True}
