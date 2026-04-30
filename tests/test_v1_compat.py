from agents._base.types import ArticleOutput, EmbedCandidate
from v1_compat import to_v1_html


def test_to_v1_html_shows_embed_candidates():
    output = ArticleOutput(
        html="<p>art</p>",
        embed_candidates=[
            EmbedCandidate(
                url="https://www.youtube.com/watch?v=abc",
                title="Melania wywiad",
                source="youtube",
                thumbnail_url="https://i.ytimg.com/vi/abc/hq.jpg",
                channel="TVN24",
            ),
            EmbedCandidate(
                url="https://x.com/user/status/1",
                title="Tweet o Melanii",
                source="twitter",
                description="Treść tweeta",
            ),
        ],
    )
    html = to_v1_html(output)
    assert "Media do osadzenia" in html
    assert "youtube.com/watch?v=abc" in html
    assert "TVN24" in html
    assert "x.com/user/status/1" in html


def test_to_v1_html_no_embed_section_when_empty():
    output = ArticleOutput(html="<p>art</p>")
    html = to_v1_html(output)
    assert "Media do osadzenia" not in html
