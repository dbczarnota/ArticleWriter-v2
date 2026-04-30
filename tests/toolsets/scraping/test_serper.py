import pytest
import respx
import httpx
from agents._base.types import SearchResult
from toolsets.scraping.serper import search


@pytest.mark.asyncio
@respx.mock
async def test_search_returns_search_results():
    respx.post("https://google.serper.dev/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "organic": [
                    {
                        "link": "https://example.com/artykul",
                        "title": "Dawid Podsiadło zarobił miliony",
                        "snippet": "Artysta zarobił 2 miliony na trasie.",
                    },
                    {
                        "link": "https://other.com/news",
                        "title": "Inna wiadomość",
                        "snippet": "Jakiś inny tekst.",
                    },
                ]
            },
        )
    )
    results = await search(
        "Dawid Podsiadło",
        num=10,
        freshness="qdr:d",
        language="pl",
        api_key="test-key",
    )
    assert len(results) == 2
    assert isinstance(results[0], SearchResult)
    assert results[0].url == "https://example.com/artykul"
    assert results[0].title == "Dawid Podsiadło zarobił miliony"
    assert results[0].snippet == "Artysta zarobił 2 miliony na trasie."
    assert results[0].source == "web"


@pytest.mark.asyncio
@respx.mock
async def test_search_empty_organic_returns_empty_list():
    respx.post("https://google.serper.dev/search").mock(
        return_value=httpx.Response(200, json={"organic": []})
    )
    results = await search("nic", num=5, freshness="qdr:w", language="pl", api_key="key")
    assert results == []


@pytest.mark.asyncio
@respx.mock
async def test_search_missing_snippet_uses_empty_string():
    respx.post("https://google.serper.dev/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "organic": [
                    {"link": "https://example.com", "title": "Tytuł"}
                ]
            },
        )
    )
    results = await search("test", num=5, freshness="qdr:w", language="pl", api_key="key")
    assert results[0].snippet == ""


@pytest.mark.asyncio
@respx.mock
async def test_search_http_error_raises():
    respx.post("https://google.serper.dev/search").mock(
        return_value=httpx.Response(401, json={"message": "Unauthorized"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        await search("test", num=5, freshness="qdr:w", language="pl", api_key="bad-key")
