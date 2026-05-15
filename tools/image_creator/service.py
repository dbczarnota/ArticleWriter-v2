"""Image creator service — htmltomedia job submission, SSE notification, DB persistence."""

from __future__ import annotations

import asyncio
import json
import secrets
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx
import sqlalchemy as sa

from tools.image_creator.config import HTML2MEDIA_ADMIN_SECRET, HTML2MEDIA_BASE_URL

# job_id → {"queue": asyncio.Queue, "article_id": str|None, "org_code": str,
#           "template_name": str, "nonce": str}
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

    Generates a per-job nonce and embeds it as a query parameter on the
    callback_url. htmltomedia treats the URL as opaque and replays it on
    completion. The webhook handler then verifies the nonce against what
    we stored — only we and htmltomedia know it, so a third party cannot
    forge a callback even if they guess the job_id.

    Returns the job_id issued by htmltomedia and registers an in-process
    asyncio.Queue so the SSE endpoint can await the webhook notification.
    """
    nonce = secrets.token_urlsafe(32)
    sep = "&" if "?" in callback_url else "?"
    callback_with_nonce = f"{callback_url}{sep}{urlencode({'nonce': nonce})}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{HTML2MEDIA_BASE_URL}/images",
            json={"html": html, "callback_url": callback_with_nonce},
            headers={"X-API-Key": api_key},
        )
        resp.raise_for_status()
        job_id: str = resp.json()["job_id"]

    _jobs[job_id] = {
        "queue": asyncio.Queue(maxsize=1),
        "article_id": article_id,
        "org_code": org_code,
        "template_name": template_name,
        "nonce": nonce,
    }
    return job_id


def verify_nonce(job_id: str, nonce: str | None) -> bool:
    """Constant-time check that nonce matches the one issued for job_id.

    Returns False if the job is unknown OR the nonce mismatches. Caller
    must reject the request on False.
    """
    job = _jobs.get(job_id)
    if job is None or nonce is None:
        return False
    return secrets.compare_digest(nonce, job["nonce"])


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
        # CAST(... AS jsonb) instead of '::jsonb' — SQLAlchemy's text() parser
        # sees '::' as colon-ambiguous and refuses to bind parameters around it.
        await db_session.execute(
            sa.text(
                "UPDATE articles "
                "SET generated_images = generated_images || CAST(:entry AS jsonb) "
                "WHERE id = CAST(:article_id AS uuid)"
            ),
            {"entry": json.dumps([entry]), "article_id": job["article_id"]},
        )
        await db_session.commit()


SSE_WAIT_TIMEOUT_SECONDS = 120.0


async def wait_for_result(job_id: str) -> AsyncIterator[str]:
    """Async generator that yields a single SSE data chunk then cleans up.

    Times out after SSE_WAIT_TIMEOUT_SECONDS (2 min) if no webhook arrives,
    yielding an error payload so the client can show feedback instead of
    hanging indefinitely.
    """
    job = _jobs.get(job_id)
    if job is None:
        payload = json.dumps({"status": "error", "error": "Job not found"})
        yield f"data: {payload}\n\n"
        return

    try:
        result = await asyncio.wait_for(
            job["queue"].get(), timeout=SSE_WAIT_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        result = {"status": "error", "url": None, "error": "Timed out waiting for image render"}
    finally:
        _jobs.pop(job_id, None)

    payload = json.dumps(result, ensure_ascii=False)
    yield f"data: {payload}\n\n"
