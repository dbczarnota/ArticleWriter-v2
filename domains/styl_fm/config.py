from pathlib import Path

from domains._base.config import DomainConfig
from domains.styl_fm.examples import EXAMPLE_ARTICLES

_DIR = Path(__file__).parent
_GUIDELINES = (_DIR / "guidelines.md").read_text(encoding="utf-8")
_REFLECTION_STANCE = (_DIR / "reflection_stance.md").read_text(encoding="utf-8")

STYL_FM_DOMAIN = DomainConfig(
    name="styl_fm",
    description="Polski portal lifestyle/celebryci. Clickbait, emocje, krótkie artykuły.",
    language="pl",
    target_word_count=600,
    max_facts_in_article=8,
    max_quotes_in_article=3,
    default_search_freshness="qdr:w",
    default_num_queries=3,
    default_max_results=5,
    default_min_source_signals=4,  # require ≥4 facts+quotes; adaptive_search will keep digging until reached
    youtube_search=True,
    twitter_search=True,
    facebook_search=False,
    news_search=True,
    tiktok_search=True,
    instagram_search=True,
    reddit_search=True,
    media_search_languages=("en", "pl"),
    media_search_num=5,
    guidelines=_GUIDELINES,
    html_format=(
        "Article structure:\n"
        "- <h1>: Main clickbait title. Exactly one. Visual tags like [zdjęcia] or [wideo] go HERE and ONLY here.\n"
        "- <h2>: Section headings. At least 2. Must be factual, SEO-friendly, keyword-rich. NO clickbait. NO quotes inside <h2>. NO visual tags inside <h2>.\n"
        "- <p>: Body paragraphs. 3–5 sentences each.\n"
        "- <blockquote>: Direct quotes from named people.\n"
        "- <strong>: Emphasis within paragraphs — use sparingly.\n"
        "\n"
        "Hard rules:\n"
        "- Visual tags ([zdjęcia], [wideo], [galeria], [porównujemy zdjęcia]) appear ONLY in the <h1> title.\n"
        "- Never place a direct quote inside an <h2> heading.\n"
        "- Never include the publication date anywhere in the article.\n"
        "- No <html>, <head>, or <body> wrapper tags — article content only.\n"
        "- No markdown — HTML tags only."
    ),
    reflection_stance=_REFLECTION_STANCE,
    example_articles=tuple(EXAMPLE_ARTICLES),
)
