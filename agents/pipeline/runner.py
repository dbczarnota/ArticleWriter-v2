# agents/pipeline/runner.py
from __future__ import annotations

import asyncio
import time

import logfire

from agents._base.run_context import init_collector
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
from agents.media_search.agent import run_media_search
from backend.config import AppSettings
from backend.services.metrics import record_pipeline_run, record_stage, record_error
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
    debug: bool = False,
) -> ArticleOutput:
    from dataclasses import replace as dc_replace
    from agents._base.config import SearchAgentConfig
    from agents._base.debug_log import PipelineLogger

    log = PipelineLogger(enabled=debug)

    _errors: list[dict[str, str]] = []
    _filter_reasons: dict[str, str] = {}
    embed_candidates: list = []
    _timing: dict[str, float] = {}
    _token_records = init_collector()
    _pipeline_t0 = time.perf_counter()

    # Apply domain freshness default when the caller hasn't explicitly overridden it
    if settings.search.search_freshness == SearchAgentConfig().search_freshness:
        settings = dc_replace(
            settings,
            search=dc_replace(settings.search, search_freshness=domain.default_search_freshness),
        )

    # Apply domain news_search default
    if not settings.search.news_search and domain.news_search:
        settings = dc_replace(
            settings,
            search=dc_replace(settings.search, news_search=True),
        )

    # Stage 1: Research
    log.search_start(topic, settings.search.num_queries, settings.search.max_results,
                     settings.search.search_freshness, news_search=settings.search.news_search)
    _stage_t0 = time.perf_counter()
    with logfire.span("pipeline.stage.research", topic=topic, domain=domain.name):
        _search_result, _media_result = await asyncio.gather(
            run_search_agent(
                topic,
                config=settings.search,
                domain_language=domain.language,
                serper_api_key=serper_api_key,
            ),
            run_media_search(
                topic,
                domain=domain,
                serper_api_key=serper_api_key,
                freshness=settings.search.search_freshness,
                log=log,
            ),
            return_exceptions=True,
        )
    _timing["research"] = (time.perf_counter() - _stage_t0) * 1000
    record_stage("research", _timing["research"], domain.name)

    if isinstance(_search_result, Exception):
        _errors.append({"stage": "search", "error": str(_search_result)})
        log.error("search", _search_result)
        record_error("search")
        search_results = []
    else:
        search_results = _search_result
        log.search_done(search_results)

    if isinstance(_media_result, Exception):
        _errors.append({"stage": "media_search", "error": str(_media_result)})
        log.error("media_search", _media_result)
        record_error("media_search")
    else:
        embed_candidates, media_errors = _media_result
        log.media_search_done(embed_candidates, media_errors)

    log.scraping_start(len(search_results), len(urls or []))
    _stage_t0 = time.perf_counter()
    with logfire.span("pipeline.stage.scraping", domain=domain.name):
        try:
            scraped, rejected_by_filter = await run_scraping_agent(
                search_results,
                topic,
                scraping_config=settings.scraping,
                jina_api_key=jina_api_key,
                extra_urls=urls or [],
                max_pages=domain.max_pages_to_scrape,
            )
            _filter_reasons = {url: "Not selected by filter" for url in rejected_by_filter}
            log.scraping_done(scraped, rejected_by_filter)
        except Exception as e:
            _errors.append({"stage": "scraping", "error": str(e)})
            log.error("scraping", e)
            record_error("scraping")
            scraped = []
    _timing["scraping"] = (time.perf_counter() - _stage_t0) * 1000
    record_stage("scraping", _timing["scraping"], domain.name)

    _stage_t0 = time.perf_counter()
    with logfire.span("pipeline.stage.parsing", domain=domain.name):
        try:
            articles = await run_parsing_agent(scraped, config=settings.parsing)
            scraped_urls: list[str] = [a.url for a in articles if a.url]
            log.parsing_done(articles)
        except Exception as e:
            _errors.append({"stage": "parsing", "error": str(e)})
            log.error("parsing", e)
            record_error("parsing")
            articles = []
            scraped_urls = []
    _timing["parsing"] = (time.perf_counter() - _stage_t0) * 1000
    record_stage("parsing", _timing["parsing"], domain.name)

    if settings.pipeline.cutoff_days > 0:
        articles, _date_reasons = _filter_by_date(
            articles,
            cutoff_days=settings.pipeline.cutoff_days,
            manual_urls=set(urls or []),
        )
        scraped_urls = [a.url for a in articles if a.url]
        _filter_reasons.update(_date_reasons)
        log.date_filter_done(len(articles), len(_date_reasons))

    _stage_t0 = time.perf_counter()
    with logfire.span("pipeline.stage.extraction", domain=domain.name):
        try:
            extraction = await run_extraction_agent(
                articles,
                topic=topic,
                language=domain.language,
                config=settings.extraction,
            )
            log.extraction_done(extraction)
        except Exception as e:
            _errors.append({"stage": "extraction", "error": str(e)})
            log.error("extraction", e)
            record_error("extraction")
            extraction = ExtractionResult(facts=[], quotes=[], keywords=[])
    _timing["extraction"] = (time.perf_counter() - _stage_t0) * 1000
    record_stage("extraction", _timing["extraction"], domain.name)

    # Stage 2: Adaptive search loop
    if settings.pipeline.adaptive_search:
        _stage_t0 = time.perf_counter()
        with logfire.span("pipeline.stage.adaptive_search", domain=domain.name):
            try:
                seen_urls: set[str] = {r.url for r in search_results}
                for _round in range(settings.adaptive_search_agent.max_additional_rounds):
                    decision = await run_adaptive_search_agent(
                        extraction,
                        topic=topic,
                        config=settings.adaptive_search_agent,
                    )
                    log.adaptive_search_done(decision, _round + 1)
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
                    extra_scraped, _ = await run_scraping_agent(
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
                    log.extraction_done(extraction)
            except Exception as e:
                _errors.append({"stage": "adaptive_search", "error": str(e)})
                log.error("adaptive_search", e)
                record_error("adaptive_search")
        _timing["adaptive_search"] = (time.perf_counter() - _stage_t0) * 1000
        record_stage("adaptive_search", _timing["adaptive_search"], domain.name)

    # Stage 3: Writing
    _stage_t0 = time.perf_counter()
    with logfire.span("pipeline.stage.instructions", domain=domain.name):
        try:
            brief = await run_instructions_agent(
                extraction,
                topic=topic,
                domain=domain,
                config=settings.instructions,
                additional_instructions=additional_instructions,
            )
            log.instructions_done(brief)
        except Exception as e:
            _errors.append({"stage": "instructions", "error": str(e)})
            log.error("instructions", e)
            record_error("instructions")
            brief = WritingBrief(selected_facts=[], selected_quotes=[], writing_instructions="")
    _timing["instructions"] = (time.perf_counter() - _stage_t0) * 1000
    record_stage("instructions", _timing["instructions"], domain.name)

    _stage_t0 = time.perf_counter()
    with logfire.span("pipeline.stage.writer", domain=domain.name):
        try:
            article, _messages = await run_writer_agent(
                brief,
                topic=topic,
                domain=domain,
                config=settings.writer,
                additional_instructions=additional_instructions,
            )
            log.writer_done(article, round_n=1)
        except Exception as e:
            _errors.append({"stage": "writer", "error": str(e)})
            log.error("writer", e)
            record_error("writer")
            article = ArticleHtml(html="")
            _messages = []

        # Stage 4: Reflection (inside writer span — revision rounds)
        if settings.pipeline.reflection:
            try:
                for _round in range(settings.reflection.max_rounds):
                    feedback = await run_reflection_agent(
                        article,
                        topic=topic,
                        domain=domain,
                        config=settings.reflection,
                        message_history=_messages,
                    )
                    log.reflection_done(feedback, round_n=_round + 1)
                    article, _messages = await run_writer_agent(
                        brief,
                        topic=topic,
                        domain=domain,
                        config=settings.writer,
                        reflection_feedback=feedback,
                        additional_instructions=additional_instructions,
                    )
                    log.writer_done(article, round_n=_round + 2)
            except Exception as e:
                _errors.append({"stage": "reflection", "error": str(e)})
                log.error("reflection", e)
                record_error("reflection")
    _timing["writer"] = (time.perf_counter() - _stage_t0) * 1000
    record_stage("writer", _timing["writer"], domain.name)

    # Stage 5: Follow-up
    _stage_t0 = time.perf_counter()
    with logfire.span("pipeline.stage.followup", domain=domain.name):
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
                    log.usage_tracking_done(used_facts, used_quotes)
                except Exception as e:
                    _errors.append({"stage": "usage_tracking", "error": str(e)})
                    log.error("usage_tracking", e)
                    record_error("usage_tracking")
                    used_facts, used_quotes = [], []
                log.followup_done(result.alternative_titles, result.followup_topics)
                _timing["followup"] = (time.perf_counter() - _stage_t0) * 1000
                record_stage("followup", _timing["followup"], domain.name)
                _total_ms = (time.perf_counter() - _pipeline_t0) * 1000
                record_pipeline_run(domain.name, "ok", _total_ms)
                log.done(len(result.sources or scraped_urls), len(_errors))
                return _replace(
                    result,
                    used_facts=used_facts,
                    used_quotes=used_quotes,
                    sources=result.sources or scraped_urls,
                    scraped_urls=scraped_urls,
                    errors=_errors,
                    filter_reasons=_filter_reasons,
                    embed_candidates=embed_candidates,
                    timing=_timing,
                    token_usage=[
                        {"agent": r.agent, "model": r.model,
                         "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
                         "duration_ms": round(r.duration_ms, 1)}
                        for r in _token_records
                    ],
                )
            except Exception as e:
                _errors.append({"stage": "followup", "error": str(e)})
                log.error("followup", e)
                record_error("followup")
    _timing["followup"] = (time.perf_counter() - _stage_t0) * 1000
    record_stage("followup", _timing["followup"], domain.name)

    sources = list(
        {f.source_url for f in extraction.facts if f.source_url}
        | {q.source_url for q in extraction.quotes if q.source_url}
    ) or scraped_urls
    _total_ms = (time.perf_counter() - _pipeline_t0) * 1000
    _status = "error" if _errors else "ok"
    record_pipeline_run(domain.name, _status, _total_ms)
    log.done(len(sources), len(_errors))
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
        embed_candidates=embed_candidates,
        timing=_timing,
        token_usage=[
            {"agent": r.agent, "model": r.model,
             "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
             "duration_ms": round(r.duration_ms, 1)}
            for r in _token_records
        ],
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
