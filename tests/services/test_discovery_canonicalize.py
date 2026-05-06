from backend.services.discovery.canonicalize import canonicalize_url


def test_strips_utm_params():
    assert canonicalize_url(
        "https://example.com/news?id=1&utm_source=rss&utm_medium=email"
    ) == "https://example.com/news?id=1"


def test_strips_all_utm_variants():
    assert canonicalize_url(
        "https://example.com/x?utm_campaign=a&utm_term=b&utm_content=c&keep=ok"
    ) == "https://example.com/x?keep=ok"


def test_strips_fbclid_gclid():
    assert canonicalize_url(
        "https://example.com/x?fbclid=abc&gclid=def&id=42"
    ) == "https://example.com/x?id=42"


def test_strips_fragment():
    assert canonicalize_url(
        "https://example.com/article#comments"
    ) == "https://example.com/article"


def test_lowercases_host_keeps_path_case():
    assert canonicalize_url(
        "https://Example.COM/Article/Path"
    ) == "https://example.com/Article/Path"


def test_idempotent():
    once = canonicalize_url("https://example.com/x?utm_source=a&keep=1")
    twice = canonicalize_url(once)
    assert once == twice == "https://example.com/x?keep=1"


def test_empty_query_drops_question_mark():
    assert canonicalize_url(
        "https://example.com/x?utm_source=a"
    ) == "https://example.com/x"


def test_preserves_existing_no_query():
    assert canonicalize_url("https://example.com/x") == "https://example.com/x"
