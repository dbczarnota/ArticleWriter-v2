import pytest
import respx
import httpx
from toolsets.scraping.scraper_httpx import scrape_with_httpx

_ARTICLE_HTML = """
<!DOCTYPE html>
<html lang="pl">
<head><title>Dawid Podsiadło zarobił miliony</title></head>
<body>
  <article>
    <h1>Dawid Podsiadło zarobił miliony na trasie koncertowej</h1>
    <p>Znany artysta Dawid Podsiadło zarobił ponad 2 miliony złotych podczas swojej ostatniej trasy
    koncertowej. Trasa Małomiasteczkowy 2025 okazała się ogromnym sukcesem. Artysta wystąpił
    w kilkunastu miastach Polski, za każdym razem wyprzedając bilety w ciągu kilku minut.
    Fani czekali na ten moment od dawna i nie zawiedli się. Koncerty trwały ponad dwie godziny.</p>
    <p>Podsiadło po zakończeniu trasy udzielił wywiadu, w którym powiedział, że był to
    najpiękniejszy rok w jego życiu. Artysta zapowiada kolejną trasę na 2026 rok.</p>
  </article>
</body>
</html>
"""


@pytest.mark.asyncio
@respx.mock
async def test_scrape_with_httpx_returns_scraped_page():
    respx.get("https://example.com/artykul").mock(
        return_value=httpx.Response(200, text=_ARTICLE_HTML, headers={"content-type": "text/html"})
    )
    page = await scrape_with_httpx("https://example.com/artykul")
    assert page is not None
    assert page.url == "https://example.com/artykul"
    assert page.scrape_tier == "httpx"
    assert len(page.content) > 50


@pytest.mark.asyncio
@respx.mock
async def test_scrape_with_httpx_returns_none_on_404():
    respx.get("https://example.com/not-found").mock(
        return_value=httpx.Response(404)
    )
    page = await scrape_with_httpx("https://example.com/not-found")
    assert page is None


@pytest.mark.asyncio
@respx.mock
async def test_scrape_with_httpx_returns_none_on_empty_content():
    respx.get("https://example.com/empty").mock(
        return_value=httpx.Response(
            200,
            text="<html><body><p>ok</p></body></html>",
            headers={"content-type": "text/html"},
        )
    )
    page = await scrape_with_httpx("https://example.com/empty")
    # trafilatura won't extract content from such short page
    assert page is None


@pytest.mark.asyncio
@respx.mock
async def test_scrape_with_httpx_respects_custom_timeout():
    respx.get("https://example.com/slow").mock(side_effect=httpx.TimeoutException("timeout"))
    page = await scrape_with_httpx("https://example.com/slow", timeout=5.0)
    assert page is None
