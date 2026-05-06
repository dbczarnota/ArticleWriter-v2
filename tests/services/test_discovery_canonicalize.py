from backend.services.discovery.canonicalize import canonicalize_url


def test_strips_utm_params():
    assert (
        canonicalize_url("https://example.com/news?id=1&utm_source=rss&utm_medium=email")
        == "https://example.com/news?id=1"
    )


def test_strips_all_utm_variants():
    assert (
        canonicalize_url("https://example.com/x?utm_campaign=a&utm_term=b&utm_content=c&keep=ok")
        == "https://example.com/x?keep=ok"
    )


def test_strips_fbclid_gclid():
    assert (
        canonicalize_url("https://example.com/x?fbclid=abc&gclid=def&id=42")
        == "https://example.com/x?id=42"
    )


def test_strips_fragment():
    assert canonicalize_url("https://example.com/article#comments") == "https://example.com/article"


def test_lowercases_host_keeps_path_case():
    assert (
        canonicalize_url("https://Example.COM/Article/Path") == "https://example.com/Article/Path"
    )


def test_idempotent():
    once = canonicalize_url("https://example.com/x?utm_source=a&keep=1")
    twice = canonicalize_url(once)
    assert once == twice == "https://example.com/x?keep=1"


def test_empty_query_drops_question_mark():
    assert canonicalize_url("https://example.com/x?utm_source=a") == "https://example.com/x"


def test_preserves_existing_no_query():
    assert canonicalize_url("https://example.com/x") == "https://example.com/x"


def test_canonicalize_handles_empty_string():
    """Empty input shouldn't crash. Result is whatever urlparse decides;
    only requirement is no exception."""
    out = canonicalize_url("")
    assert isinstance(out, str)


def test_canonicalize_handles_javascript_scheme():
    """javascript:alert(1) is not a real http URL but the helper must
    not blow up. Whatever it returns, it's not our concern at this layer
    (the poller has scheme allowlist for actual fetches)."""
    out = canonicalize_url("javascript:alert(1)")
    assert isinstance(out, str)


def test_canonicalize_handles_very_long_url():
    """No length limit at this layer — caller may truncate before storage."""
    long_url = "https://example.com/" + "x" * 5000 + "?utm_source=spam"
    out = canonicalize_url(long_url)
    assert "utm_source" not in out


def test_canonicalize_handles_idn_punycode():
    """IDN domains pass through; we don't normalize unicode forms."""
    out = canonicalize_url("https://xn--80aax.example/article")
    assert "xn--80aax.example" in out
