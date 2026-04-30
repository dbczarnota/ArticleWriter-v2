# agents/pipeline/runner.py
from __future__ import annotations

from agents._base.types import ArticleOutput, ParsedArticle
from agents.extraction.agent import ExtractionResult, run_extraction_agent
from agents.search.agent import run_search_agent
from agents.scraping.agent import run_scraping_agent
from agents.parsing.agent import run_parsing_agent
from agents.adaptive_search.agent import run_adaptive_search_agent
from agents.instructions.agent import WritingBrief, run_instructions_agent
from agents.writer.agent import ArticleHtml, run_writer_agent
from agents.reflection.agent import run_reflection_agent
from agents.followup.agent import run_followup_agent
from agents.usage_tracking.agent import run_usage_tracking_agent
from backend.config import AppSettings
from domains._base.config import DomainConfig
from toolsets.scraping.serper import search as serper_search


async def run_pipeline(
    topic: str,
    *,
    settings: AppSettings,
    domain: DomainConfig,
    serper_api_key: str,
    jina_api_key: str | None = None,
    urls: list[str] | None = None,
    additional_instructions: str | None = None,
) -> ArticleOutput:
    from dataclasses import replace as dc_replace
    from agents._base.config import SearchAgentConfig

    _errors: list[dict[str, str]] = []
    _filter_reasons: dict[str, str] = {}

    # Apply domain freshness default when the caller hasn't explicitly overridden it
    if settings.search.search_freshness == SearchAgentConfig().search_freshness:
        settings = dc_replace(
            settings,
            search=dc_replace(settings.search, search_freshness=domain.default_search_freshness),
        )

    # Stage 1: Research
    try:
        search_results = await run_search_agent(
            topic,
            config=settings.search,
            domain_language=domain.language,
            serper_api_key=serper_api_key,
        )
    except Exception as e:
        _errors.append({"stage": "search", "error": str(e)})
        search_results = []

    try:
        scraped, rejected_by_filter = await run_scraping_agent(
            search_results,
            topic,
            scraping_config=settings.scraping,
            jina_api_key=jina_api_key,
            extra_urls=urls or [],
        )
        _filter_reasons = {url: "Not selected by filter" for url in rejected_by_filter}
    except Exception as e:
        _errors.append({"stage": "scraping", "error": str(e)})
        scraped = []

    try:
        articles = await run_parsing_agent(scraped, config=settings.parsing)
        scraped_urls: list[str] = [a.url for a in articles if a.url]
    except Exception as e:
        _errors.append({"stage": "parsing", "error": str(e)})
        articles = []
        scraped_urls = []

    if settings.pipeline.cutoff_days > 0:
        articles, _date_reasons = _filter_by_date(
            articles,
            cutoff_days=settings.pipeline.cutoff_days,
            manual_urls=set(urls or []),
        )
        scraped_urls = [a.url for a in articles if a.url]
        _filter_reasons.update(_date_reasons)

    try:
        extraction = await run_extraction_agent(
            articles,
            topic=topic,
            language=domain.language,
            config=settings.extraction,
        )
    except Exception as e:
        _errors.append({"stage": "extraction", "error": str(e)})
        extraction = ExtractionResult(facts=[], quotes=[], keywords=[])

    # Stage 2: Adaptive search loop
    if settings.pipeline.adaptive_search:
        try:
            seen_urls: set[str] = {r.url for r in search_results}
            for _ in range(settings.adaptive_search_agent.max_additional_rounds):
                decision = await run_adaptive_search_agent(
                    extraction,
                    topic=topic,
                    config=settings.adaptive_search_agent,
                )
                if not decision.needs_more_research or not decision.additional_queries:
                    break
                extra_results = []
                for query in decision.additional_queries:
                    for r in await serper_search(
                        query,
                        num=settings.search.max_results,
                        freshness=settings.search.search_freshness,
                        language=domain.language,
                        api_key=serper_api_key,
                    ):
                        if r.url not in seen_urls:
                            seen_urls.add(r.url)
                            extra_results.append(r)
                if not extra_results:
                    break
                extra_scraped = await run_scraping_agent(
                    extra_results,
                    topic,
                    scraping_config=settings.scraping,
                    jina_api_key=jina_api_key,
                )
                extra_articles = await run_parsing_agent(extra_scraped, config=settings.parsing)
                extra_extraction = await run_extraction_agent(
                    extra_articles,
                    topic=topic,
                    language=domain.language,
                    config=settings.extraction,
                )
                extraction = _merge_extraction(extraction, extra_extraction)
        except Exception as e:
            _errors.append({"stage": "adaptive_search", "error": str(e)})

    # Stage 3: Writing
    try:
        brief = await run_instructions_agent(
            extraction,
            topic=topic,
            domain=domain,
            config=settings.instructions,
            additional_instructions=additional_instructions,
        )
    except Exception as e:
        _errors.append({"stage": "instructions", "error": str(e)})
        brief = WritingBrief(selected_facts=[], selected_quotes=[], writing_instructions="")

    try:
        article = await run_writer_agent(
            brief,
            topic=topic,
            domain=domain,
            config=settings.writer,
            additional_instructions=additional_instructions,
        )
    except Exception as e:
        _errors.append({"stage": "writer", "error": str(e)})
        article = ArticleHtml(html="")

    # Stage 4: Reflection
    if settings.pipeline.reflection:
        try:
            feedback = await run_reflection_agent(
                article,
                topic=topic,
                domain=domain,
                config=settings.reflection,
            )
            article = await run_writer_agent(
                brief,
                topic=topic,
                domain=domain,
                config=settings.writer,
                reflection_feedback=feedback,
                additional_instructions=additional_instructions,
            )
        except Exception as e:
            _errors.append({"stage": "reflection", "error": str(e)})

    # Stage 5: Follow-up
    if settings.pipeline.followup:
        try:
            from dataclasses import replace as _replace
            result = await run_followup_agent(
                article,
                topic=topic,
                extraction_result=extraction,
                config=settings.followup,
            )
            try:
                used_facts, used_quotes = await run_usage_tracking_agent(
                    article,
                    extraction_result=extraction,
                    config=settings.usage_tracking,
                )
            except Exception as e:
                _errors.append({"stage": "usage_tracking", "error": str(e)})
                used_facts, used_quotes = [], []
            return _replace(
                result,
                used_facts=used_facts,
                used_quotes=used_quotes,
                sources=result.sources or scraped_urls,
                scraped_urls=scraped_urls,
                errors=_errors,
                filter_reasons=_filter_reasons,
            )
        except Exception as e:
            _errors.append({"stage": "followup", "error": str(e)})

    sources = list(
        {f.source_url for f in extraction.facts if f.source_url}
        | {q.source_url for q in extraction.quotes if q.source_url}
    ) or scraped_urls
    return ArticleOutput(
        html=article.html,
        alternative_titles=[],
        followup_topics=[],
        used_facts=[],
        used_quotes=[],
        sources=sources,
        scraped_urls=scraped_urls,
        errors=_errors,
        filter_reasons=_filter_reasons,
    )


