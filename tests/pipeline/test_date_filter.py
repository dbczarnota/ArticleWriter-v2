import pytest
from datetime import datetime, timedelta
from agents._base.types import ParsedArticle


def _make_article(url: str, days_old: int | None) -> ParsedArticle:
    if days_old is None:
        pub_date = None
    else:
        pub_date = (datetime.now().date() - timedelta(days=days_old)).isoformat()
    return ParsedArticle(url=url, title="t", content="c", publication_date=pub_date)


def test_filter_keeps_recent():
    from agents.pipeline.runner import _filter_by_date
    articles = [_make_article("a", 5), _make_article("b", 60)]
    kept, reasons = _filter_by_date(articles, cutoff_days=30, manual_urls=set())
    assert len(kept) == 1
    assert kept[0].url == "a"


def test_filter_keeps_manual_url_regardless_of_date():
    from agents.pipeline.runner import _filter_by_date
    articles = [_make_article("manual", 365)]
    kept, reasons = _filter_by_date(articles, cutoff_days=30, manual_urls={"manual"})
    assert len(kept) == 1


def test_filter_keeps_no_date():
    from agents.pipeline.runner import _filter_by_date
    articles = [_make_article("nodate", None)]
    kept, reasons = _filter_by_date(articles, cutoff_days=30, manual_urls=set())
    assert len(kept) == 1


def test_filter_returns_reasons():
    from agents.pipeline.runner import _filter_by_date
    articles = [_make_article("old", 60), _make_article("new", 5)]
    kept, reasons = _filter_by_date(articles, cutoff_days=30, manual_urls=set())
    assert reasons["old"].startswith("Too old")
    assert "new" not in reasons
