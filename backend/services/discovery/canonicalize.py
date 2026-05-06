"""URL canonicalization for cross-feed deduplication.

Strips tracking parameters and fragments so the same article from two RSS
sources hashes to the same canonical URL. Conservative — only drops the
parameters we know are pure tracking; everything else stays so we don't
collapse genuinely different URLs.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "utm_name",
        "fbclid",
        "gclid",
        "msclkid",
        "mc_eid",
        "mc_cid",
        "_ga",
        "ref",
        "ref_src",
    }
)


def canonicalize_url(url: str) -> str:
    """Return a stable form of `url` suitable for cross-feed dedup."""
    parsed = urlparse(url)
    pairs = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k not in _TRACKING_PARAMS
    ]
    new_query = urlencode(pairs)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            new_query,
            "",  # fragment dropped
        )
    )
