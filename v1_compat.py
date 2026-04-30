"""Convert ArticleOutput (v2 JSON) to the single-HTML-blob format that v1 sent to Make.com."""
from __future__ import annotations
from html import escape
from agents._base.types import ArticleOutput


_CSS = (
    "body{font-family:sans-serif;margin:20px}"
    "article{border:1px solid #ccc;padding:15px;margin-bottom:20px;background-color:#f9f9f9}"
    "section{margin-bottom:20px;border:1px solid #eee;padding:0 15px 15px 15px}"
    "h1,h2{color:#333}h1{border-bottom:2px solid #ccc;padding-bottom:5px}"
    "h2{border-bottom:1px solid #eee;padding-bottom:3px}"
    "ul{list-style-type:disc;margin-left:20px}li{margin-bottom:5px}"
    "blockquote{border-left:3px solid #ccc;padding-left:10px;margin-left:0;font-style:italic;color:#555}"
    ".source-item{margin-bottom:8px}"
    ".source-url{font-weight:bold}"
    ".source-status{font-style:italic;margin-left:10px;padding:2px 5px;border-radius:3px}"
    ".status-included{color:#2a8a2a;background-color:#e9f5e9}"
    ".status-excluded{color:#b95000;background-color:#fff8e1}"
    ".used-marker{background-color:#d4edda;color:#155724;border:1px solid #c3e6cb;"
    "padding:2px 6px;border-radius:4px;font-size:0.8em;font-weight:bold;"
    "margin-left:8px;display:inline-block;vertical-align:middle;}"
    ".error-report{border-color:#d32f2f;background-color:#ffebee}"
    ".error-report h2{color:#c00}"
)


def _section(title: str, items: list[str]) -> str:
    if items:
        lis = "".join(f"<li>{escape(i)}</li>" for i in items)
        content = f"<ul>{lis}</ul>"
    else:
        content = "<ul><li>Brak danych.</li></ul>"
    return f"<section><h2>{escape(title)}</h2>{content}</section>"


def _used_section(title: str, items: list[str]) -> str:
    used_marker = '<span class="used-marker">USED</span>'
    if items:
        lis = "".join(f"<li>{escape(i)}{used_marker}</li>" for i in items)
        content = f"<ul>{lis}</ul>"
    else:
        content = "<ul><li>Brak danych.</li></ul>"
    return f"<section><h2>{escape(title)}</h2>{content}</section>"


def _errors_section(errors: list[dict]) -> str:
    if not errors:
        return ""
    items = [f"<li><strong>{escape(e.get('stage','?'))}</strong>: {escape(e.get('error','?'))}</li>" for e in errors]
    content = f"<ul>{''.join(items)}</ul>"
    return f"<section class='error-report'><h2>Execution Errors</h2>{content}</section>"


def _sources_section(output: ArticleOutput) -> str:
    included = set(output.sources)
    all_urls = list(dict.fromkeys(output.scraped_urls + output.sources))  # preserve order, dedupe

    if not all_urls:
        return _section("Źródła i Status Przetwarzania", [])

    items = []
    for url in all_urls:
        safe_url = escape(url)
        if url in included:
            status = '<span class="source-status status-included">Included</span>'
        else:
            status = '<span class="source-status status-excluded">Scraped, not used</span>'
        items.append(
            f'<li class="source-item">'
            f'<span class="source-url">{safe_url}</span>{status}'
            f"</li>"
        )

    content = f"<ul>{''.join(items)}</ul>"
    return f"<section><h2>Źródła i Status Przetwarzania</h2>{content}</section>"


def to_v1_html(output: ArticleOutput) -> str:
    article = f"<article>\n{output.html}\n</article>"
    errors = _errors_section(output.errors)
    titles = _section("Alternatywne tytuły", output.alternative_titles)
    topics = _section("Tematy do rozważenia", output.followup_topics)
    sources = _sources_section(output)
    quotes = _used_section("Cytaty użyte w artykule", output.used_quotes)
    facts = _used_section("Fakty użyte w artykule", output.used_facts)

    return (
        "<!DOCTYPE html><html>"
        f'<head><title>Article Result</title><meta charset="UTF-8">'
        f"<style>{_CSS}</style></head><body>"
        f"{article}{errors}{titles}{topics}{sources}{quotes}{facts}"
        "</body></html>"
    )
