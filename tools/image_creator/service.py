"""Image creator service — htmltomedia job submission, SSE notification, DB persistence."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import sqlalchemy as sa

from tools.image_creator.config import HTML2MEDIA_ADMIN_SECRET, HTML2MEDIA_BASE_URL

# job_id → {"queue": asyncio.Queue, "article_id": str|None, "org_code": str, "template_name": str}
_jobs: dict[str, dict[str, Any]] = {}


async def enable_org(org_code: str) -> str:
    """Create a new API key in htmltomedia for this org. Returns the raw key."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{HTML2MEDIA_BASE_URL}/keys",
            json={"label": org_code},
            headers={"X-Admin-Key": HTML2MEDIA_ADMIN_SECRET},
        )
        resp.raise_for_status()
        return resp.json()["key"]


async def submit_job(
    *,
    html: str,
    article_id: str | None,
    org_code: str,
    template_name: str,
    callback_url: str,
    api_key: str,
) -> str:
    """Submit an HTML-to-image job to the htmltomedia service.

    Returns the job_id issued by htmltomedia and registers an in-process
    asyncio.Queue so the SSE endpoint can await the webhook notification.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{HTML2MEDIA_BASE_URL}/images",
            json={"html": html, "callback_url": callback_url},
            headers={"X-API-Key": api_key},
        )
        resp.raise_for_status()
        job_id: str = resp.json()["job_id"]

    _jobs[job_id] = {
        "queue": asyncio.Queue(maxsize=1),
        "article_id": article_id,
        "org_code": org_code,
        "template_name": template_name,
    }
    return job_id


async def handle_webhook(
    job_id: str,
    status: str,
    url: str | None,
    error: str | None,
    db_session: Any,
) -> None:
    """Process an inbound webhook from htmltomedia.

    Puts the result onto the job's queue (so the waiting SSE stream can
    forward it to the browser), and — when the job was associated with an
    article and completed successfully — appends the image to the article's
    generated_images JSONB list.
    """
    job = _jobs.get(job_id)
    if job is None:
        return

    result = {"status": status, "url": url, "error": error}
    await job["queue"].put(result)

    if status == "done" and url and job["article_id"]:
        entry = {
            "url": url,
            "name": job["template_name"],
            "created_at": datetime.now(UTC).isoformat(),
        }
        await db_session.execute(
            sa.text(
                "UPDATE articles "
                "SET generated_images = generated_images || :entry::jsonb "
                "WHERE id = :article_id"
            ),
            {"entry": json.dumps([entry]), "article_id": job["article_id"]},
        )
        await db_session.commit()


async def wait_for_result(job_id: str) -> AsyncIterator[str]:
    """Async generator that yields a single SSE data chunk then cleans up."""
    job = _jobs.get(job_id)
    if job is None:
        return

    result = await job["queue"].get()
    payload = json.dumps(result, ensure_ascii=False)
    yield f"data: {payload}\n\n"
    _jobs.pop(job_id, None)
