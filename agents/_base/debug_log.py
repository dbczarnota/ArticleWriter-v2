# agents/_base/debug_log.py
"""Rich debug logger for the article pipeline. Enabled via DEBUG=True in run_pipeline."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents._base.types import SearchResult, ScrapedPage, ParsedArticle
    from agents.extraction.agent import ExtractionResult
    from agents.instructions.agent import WritingBrief
    from agents.writer.agent import ArticleHtml
    from agents.reflection.agent import ReflectionFeedback
    from agents.adaptive_search.agent import AdaptiveSearchDecision


class PipelineLogger:
    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        if enabled:
            import sys, io
            from rich.console import Console
            utf8_out = io.open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
            self._c = Console(highlight=False, file=utf8_out)
        self._stage = 0

    # ── internal helpers ──────────────────────────────────────────────────

    def _rule(self, title: str, color: str = "cyan") -> None:
        from rich.rule import Rule
        self._c.print(Rule(f"[bold {color}]{title}[/]", style=color))

    def _kv(self, **kwargs: object) -> None:
        parts = "   ".join(f"[dim]{k}[/]  [white]{v}[/]" for k, v in kwargs.items())
        self._c.print(f"  {parts}")

    def _ok(self, msg: str) -> None:
        self._c.print(f"  [bold green]✓[/] {msg}")

    def _warn(self, msg: str) -> None:
        self._c.print(f"  [bold yellow]![/] {msg}")

    def _err(self, stage: str, exc: Exception) -> None:
        self._c.print(f"  [bold red]✗ {stage} ERROR:[/] [red]{exc}[/]")

    def _table(self, headers: list[str], rows: list[list[str]], max_rows: int = 20) -> None:
        from rich.table import Table
        t = Table(*headers, show_header=True, header_style="bold dim", box=None,
                  padding=(0, 1), show_edge=False)
        for row in rows[:max_rows]:
            t.add_row(*row)
        if len(rows) > max_rows:
            t.add_row(*[f"[dim]… {len(rows) - max_rows} more[/]"] + [""] * (len(headers) - 1))
        self._c.print(t)

    def _head(self, text: str, n: int = 300) -> str:
        text = text.strip()
        return text[:n] + ("…" if len(text) > n else "")

    def _next(self, name: str, color: str = "cyan") -> None:
        self._stage += 1
        self._rule(f"[{self._stage}] {name}", color)

    # ── public stage methods ───────────────────────────────────────────────

    def search_start(self, topic: str, num_queries: int, max_results: int, freshness: str,
                     news_search: bool = False) -> None:
        if not self._enabled: return
        self._next("SEARCH", "cyan")
        self._kv(topic=self._head(topic, 80), queries=num_queries,
                 max_results=max_results, freshness=freshness)
        if news_search:
            self._ok("news_search=True — /news runs in parallel with /search per query")

    def media_search_start(self, languages: tuple, flags: list[str], queries: list[str]) -> None:
        if not self._enabled: return
        self._next("MEDIA SEARCH", "cyan")
        self._kv(languages=list(languages), sources=flags)
        for i, q in enumerate(queries):
            lang = languages[i] if i < len(languages) else "?"
            self._ok(f"[{lang}] {q}")

    def media_search_done(self, candidates: list, errors: dict[str, str] | None = None) -> None:
        if not self._enabled: return
        self._next("MEDIA SEARCH", "cyan")
        if errors:
            for src, msg in errors.items():
                self._warn(f"{src} failed: {msg[:100]}")
        if not candidates:
            self._warn("no embed candidates found")
            return
        from collections import Counter
        counts = Counter(c.source for c in candidates)
        summary = "  ".join(f"{src}: {n}" for src, n in counts.items())
        self._ok(f"{len(candidates)} candidates  ({summary})")
        self._table(
            ["Source", "Title", "URL"],
            [[c.source, c.title[:45], c.url[:55]] for c in candidates],
        )

    def search_done(self, results: list[SearchResult]) -> None:
        if not self._enabled: return
        self._ok(f"{len(results)} results")
        if results:
            self._table(
                ["URL", "Title", "Snippet"],
                [[r.url[:60], r.title[:50], r.snippet[:60]] for r in results],
            )

    def scraping_start(self, n_search: int, n_extra: int) -> None:
        if not self._enabled: return
        self._next("SCRAPING", "cyan")
        self._kv(from_search=n_search, extra_urls=n_extra, total=n_search + n_extra)

    def scraping_done(self, pages: list[ScrapedPage], rejected: list[str]) -> None:
        if not self._enabled: return
        tier_counts: dict[str, int] = {}
        for p in pages:
            tier_counts[p.scrape_tier] = tier_counts.get(p.scrape_tier, 0) + 1
        tiers = "  ".join(f"{k}: {v}" for k, v in tier_counts.items())
        self._ok(f"{len(pages)} pages scraped  ({tiers})")
        if rejected:
            self._warn(f"{len(rejected)} rejected by LLM filter")
            for url in rejected[:5]:
                self._c.print(f"    [dim]✗ {url[:80]}[/]")

    def parsing_done(self, articles: list[ParsedArticle]) -> None:
        if not self._enabled: return
        self._next("PARSING", "cyan")
        self._ok(f"{len(articles)} articles parsed")
        if articles:
            self._table(
                ["URL", "Title", "Date"],
                [[a.url[:55], a.title[:45], a.publication_date or "—"] for a in articles],
            )

    def date_filter_done(self, kept: int, removed: int) -> None:
        if not self._enabled: return
        if removed:
            self._warn(f"date filter: kept {kept}, removed {removed} (too old)")

    def extraction_done(self, result: ExtractionResult) -> None:
        if not self._enabled: return
        self._next("EXTRACTION", "magenta")
        self._ok(f"{len(result.facts)} facts   {len(result.quotes)} quotes   "
                 f"{len(result.keywords)} keywords")
        if result.facts:
            self._c.print("  [bold]Facts:[/]")
            self._table(
                ["Text", "Context", "Source"],
                [[f.text[:55], f.context[:40], f.source_url[:40]] for f in result.facts],
            )
        if result.quotes:
            self._c.print("  [bold]Quotes:[/]")
            self._table(
                ["Quote", "Speaker", "Context"],
                [[q.text[:55], q.speaker[:25], q.context[:35]] for q in result.quotes],
            )
        if result.keywords:
            self._c.print(f"  [dim]keywords:[/] {', '.join(result.keywords)}")

    def adaptive_search_done(self, decision: AdaptiveSearchDecision, round_n: int) -> None:
        if not self._enabled: return
        self._next(f"ADAPTIVE SEARCH (round {round_n})", "yellow")
        if decision.needs_more_research:
            self._warn(f"needs more research — {len(decision.additional_queries)} extra queries")
            for q in decision.additional_queries:
                self._c.print(f"    [yellow]→[/] {q}")
        else:
            self._ok("coverage sufficient, skipping extra search")
        if decision.reasoning:
            self._c.print(f"  [dim]reasoning:[/] {self._head(decision.reasoning, 120)}")

    def instructions_done(self, brief: WritingBrief) -> None:
        if not self._enabled: return
        self._next("INSTRUCTIONS", "blue")
        self._ok(f"{len(brief.selected_facts)} facts selected   "
                 f"{len(brief.selected_quotes)} quotes selected")
        if brief.selected_facts:
            self._c.print("  [bold]Selected facts:[/]")
            for f in brief.selected_facts:
                self._c.print(f"    [green]•[/] {self._head(f, 100)}")
        if brief.selected_quotes:
            self._c.print("  [bold]Selected quotes:[/]")
            for q in brief.selected_quotes:
                self._c.print(f"    [green]•[/] {self._head(q, 100)}")
        self._c.print(f"  [bold]Writing instructions:[/] {self._head(brief.writing_instructions, 300)}")

    def writer_done(self, article: ArticleHtml, round_n: int = 1) -> None:
        if not self._enabled: return
        label = "WRITER" if round_n == 1 else f"WRITER (revision {round_n})"
        self._next(label, "green")
        word_count = len(article.html.split())
        self._ok(f"{len(article.html)} chars  ~{word_count} words (HTML)")
        self._c.print(f"  [dim]preview:[/] {self._head(article.html, 400)}")

    def reflection_done(self, feedback: ReflectionFeedback, round_n: int = 1) -> None:
        if not self._enabled: return
        self._next(f"REFLECTION (round {round_n})", "yellow")
        self._c.print(f"  [bold]Feedback:[/] {self._head(feedback.feedback, 250)}")
        if feedback.priority_fixes:
            self._c.print("  [bold]Priority fixes:[/]")
            for fix in feedback.priority_fixes:
                self._c.print(f"    [yellow]→[/] {fix}")

    def usage_tracking_done(self, used_facts: list[str], used_quotes: list[str]) -> None:
        if not self._enabled: return
        self._next("USAGE TRACKING", "magenta")
        self._ok(f"{len(used_facts)} facts used   {len(used_quotes)} quotes used")
        for f in used_facts:
            self._c.print(f"    [green]✓[/] {self._head(f, 90)}")
        for q in used_quotes:
            self._c.print(f"    [green]✓[/] {self._head(q, 90)}")

    def followup_done(self, titles: list[str], topics: list[str]) -> None:
        if not self._enabled: return
        self._next("FOLLOW-UP", "cyan")
        self._ok(f"{len(titles)} alternative titles   {len(topics)} follow-up topics")
        for t in titles[:5]:
            self._c.print(f"    [cyan]•[/] {t}")
        if topics:
            self._c.print(f"  [dim]topics:[/] {', '.join(topics[:3])}")

    def error(self, stage: str, exc: Exception) -> None:
        if not self._enabled: return
        self._err(stage, exc)

    def done(self, sources: int, errors: int) -> None:
        if not self._enabled: return
        from rich.rule import Rule
        color = "green" if errors == 0 else "yellow"
        self._c.print(Rule(
            f"[bold {color}]PIPELINE DONE — {sources} sources   {errors} errors[/]",
            style=color,
        ))
