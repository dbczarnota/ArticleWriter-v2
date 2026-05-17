"""Compose Serper `q` string with site: include/exclude operators."""

from __future__ import annotations


def compose_serper_q(
    query: str,
    *,
    include: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
) -> str:
    """Append `(site:a OR site:b) -site:x -site:y` to query.

    Empty include + empty exclude returns the query unchanged.
    Domains are stripped of whitespace; empty entries are dropped.
    Order of input tuples is preserved (makes Logfire diffs readable).
    """
    inc = tuple(d.strip() for d in include if d and d.strip())
    exc = tuple(d.strip() for d in exclude if d and d.strip())

    if not inc and not exc:
        return query

    parts: list[str] = [query]

    if inc:
        if len(inc) == 1:
            parts.append(f"site:{inc[0]}")
        else:
            or_group = " OR ".join(f"site:{d}" for d in inc)
            parts.append(f"({or_group})")

    if exc:
        parts.extend(f"-site:{d}" for d in exc)

    return " ".join(parts)
