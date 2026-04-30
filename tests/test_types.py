from dataclasses import fields
from agents._base.types import Fact, Quote, ScrapedPage, ParsedArticle, SearchResult, VideoResult, ArticleOutput


def test_fact_has_required_context_field():
    f = Fact(
        text="zarobił 2 miliony złotych",
        context="Dawid Podsiadło, trasa Małomiasteczkowy 2025",
        source_url="https://example.com/artykul",
        source_title="Sukces trasy Podsiadło",
    )
    assert f.context == "Dawid Podsiadło, trasa Małomiasteczkowy 2025"
    assert f.source_url == "https://example.com/artykul"


def test_quote_has_speaker_and_context():
    q = Quote(
        text="To był najpiękniejszy rok w moim życiu",
        speaker="Dawid Podsiadło",
        context="o trasie koncertowej, wywiad dla Gazety Wyborczej",
        source_url="https://example.com/wywiad",
    )
    assert q.speaker == "Dawid Podsiadło"
    assert q.context != ""


def test_scraped_page_tracks_tier():
    page = ScrapedPage(
        url="https://example.com",
        title="Artykuł testowy",
        content="# Treść\n\nJakiś tekst.",
        scrape_tier="httpx",
    )
    assert page.scrape_tier in ("httpx", "jina", "firecrawl")


def test_search_result_sources():
    for source in ("web", "twitter", "facebook", "youtube"):
        r = SearchResult(
            url="https://example.com",
            title="Tytuł",
            snippet="Fragment tekstu",
            source=source,
        )
        assert r.source == source


def test_article_output_defaults():
    out = ArticleOutput(html="<h1>Test</h1>")
    assert out.alternative_titles == []
    assert out.followup_topics == []
    assert out.used_facts == []
    assert out.used_quotes == []
    assert out.sources == []
