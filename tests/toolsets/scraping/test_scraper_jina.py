import pytest
import respx
import httpx
from toolsets.scraping.rate_limiter import reset_jina_semaphore
from toolsets.scraping.scraper_jina import scrape_with_jina

_JINA_CONTENT = """# Dawid Podsiadło zarobił miliony

Znany artysta Dawid Podsiadło zarobił ponad 2 miliony złotych podczas swojej ostatniej trasy
koncertowej. Trasa Małomiasteczkowy 2025 okazała się ogromnym sukcesem finansowym i artystycznym.
Fani czekali na ten moment od lat i nie zawiedli się.
"""


@pytest.fixture(autouse=True)
def reset_sem():
    reset_jina_semaphore()
    yield
    reset_jina_semaphore()


@pytest.mark.asyncio
@respx.mock
async def test_scrape_with_jina_returns_scraped_page():
    url = "https://example.com/artykul"
    respx.get(f"https://r.jina.ai/{url}").mock(
        return_value=httpx.Response(200, text=_JINA_CONTENT)
    )
    page = await scrape_with_jina(url, api_key="test-key")
    assert page is not None
    assert page.url == url
    assert page.scrape_tier == "jina"
    assert "Podsiadło" in page.content


@pytest.mark.asyncio
@respx.mock
async def test_scrape_with_jina_works_without_api_key():
    url = "https://example.com/artykul"
    respx.get(f"https://r.jina.ai/{url}").mock(
        return_value=httpx.Response(200, text=_JINA_CONTENT)
    )
    page = await scrape_with_jina(url, api_key=None)
    assert page is not None
    assert page.scrape_tier == "jina"


@pytest.mark.asyncio
@respx.mock
async def test_scrape_with_jina_returns_none_on_http_error():
    url = "https://example.com/blocked"
    respx.get(f"https://r.jina.ai/{url}").mock(
        return_value=httpx.Response(422)
    )
    page = await scrape_with_jina(url, api_key="key")
    assert page is None


@pytest.mark.asyncio
@respx.mock
async def test_scrape_with_jina_returns_none_on_empty_content():
    url = "https://example.com/empty"
    respx.get(f"https://r.jina.ai/{url}").mock(
        return_value=httpx.Response(200, text="krótki")
    )
    page = await scrape_with_jina(url, api_key="key")
    assert page is None


@pytest.mark.asyncio
@respx.mock
async def test_scrape_with_jina_sets_authorization_header_when_key_provided():
    url = "https://example.com/artykul"
    captured_headers = {}

    def capture(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, text=_JINA_CONTENT)

    respx.get(f"https://r.jina.ai/{url}").mock(side_effect=capture)
    await scrape_with_jina(url, api_key="my-secret-key")
    assert captured_headers.get("authorization") == "Bearer my-secret-key"
