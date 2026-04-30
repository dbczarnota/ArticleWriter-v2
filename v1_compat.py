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
    ".models-table{border-collapse:collapse;width:100%;font-size:0.9em}"
    ".models-table th,.models-table td{text-align:left;padding:4px 10px;border-bottom:1px solid #eee}"
    ".models-table th{color:#555;font-weight:bold}"
    ".stage-ok{color:#2a8a2a}.stage-err{color:#c00;font-weight:bold}"
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
    all_urls = list(dict.fromkeys(output.scraped_urls + output.sources + list(output.filter_reasons)))

    if not all_urls:
        return "<section><h2>Źródła i Status Przetwarzania</h2><ul><li>Brak danych.</li></ul></section>"

    items = []
    for url in all_urls:
        if url in included:
            css, label = "status-included", "Included"
        elif url in output.filter_reasons:
            css, label = "status-excluded", output.filter_reasons[url]
        else:
            css, label = "status-excluded", "Scraped, not used"
        safe_url = escape(url)
        items.append(
            f'<li class="source-item"><span class="source-url">{safe_url}</span>'
            f'<span class="source-status {css}">{escape(label)}</span></li>'
        )
    content = f"<ul>{''.join(items)}</ul>"
    return f"<section><h2>Źródła i Status Przetwarzania</h2>{content}</section>"


def _models_section(agent_models: dict[str, str], errors: list[dict]) -> str:
    error_stages = {e.get("stage", "") for e in errors}
    rows = ""
    for stage, model in agent_models.items():
        if stage in error_stages:
            status = '<span class="stage-err">&#x2717; error</span>'
        else:
            status = '<span class="stage-ok">&#x2713;</span>'
        rows += f"<tr><td>{escape(stage)}</td><td>{escape(model)}</td><td>{status}</td></tr>"
    return (
        "<section><h2>Modele</h2>"
        '<table class="models-table">'
        "<thead><tr><th>Agent</th><th>Model</th><th>Status</th></tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table></section>"
    )


def to_v1_html(output: ArticleOutput, agent_models: dict[str, str] | None = None) -> str:
    article = f"<article>\n{output.html}\n</article>"
    errors = _errors_section(output.errors)
    titles = _section("Alternatywne tytuły", output.alternative_titles)
    topics = _section("Tematy do rozważenia", output.followup_topics)
    sources = _sources_section(output)
    quotes = _used_section("Cytaty użyte w artykule", output.used_quotes)
    facts = _used_section("Fakty użyte w artykule", output.used_facts)
    models = _models_section(agent_models, output.errors) if agent_models else ""

    return (
        "<!DOCTYPE html><html>"
        f'<head><title>Article Result</title><meta charset="UTF-8">'
        f"<style>{_CSS}</style></head><body>"
        f"{article}{errors}{titles}{topics}{sources}{quotes}{facts}{models}"
        "</body></html>"
    )
