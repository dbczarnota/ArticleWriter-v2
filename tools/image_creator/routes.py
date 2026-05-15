"""FastAPI routes for the Image Creator tool."""

from __future__ import annotations

import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse

from backend.auth.deps import get_current_org
from backend.database import get_session_maker
from backend.db.models import Org
from backend.repositories import get_article_repo, get_org_config_repo
from backend.repositories.protocols import ArticleRepository, OrgConfigRepository
from tools.image_creator import service
from tools.image_creator.config import (
    HTML2MEDIA_WEBHOOK_SECRET,
    PUBLIC_BASE_URL,
    WEBHOOK_PATH,
)
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
    config_repo: OrgConfigRepository = Depends(get_org_config_repo),
    article_repo: ArticleRepository = Depends(get_article_repo),
) -> CreateJobResponse:
    """Submit an HTML template to htmltomedia and return the job_id."""
    config = await config_repo.get(org.code)
    if config is None or not config.image_creator_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Image creator is not enabled for this organization.",
        )
    if not config.image_creator_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image creator API key is not configured.",
        )

    if body.article_id is not None:
        try:
            article_uuid = UUID(body.article_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid article_id.",
            ) from e
        article = await article_repo.get(article_uuid, org_code=org.code)
        if article is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found in this organization.",
            )

    callback_url = PUBLIC_BASE_URL + WEBHOOK_PATH
    job_id = await service.submit_job(
        html=body.html,
        article_id=body.article_id,
        org_code=org.code,
        template_name=body.template_name,
        callback_url=callback_url,
        api_key=config.image_creator_api_key,
    )
    return CreateJobResponse(job_id=job_id)


@router.get("/jobs/{job_id}/stream")
async def stream_job(job_id: str) -> StreamingResponse:
    """SSE stream that yields one event when the job completes.

    Auth note: this endpoint is intentionally unauthenticated because EventSource
    in the browser cannot attach custom headers. The job_id is a UUID4 (~122 bits
    of entropy) issued by htmltomedia and only returned to the original POSTer,
    so it acts as a capability token. If the job_id isn't in our in-memory
    registry, the stream closes immediately with no payload.
    """
    return StreamingResponse(
        service.wait_for_result(job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/webhook")
async def webhook(
    body: WebhookPayload,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
) -> dict:
    """Inbound callback from htmltomedia — notifies the waiting SSE stream.

    Requires `X-Webhook-Secret` header matching HTML2MEDIA_WEBHOOK_SECRET env
    var. Comparison is constant-time. If the env var is unset (dev mode),
    the endpoint rejects all calls — never accept unauthenticated webhooks
    even in dev, since they mutate articles.
    """
    if not HTML2MEDIA_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret not configured.",
        )
    if not x_webhook_secret or not secrets.compare_digest(
        x_webhook_secret, HTML2MEDIA_WEBHOOK_SECRET
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret.",
        )

    sm = get_session_maker()
    if sm is not None:
        async with sm() as session:  # type: ignore[union-attr]
            await service.handle_webhook(body.job_id, body.status, body.url, body.error, session)
    else:
        await service.handle_webhook(body.job_id, body.status, body.url, body.error, _NullSession())
    return {"ok": True}
