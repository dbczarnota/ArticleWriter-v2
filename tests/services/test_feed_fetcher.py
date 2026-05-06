from __future__ import annotations

import pytest
import respx
from httpx import Response

from backend.services.discovery.feed_fetcher import (
    FetchResult,
    fetch_feed,
)

_RSS_VALID = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>Test feed</title>
<item>
  <title>Article one</title>
  <link>https://example.com/a/1</link>
  <guid>guid-1</guid>
  <description>First summary</description>
  <pubDate>Mon, 04 May 2026 10:00:00 +0000</pubDate>
</item>
<item>
  <title>Article two</title>
  <link>https://example.com/a/2</link>
  <guid>guid-2</guid>
  <description>Second summary</description>
</item>
</channel></rss>"""


@pytest.mark.asyncio
@respx.mock
async def test_parses_valid_rss_200():
    respx.get("https://example.com/rss").mock(
        return_value=Response(
            200,
            text=_RSS_VALID,
            headers={"ETag": '"abc"', "Last-Modified": "Mon, 04 May 2026 11:00:00 GMT"},
        )
    )
    out = await fetch_feed("https://example.com/rss", etag=None, last_modified=None)
    assert isinstance(out, FetchResult)
    assert out.not_modified is False
    assert out.etag == '"abc"'
    assert out.last_modified == "Mon, 04 May 2026 11:00:00 GMT"
    assert len(out.items) == 2
    assert out.items[0].title == "Article one"
    assert out.items[0].url == "https://example.com/a/1"
    assert out.items[0].guid == "guid-1"


@pytest.mark.asyncio
@respx.mock
async def test_304_returns_empty_items():
    respx.get("https://example.com/rss").mock(return_value=Response(304))
    out = await fetch_feed(
        "https://example.com/rss", etag='"abc"', last_modified="Mon, 04 May 2026 11:00:00 GMT"
    )
    assert out.not_modified is True
    assert out.items == []
    assert out.etag == '"abc"'  # preserved


@pytest.mark.asyncio
@respx.mock
async def test_4xx_raises_fetch_error():
    from backend.services.discovery.feed_fetcher import FeedFetchError

    respx.get("https://example.com/rss").mock(return_value=Response(404))
    with pytest.raises(FeedFetchError):
        await fetch_feed("https://example.com/rss", etag=None, last_modified=None)


@pytest.mark.asyncio
@respx.mock
async def test_malformed_xml_returns_empty_items_no_error():
    """feedparser is forgiving — empty entries from a 200 should NOT raise."""
    respx.get("https://example.com/rss").mock(return_value=Response(200, text="<not></valid>"))
    out = await fetch_feed("https://example.com/rss", etag=None, last_modified=None)
    assert out.items == []


@pytest.mark.asyncio
@respx.mock
async def test_etag_and_last_modified_sent_as_request_headers():
    route = respx.get("https://example.com/rss").mock(return_value=Response(304))
    await fetch_feed(
        "https://example.com/rss",
        etag='"prev"',
        last_modified="Sun, 03 May 2026 10:00:00 GMT",
    )
    headers = route.calls.last.request.headers
    assert headers.get("If-None-Match") == '"prev"'
    assert headers.get("If-Modified-Since") == "Sun, 03 May 2026 10:00:00 GMT"