def _filter_by_date(
    articles: list[ParsedArticle],
    cutoff_days: int,
    manual_urls: set[str],
) -> tuple[list[ParsedArticle], dict[str, str]]:
    from datetime import datetime, timedelta
    cutoff = datetime.now().date() - timedelta(days=cutoff_days)
    kept: list[ParsedArticle] = []
    reasons: dict[str, str] = {}
    for article in articles:
        if article.url in manual_urls:
            kept.append(article)
            continue
        if article.publication_date is None:
            kept.append(article)
            continue
        try:
            pub = datetime.fromisoformat(article.publication_date).date()
        except ValueError:
            kept.append(article)
            continue
        if pub < cutoff:
            reasons[article.url] = f"Too old: {pub}"
        else:
            kept.append(article)
    return kept, reasons


def _merge_extraction(base: ExtractionResult, extra: ExtractionResult) -> ExtractionResult:
    seen_facts = {f.text for f in base.facts}
    seen_quotes = {q.text for q in base.quotes}
    merged_facts = base.facts + [f for f in extra.facts if f.text not in seen_facts]
    merged_quotes = base.quotes + [q for q in extra.quotes if q.text not in seen_quotes]
    merged_keywords = list(dict.fromkeys(base.keywords + extra.keywords))
    return ExtractionResult(facts=merged_facts, quotes=merged_quotes, keywords=merged_keywords)
