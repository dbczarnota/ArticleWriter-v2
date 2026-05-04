"""Verify _filter_by_date uses UTC, not local time."""

from datetime import UTC, datetime, timedelta

from agents._base.types import ParsedArticle
from agents.pipeline import runner


def _make_article(days_ago: int) -> ParsedArticle:
    dt = (datetime.now(UTC) - timedelta(days=days_ago)).date().isoformat()
    return ParsedArticle(url=f"https://ex.com/{days_ago}", title="T", content="C", publication_date=dt)


def test_filter_keeps_article_within_window():
    article = _make_article(days_ago=3)
    kept, reasons = runner._filter_by_date([article], cutoff_days=7, manual_urls=set())
    assert kept == [article], f"Article wrongly filtered: {reasons}"


def test_filter_removes_article_outside_window():
    article = _make_article(days_ago=10)
    kept, reasons = runner._filter_by_date([article], cutoff_days=7, manual_urls=set())
    assert kept == [], "Article should have been filtered but was kept"
    assert len(reasons) == 1
