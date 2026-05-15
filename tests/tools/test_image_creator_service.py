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
    respx.post("https://headlinesforge.com/html2media/images").mock(
        return_value=httpx.Response(200, json={"job_id": "abc-123"})
    )
    job_id = await service.submit_job(
        html="<h1>Test</h1>",
        article_id="art-1",
        org_code="org-1",
        template_name="Card",
        callback_url="https://headlinesforge.com/api/v2/tools/image-creator/webhook",
        api_key="htm_testkey",
    )
    assert job_id == "abc-123"
    assert "abc-123" in service._jobs
    assert service._jobs["abc-123"]["article_id"] == "art-1"


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
