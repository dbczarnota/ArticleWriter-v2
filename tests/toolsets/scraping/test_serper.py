import pytest
import respx
import httpx
from agents._base.types import SearchResult, EmbedCandidate
from toolsets.scraping.serper import search, search_news, search_videos, search_site


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


@pytest.mark.asyncio
@respx.mock
async def test_search_includes_language_restriction():
    route = respx.post("https://google.serper.dev/search").mock(
        return_value=httpx.Response(200, json={"organic": []})
    )
    await search("test", num=5, freshness="qdr:d", language="pl", api_key="k")
    import json
    body = json.loads(route.calls[0].request.content)
    assert body["lr"] == "lang_pl"


@pytest.mark.asyncio
@respx.mock
async def test_search_news_returns_search_results():
    respx.post("https://google.serper.dev/news").mock(
        return_value=httpx.Response(200, json={
            "news": [
                {"link": "https://plotek.pl/1", "title": "News 1", "snippet": "Snip 1"},
                {"link": "https://plotek.pl/2", "title": "News 2", "snippet": "Snip 2"},
            ]
        })
    )
    results = await search_news("Melania", num=5, language="pl", api_key="k")
    assert len(results) == 2
    assert results[0].url == "https://plotek.pl/1"
    assert results[0].source == "web"


@pytest.mark.asyncio
@respx.mock
async def test_search_videos_returns_embed_candidates():
    respx.post("https://google.serper.dev/videos").mock(
        return_value=httpx.Response(200, json={
            "videos": [
                {
                    "link": "https://www.youtube.com/watch?v=abc123",
                    "title": "Melania wywiad",
                    "snippet": "Opis",
                    "imageUrl": "https://i.ytimg.com/vi/abc123/hq.jpg",
                    "channel": "TVN24",
                }
            ]
        })
    )
    results = await search_videos("Melania", num=5, api_key="k")
    assert len(results) == 1
    assert isinstance(results[0], EmbedCandidate)
    assert results[0].source == "youtube"
    assert results[0].channel == "TVN24"
    assert results[0].thumbnail_url == "https://i.ytimg.com/vi/abc123/hq.jpg"


@pytest.mark.asyncio
@respx.mock
async def test_search_site_returns_embed_candidates():
    respx.post("https://google.serper.dev/search").mock(
        return_value=httpx.Response(200, json={
            "organic": [
                {"link": "https://x.com/user/status/1", "title": "Tweet 1", "snippet": "Treść"},
            ]
        })
    )
    results = await search_site("Melania", site="x.com", source="twitter",
                                num=5, api_key="k")
    assert len(results) == 1
    assert results[0].source == "twitter"
    assert results[0].url == "https://x.com/user/status/1"


@pytest.mark.asyncio
@respx.mock
async def test_search_news_empty_returns_empty():
    respx.post("https://google.serper.dev/news").mock(
        return_value=httpx.Response(200, json={"news": []})
    )
    results = await search_news("test", num=5, language="pl", api_key="k")
    assert results == []
