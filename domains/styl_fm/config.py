from pathlib import Path
from domains._base.config import DomainConfig
from domains.styl_fm.examples import EXAMPLE_ARTICLES

_GUIDELINES_PATH = Path(__file__).parent / "guidelines.md"

STYL_FM_DOMAIN = DomainConfig(
    name="styl_fm",
    description="Polski portal lifestyle/celebryci. Clickbait, emocje, krótkie artykuły.",
    language="pl",
    target_word_count=600,
    max_facts_in_article=8,
    max_quotes_in_article=3,
    default_search_freshness="qdr:d",   # newsy — domyślnie 24h
    default_num_queries=3,
    default_max_results=5,
    youtube_search=True,
    twitter_search=True,
    facebook_search=False,
    news_search=True,
    tiktok_search=True,
    instagram_search=True,
    reddit_search=False,
    guidelines=_GUIDELINES_PATH.read_text(encoding="utf-8"),
    html_format=(
        "Use <h1> for the main title, <h2> for section headings, <p> for paragraphs. "
        "Wrap direct quotes from people in <blockquote>. "
        "No <html>, <head>, or <body> tags — article content only."
    ),
    example_articles=tuple(EXAMPLE_ARTICLES),
)
