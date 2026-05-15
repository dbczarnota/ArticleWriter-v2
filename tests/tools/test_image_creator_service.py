import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from tools.image_creator import service


@pytest.fixture(autouse=True)
def clear_jobs():
    service._jobs.clear()
    yield
    service._jobs.clear()


@respx.mock
@pytest.mark.asyncio
async def test_submit_job_calls_htmltomedia_and_stores_job():
    route = respx.post("https://headlinesforge.com/html2media/images").mock(
        return_value=httpx.Response(200, json={"job_id": "abc-123"})
    )
    job_id = await service.submit_job(
        html="<h1>Test</h1>",
        article_id="art-1",
        org_code="org-1",
        template_name="Card",
        callback_url="https://headlinesforge.com/v2/tools/image-creator/webhook",
        api_key="htm_testkey",
    )
    assert job_id == "abc-123"
    assert "abc-123" in service._jobs
    assert service._jobs["abc-123"]["article_id"] == "art-1"
    # Nonce is generated and stored
    assert isinstance(service._jobs["abc-123"]["nonce"], str)
    assert len(service._jobs["abc-123"]["nonce"]) >= 32
    # Nonce is appended as a query param to the callback URL we send to htmltomedia
    sent_body = route.calls.last.request.content.decode()
    assert "nonce=" in sent_body
    assert service._jobs["abc-123"]["nonce"] in sent_body


@respx.mock
@pytest.mark.asyncio
async def test_submit_job_preserves_existing_query_in_callback_url():
    route = respx.post("https://headlinesforge.com/html2media/images").mock(
        return_value=httpx.Response(200, json={"job_id": "abc-456"})
    )
    await service.submit_job(
        html="<h1>x</h1>",
        article_id=None,
        org_code="org-1",
        template_name="",
        callback_url="https://example.com/webhook?existing=1",
        api_key="k",
    )
    sent_body = route.calls.last.request.content.decode()
    assert "existing=1" in sent_body
    assert "&nonce=" in sent_body


@pytest.mark.asyncio
async def test_verify_nonce_accepts_matching_nonce():
    service._jobs["job-x"] = {
        "queue": asyncio.Queue(maxsize=1),
        "article_id": None,
        "org_code": "org-1",
        "template_name": "Card",
        "nonce": "the-secret-nonce-value-xyz",
    }
    assert service.verify_nonce("job-x", "the-secret-nonce-value-xyz") is True


@pytest.mark.asyncio
async def test_verify_nonce_rejects_wrong_nonce():
    service._jobs["job-x"] = {
        "queue": asyncio.Queue(maxsize=1),
        "article_id": None,
        "org_code": "org-1",
        "template_name": "Card",
        "nonce": "real-nonce",
    }
    assert service.verify_nonce("job-x", "wrong-nonce") is False


@pytest.mark.asyncio
async def test_verify_nonce_rejects_unknown_job():
    assert service.verify_nonce("nonexistent-job", "any-nonce") is False


@pytest.mark.asyncio
async def test_verify_nonce_rejects_none_nonce():
    service._jobs["job-x"] = {
        "queue": asyncio.Queue(maxsize=1),
        "article_id": None,
        "org_code": "org-1",
        "template_name": "Card",
        "nonce": "real-nonce",
    }
    assert service.verify_nonce("job-x", None) is False


@respx.mock
@pytest.mark.asyncio
async def test_enable_org_calls_htmltomedia_keys_endpoint():
    respx.post("https://headlinesforge.com/html2media/keys").mock(
        return_value=httpx.Response(200, json={"key": "htm_user_key_abc"})
    )
    key = await service.enable_org("org-test")
    assert key == "htm_user_key_abc"


@pytest.mark.asyncio
async def test_wait_for_result_yields_error_for_unknown_job():
    events = []
    async for chunk in service.wait_for_result("unknown-job-id"):
        events.append(chunk)
    assert len(events) == 1
    assert '"status": "error"' in events[0]
    assert "Job not found" in events[0]


@pytest.mark.asyncio
async def test_handle_webhook_puts_result_in_queue_no_article():
    service._jobs["job-1"] = {
        "queue": asyncio.Queue(maxsize=1),
        "article_id": None,
        "org_code": "org-1",
        "template_name": "Card",
    }
    db_mock = AsyncMock()
    await service.handle_webhook("job-1", "done", "https://example.com/img.jpg", None, db_mock)
    result = service._jobs["job-1"]["queue"].get_nowait()
    assert result == {"status": "done", "url": "https://example.com/img.jpg", "error": None}
    # no DB write since article_id is None
    db_mock.execute.assert_not_called()


@pytest.mark.asyncio
async def test_handle_webhook_unknown_job_does_not_raise():
    db_mock = AsyncMock()
    # should not raise
    await service.handle_webhook("nonexistent", "done", "https://x.com/img.jpg", None, db_mock)


@pytest.mark.asyncio
async def test_wait_for_result_yields_sse_event():
    service._jobs["job-2"] = {
        "queue": asyncio.Queue(maxsize=1),
        "article_id": None,
        "org_code": "org-1",
        "template_name": "Card",
    }
    await service._jobs["job-2"]["queue"].put(
        {"status": "done", "url": "https://x.com/r.jpg", "error": None}
    )

    events = []
    async for chunk in service.wait_for_result("job-2"):
        events.append(chunk)

    assert len(events) == 1
    assert '"status": "done"' in events[0]
    assert "job-2" not in service._jobs  # cleaned up
