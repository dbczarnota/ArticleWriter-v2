from pathlib import Path
from domains._base.config import DomainConfig
from domains.styl_fm.examples import EXAMPLE_ARTICLES

_GUIDELINES_PATH = Path(__file__).parent / "guidelines.md"

STYL_FM_DOMAIN = DomainConfig(
    name="styl_fm",
    description="Polski portal lifestyle/celebryci. Clickbait, emocje, krótkie artykuły.",
    target_word_count=600,
    max_facts_in_article=8,
    max_quotes_in_article=3,
    default_search_freshness="qdr:d",   # newsy — domyślnie 24h
    default_num_queries=3,
    default_max_results=5,
    youtube_search=False,
    twitter_search=False,
    facebook_search=False,
    guidelines=_GUIDELINES_PATH.read_text(encoding="utf-8"),
    example_articles=EXAMPLE_ARTICLES,
)
