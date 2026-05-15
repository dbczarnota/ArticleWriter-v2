"""FastAPI routes for the Image Creator tool."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from backend.auth.deps import get_current_org
from backend.database import get_session_maker
from backend.db.models import Org
from backend.repositories import get_article_repo, get_org_config_repo
from backend.repositories.protocols import ArticleRepository, OrgConfigRepository
from tools.image_creator import service
from tools.image_creator.config import PUBLIC_BASE_URL, WEBHOOK_PATH
from tools.image_creator.schemas import (
    CreateJobRequest,
    CreateJobResponse,
    EnableResponse,
    WebhookPayload,
)

router = APIRouter(prefix="/tools/image-creator", tags=["image-creator"])


@router.post("/enable", response_model=EnableResponse)
async def enable(
    org: Org = Depends(get_current_org),
    config_repo: OrgConfigRepository = Depends(get_org_config_repo),
) -> EnableResponse:
    """Enable Image Creator for this org.

    Idempotent: if an api_key is already provisioned in OrgConfig we just
    flip `image_creator_enabled` to True without touching htmltomedia.
    Otherwise we call htmltomedia to mint a new per-org key, persist it,
    and enable the feature.
    """
    config = await config_repo.get(org.code)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OrgConfig not found.",
        )

    if not config.image_creator_api_key:
        try:
            api_key = await service.enable_org(org.code)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to provision htmltomedia key: {e}",
            ) from e
        config.image_creator_api_key = api_key

    config.image_creator_enabled = True
    await config_repo.upsert(config)
    return EnableResponse(enabled=True)


@router.post("/disable", response_model=EnableResponse)
async def disable(
    org: Org = Depends(get_current_org),
    config_repo: OrgConfigRepository = Depends(get_org_config_repo),
) -> EnableResponse:
    """Disable Image Creator for this org.

    Keeps the api_key in storage so re-enabling later does not waste a
    provisioning call to htmltomedia.
    """
    config = await config_repo.get(org.code)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OrgConfig not found.",
        )
    config.image_creator_enabled = False
    await config_repo.upsert(config)
    return EnableResponse(enabled=False)


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


@router.delete("/articles/{article_id}/images")
async def delete_generated_image(
    article_id: UUID,
    url: str = Query(..., description="URL of the image to remove from generated_images"),
    org: Org = Depends(get_current_org),
    article_repo: ArticleRepository = Depends(get_article_repo),
) -> dict:
    """Remove a single generated image entry (matched by URL) from the
    article's generated_images JSONB array. Idempotent — no-op if no entry
    with that URL exists. R2 object is NOT deleted (cheap storage, kept for
    audit/recovery)."""
    article = await article_repo.get(article_id, org_code=org.code)
    if article is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found in this organization.",
        )

    sm = get_session_maker()
    if sm is None:
        return {"ok": True}
    async with sm() as session:  # type: ignore[union-attr]
        await session.execute(
            sa.text(
                "UPDATE articles "
                "SET generated_images = COALESCE( "
                "  (SELECT jsonb_agg(elem) "
                "   FROM jsonb_array_elements(generated_images) elem "
                "   WHERE elem->>'url' != :url), "
                "  CAST('[]' AS jsonb)) "
                "WHERE id = CAST(:article_id AS uuid) AND org_code = :org_code"
            ),
            {"url": url, "article_id": str(article_id), "org_code": org.code},
        )
        await session.commit()
    return {"ok": True}


@router.post("/webhook")
async def webhook(
    body: WebhookPayload,
    nonce: str = Query(..., description="Per-job nonce we issued in callback_url"),
) -> dict:
    """Inbound callback from htmltomedia — notifies the waiting SSE stream.

    Authentication: per-job nonce embedded as a query parameter on the
    callback URL we hand to htmltomedia. We compare it constant-time against
    the nonce we stored when submitting the job. An attacker forging this
    request would need to know both the job_id (UUID4) and the nonce (32-byte
    urlsafe token) — ~250 bits of combined entropy.
    """
    if not service.verify_nonce(body.job_id, nonce):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid nonce or unknown job.",
        )

    sm = get_session_maker()
    if sm is not None:
        async with sm() as session:  # type: ignore[union-attr]
            await service.handle_webhook(body.job_id, body.status, body.url, body.error, session)
    else:
        await service.handle_webhook(body.job_id, body.status, body.url, body.error, _NullSession())
    return {"ok": True}
