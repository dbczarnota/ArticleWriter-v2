from toolsets.scraping._serper_q import compose_serper_q


def test_empty_include_and_exclude_returns_query_unchanged():
    assert compose_serper_q("Dawid Podsiadło") == "Dawid Podsiadło"


def test_single_include_uses_bare_site_no_or_group():
    assert compose_serper_q("topic", include=("wp.pl",)) == "topic site:wp.pl"


def test_multiple_include_uses_or_group():
    out = compose_serper_q("topic", include=("wp.pl", "onet.pl", "interia.pl"))
    assert out == "topic (site:wp.pl OR site:onet.pl OR site:interia.pl)"


def test_exclude_only():
    out = compose_serper_q("topic", exclude=("pudelek.pl", "plotek.pl"))
    assert out == "topic -site:pudelek.pl -site:plotek.pl"


def test_include_and_exclude_combined():
    out = compose_serper_q(
        "topic",
        include=("wp.pl", "onet.pl"),
        exclude=("pudelek.pl",),
    )
    assert out == "topic (site:wp.pl OR site:onet.pl) -site:pudelek.pl"


def test_whitespace_stripped_from_domains():
    out = compose_serper_q(
        "topic",
        include=("  wp.pl  ", "onet.pl"),
        exclude=(" pudelek.pl ",),
    )
    assert out == "topic (site:wp.pl OR site:onet.pl) -site:pudelek.pl"


def test_empty_string_domains_dropped():
    out = compose_serper_q(
        "topic",
        include=("wp.pl", "", "   "),
        exclude=("",),
    )
    assert out == "topic site:wp.pl"


def test_order_preserved():
    out = compose_serper_q("t", include=("c.pl", "a.pl", "b.pl"))
    assert out == "t (site:c.pl OR site:a.pl OR site:b.pl)"


def test_all_empty_after_strip_returns_query_unchanged():
    assert compose_serper_q("topic", include=("",), exclude=("   ",)) == "topic"
