# tests/agents/pipeline/test_extract_social.py
import pytest
from agents._base.types import SearchResult
from agents.pipeline.runner import _extract_social_from_search


def _r(url: str, title: str = "T", snippet: str = "s") -> SearchResult:
    return SearchResult(url=url, title=title, snippet=snippet, source="web")


def test_non_social_url_stays_scrapable():
    results = [_r("https://example.com/article")]
    scrapable, embeds = _extract_social_from_search(results)
    assert len(scrapable) == 1
    assert len(embeds) == 0


def test_youtube_com_becomes_embed():
    results = [_r("https://youtube.com/watch?v=abc")]
    scrapable, embeds = _extract_social_from_search(results)
    assert len(scrapable) == 0
    assert len(embeds) == 1
    assert embeds[0].source == "youtube"
    assert embeds[0].url == "https://youtube.com/watch?v=abc"


def test_www_youtube_com_becomes_embed():
    results = [_r("https://www.youtube.com/watch?v=abc")]
    _, embeds = _extract_social_from_search(results)
    assert embeds[0].source == "youtube"


def test_youtu_be_becomes_embed():
    results = [_r("https://youtu.be/abc123")]
    _, embeds = _extract_social_from_search(results)
    assert embeds[0].source == "youtube"


def test_twitter_com_becomes_embed():
    results = [_r("https://twitter.com/user/status/123")]
    _, embeds = _extract_social_from_search(results)
    assert embeds[0].source == "twitter"


def test_x_com_becomes_embed():
    results = [_r("https://x.com/user/status/456")]
    _, embeds = _extract_social_from_search(results)
    assert embeds[0].source == "twitter"


def test_tiktok_com_becomes_embed():
    results = [_r("https://www.tiktok.com/@user/video/1")]
    _, embeds = _extract_social_from_search(results)
    assert embeds[0].source == "tiktok"


def test_instagram_com_becomes_embed():
    results = [_r("https://instagram.com/p/abc/")]
    _, embeds = _extract_social_from_search(results)
    assert embeds[0].source == "instagram"


def test_reddit_com_becomes_embed():
    results = [_r("https://www.reddit.com/r/news/comments/abc/")]
    _, embeds = _extract_social_from_search(results)
    assert embeds[0].source == "reddit"


def test_snippet_becomes_description():
    results = [_r("https://youtube.com/watch?v=x", snippet="Great video")]
    _, embeds = _extract_social_from_search(results)
    assert embeds[0].description == "Great video"


def test_empty_snippet_gives_none_description():
    result = SearchResult(url="https://youtube.com/watch?v=x", title="T", snippet=None, source="web")
    _, embeds = _extract_social_from_search([result])
    assert embeds[0].description is None


def test_mixed_results_split_correctly():
    results = [
        _r("https://nytimes.com/article"),
        _r("https://youtube.com/watch?v=1"),
        _r("https://bbc.com/news/abc"),
        _r("https://twitter.com/user/status/1"),
    ]
    scrapable, embeds = _extract_social_from_search(results)
    assert len(scrapable) == 2
    assert len(embeds) == 2
    assert {e.source for e in embeds} == {"youtube", "twitter"}


def test_empty_input_returns_empty():
    scrapable, embeds = _extract_social_from_search([])
    assert scrapable == []
    assert embeds == []


def test_subdomain_not_matched_as_social():
    """fake-youtube.com must not match youtube.com."""
    results = [_r("https://fake-youtube.com/article")]
    scrapable, embeds = _extract_social_from_search(results)
    assert len(scrapable) == 1
    assert len(embeds) == 0
