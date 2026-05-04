# agents/pipeline/runner.py
from __future__ import annotations

import re
import time
from typing import Literal
from uuid import UUID

import logfire

from agents._base.resilient import InsufficientSourcesError
from agents._base.run_context import get_fallback_events, init_collector
from agents._base.types import ArticleOutput, EmbedCandidate, ParsedArticle
from agents.adaptive_search.agent import run_adaptive_search_agent
from agents.extraction.agent import ExtractionResult, run_extraction_agent
from agents.followup.agent import run_followup_agent
from agents.instructions.agent import WritingBrief, run_instructions_agent
from agents.media_search.agent import run_media_search
from agents.parsing.agent import run_parsing_agent
from agents.reflection.agent import run_reflection_agent
from agents.scraping.agent import run_scraping_agent
from agents.search.agent import run_search_agent
from agents.writer.agent import ArticleHtml, run_writer_agent
from backend.config import AppSettings
from backend.domain import DomainConfig
from backend.services.metrics import record_error, record_pipeline_run, record_stage
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
    org_code: str = "__local_dev__",
    author_user_id: str = "local-dev",
    _article_id: UUID | None = None,
) -> ArticleOutput:
    """Pipeline entry. `org_code` + `author_user_id` are persistence context;
    they identify which Kinde org owns the article and which user authored it.
    Defaults match the run.py local-dev path so existing callers keep working;
    backend/api/v2.py overrides them from the JWT + X-Org-Code header."""
    with logfire.span(
        "pipeline.run",
        topic=topic,
        domain=domain.name,
        org_code=org_code,
        urls_count=len(urls) if urls else 0,
        has_additional_instructions=bool(additional_instructions),
    ):
        return await _run_pipeline_inner(
            topic=topic,
            settings=settings,
            domain=domain,
            serper_api_key=serper_api_key,
            jina_api_key=jina_api_key,
            urls=urls,
            additional_instructions=additional_instructions,
            debug=debug,
            org_code=org_code,
            author_user_id=author_user_id,
            article_id=_article_id,
        )


async def _run_pipeline_inner(
    *,
    topic: str,
    settings: AppSettings,
    domain: DomainConfig,
    serper_api_key: str,
    jina_api_key: str | None,
    urls: list[str] | None,
    additional_instructions: str | None,
    debug: bool,
    org_code: str,
    author_user_id: str,
    article_id: UUID | None = None,
) -> ArticleOutput:
    from dataclasses import replace as dc_replace

    from agents._base.config import SearchAgentConfig
    from agents._base.debug_log import PipelineLogger
    from backend.repositories import get_article_repo

    log = PipelineLogger(enabled=debug)

    _errors: list[dict[str, str]] = []
    _filter_reasons: dict[str, str] = {}
    _timing: dict[str, float] = {}
    _token_records = init_collector()
    _pipeline_t0 = time.perf_counter()

    # Persist a 'running' Article row up-front so failures still produce a record.
    # Repo is Null when DB_BACKEND=null (run.py default), Postgres when configured.
    # When called from the API endpoint, article_id is pre-created there (non-blocking flow).
    _article_repo = get_article_repo()
    if article_id is not None:
        _article_id = article_id
    else:
        _article_id = await _article_repo.create_running(
            org_code=org_code,
            author_user_id=author_user_id,
            domain_name=domain.name,
            topic=topic,
        )

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

    # Apply domain search volume defaults when caller hasn't overridden them
    if (
        settings.search.num_queries == SearchAgentConfig().num_queries
        and domain.default_num_queries != SearchAgentConfig().num_queries
    ):
        settings = dc_replace(
            settings,
            search=dc_replace(settings.search, num_queries=domain.default_num_queries),
        )
    if (
        settings.search.max_results == SearchAgentConfig().max_results
        and domain.default_max_results != SearchAgentConfig().max_results
    ):
        settings = dc_replace(
            settings,
            search=dc_replace(settings.search, max_results=domain.default_max_results),
        )

    # Apply domain default for reviewer's competitor-coverage slice when caller hasn't overridden it
    from agents._base.config import ReflectionAgentConfig

    if (
        settings.reflection.context_articles_count == ReflectionAgentConfig().context_articles_count
        and domain.default_reflection_context_articles
        != ReflectionAgentConfig().context_articles_count
    ):
        settings = dc_replace(
            settings,
            reflection=dc_replace(
                settings.reflection,
                context_articles_count=domain.default_reflection_context_articles,
            ),
        )

    # Apply domain default for min_source_signals (gate floor + adaptive_search target).
    # Per-domain because different editorial brands need different evidentiary depth.
    from backend.config import PipelineFlags

    if (
        settings.pipeline.min_source_signals == PipelineFlags().min_source_signals
        and domain.default_min_source_signals != PipelineFlags().min_source_signals
    ):
        settings = dc_replace(
            settings,
            pipeline=dc_replace(
                settings.pipeline,
                min_source_signals=domain.default_min_source_signals,
            ),
        )

    # Stage 1: Research
    await _article_repo.set_pipeline_stage(_article_id, "search")
    log.search_start(
        topic,
        settings.search.num_queries,
        settings.search.max_results,
        settings.search.search_freshness,
        news_search=settings.search.news_search,
    )
    _stage_t0 = time.perf_counter()
    with logfire.span("pipeline.stage.research", topic=topic, domain=domain.name):
        try:
            search_results = await run_search_agent(
                topic,
                config=settings.search,
                domain_language=domain.language,
                serper_api_key=serper_api_key,
            )
            log.search_done(search_results)
        except Exception as e:
            _errors.append({"stage": "search", "error": str(e)})
            log.error("search", e)
            record_error("search")
            search_results = []
    _timing["research"] = (time.perf_counter() - _stage_t0) * 1000
    record_stage("research", _timing["research"], domain.name)

    # Promote social media URLs discovered via organic search to embed_candidates
    # and remove them from the scraping list (they don't scrape usefully).
    # NB: media_search now runs LATER (post-rerank) so it can see actual article context.
    search_results, _search_embeds = _extract_social_from_search(search_results)

    await _article_repo.set_pipeline_stage(_article_id, "scraping")
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
    _content_embeds = _extract_social_from_content(scraped)

    await _article_repo.set_pipeline_stage(_article_id, "parsing")
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

    await _article_repo.set_pipeline_stage(_article_id, "extraction")
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
        await _article_repo.set_pipeline_stage(_article_id, "adaptive_search")
        _stage_t0 = time.perf_counter()
        _target = settings.pipeline.min_source_signals
        with logfire.span(
            "pipeline.stage.adaptive_search",
            domain=domain.name,
            target_signals=_target,
            initial_signals=len(extraction.facts) + len(extraction.quotes),
            max_rounds_budget=settings.adaptive_search_agent.max_additional_rounds,
        ):
            try:
                seen_urls: set[str] = {r.url for r in search_results}
                for _round in range(settings.adaptive_search_agent.max_additional_rounds):
                    current = len(extraction.facts) + len(extraction.quotes)
                    decision = await run_adaptive_search_agent(
                        extraction,
                        topic=topic,
                        config=settings.adaptive_search_agent,
                        target_signals=_target,
                    )
                    log.adaptive_search_done(decision, _round + 1)
                    # Stop if agent is satisfied AND we've met the floor.
                    if (
                        not decision.needs_more_research or not decision.additional_queries
                    ) and current >= _target:
                        break
                    if not decision.additional_queries:
                        break  # nothing to query, agent gave up
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
                    articles = (
                        articles + extra_articles
                    )  # extend pool for downstream rerank/context
                    extra_extraction = await run_extraction_agent(
                        extra_articles,
                        topic=topic,
                        language=domain.language,
                        config=settings.extraction,
                    )
                    extraction = _merge_extraction(extraction, extra_extraction)
                    log.extraction_done(extraction)
                    # Early exit if we hit the floor — don't waste a budget on another LLM call.
                    if len(extraction.facts) + len(extraction.quotes) >= _target:
                        break
            except Exception as e:
                _errors.append({"stage": "adaptive_search", "error": str(e)})
                log.error("adaptive_search", e)
                record_error("adaptive_search")
        _timing["adaptive_search"] = (time.perf_counter() - _stage_t0) * 1000
        record_stage("adaptive_search", _timing["adaptive_search"], domain.name)

    # Rerank parsed articles by their contribution to extraction; reused below for both
    # media_search context AND reviewer's competitor-coverage block.
    ranked_articles = _rank_articles_by_extraction(articles, extraction)

    # Stage 2.5: Media search — runs AFTER rerank so the query formulator sees the
    # actual top sources (not just the topic line) and can produce concrete event-specific
    # queries. This used to run in parallel with web search, but a thin topic line caused
    # the LLM to fall back to generic queries that pulled in unrelated social content.
    await _article_repo.set_pipeline_stage(_article_id, "media_search")
    embed_candidates: list[EmbedCandidate] = []
    media_errors: dict[str, str] = {}
    _stage_t0 = time.perf_counter()
    with logfire.span("pipeline.stage.media_search", domain=domain.name):
        try:
            embed_candidates, media_errors = await run_media_search(
                topic,
                domain=domain,
                serper_api_key=serper_api_key,
                freshness=settings.search.search_freshness,
                context_articles=ranked_articles[:2],
                log=log,
            )
            log.media_search_done(embed_candidates, media_errors)
        except Exception as e:
            _errors.append({"stage": "media_search", "error": str(e)})
            log.error("media_search", e)
            record_error("media_search")
    _timing["media_search"] = (time.perf_counter() - _stage_t0) * 1000
    record_stage("media_search", _timing["media_search"], domain.name)

    # Combine all embed sources: media_search + organic search + competitor content scraping.
    # Dedup by URL; media_search results take priority (they have richer metadata).
    _all_embeds = embed_candidates + _search_embeds + _content_embeds
    seen: set[str] = set()
    embed_candidates = [e for e in _all_embeds if not (e.url in seen or seen.add(e.url))]

    # Gate: refuse to run writer if extraction is empty.
    # All upstream failures (Serper auth/credits, Jina credits/timeouts, parser yielding 0
    # articles, extraction LLM error) collapse here. Writer must NOT run on no source material.
    _signal_count = len(extraction.facts) + len(extraction.quotes)
    if _signal_count < settings.pipeline.min_source_signals:
        with logfire.span(
            "pipeline.guardrail.insufficient_sources",
            facts=len(extraction.facts),
            quotes=len(extraction.quotes),
            min_required=settings.pipeline.min_source_signals,
        ):
            log.error("guardrail", RuntimeError("insufficient_sources"))
            await _article_repo.mark_failed(
                _article_id,
                error_status="insufficient_sources",
                errors=_errors,
                insufficient_sources_detail={
                    "facts_count": len(extraction.facts),
                    "quotes_count": len(extraction.quotes),
                    "min_required": settings.pipeline.min_source_signals,
                    "upstream_errors": list(_errors),
                },
            )
            raise InsufficientSourcesError(
                facts_count=len(extraction.facts),
                quotes_count=len(extraction.quotes),
                min_required=settings.pipeline.min_source_signals,
                upstream_errors=list(_errors),
            )

    # Stage 3: Writing
    await _article_repo.set_pipeline_stage(_article_id, "instructions")
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

    await _article_repo.set_pipeline_stage(_article_id, "writer")
    _stage_t0 = time.perf_counter()
    _writer_messages: list = []  # accumulates across all writer turns for revision rounds
    with logfire.span("pipeline.stage.writer", domain=domain.name, round=1):
        try:
            article, _writer_messages = await run_writer_agent(
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
    _timing["writer"] = (time.perf_counter() - _stage_t0) * 1000
    record_stage("writer", _timing["writer"], domain.name)

    # Stage 4: Reflection — own top-level stage with per-round sub-spans.
    # Each writer.revise turn receives the FULL accumulated writer history so it
    # can consciously revise its prior draft instead of regenerating from scratch.
    if settings.pipeline.reflection:
        await _article_repo.set_pipeline_stage(_article_id, "reflection")
        _stage_t0 = time.perf_counter()
        with logfire.span(
            "pipeline.stage.reflection",
            domain=domain.name,
            max_rounds=settings.reflection.max_rounds,
        ):
            try:
                for _round in range(settings.reflection.max_rounds):
                    round_n = _round + 1
                    with logfire.span("reflection.review", round=round_n):
                        feedback = await run_reflection_agent(
                            article,
                            topic=topic,
                            domain=domain,
                            config=settings.reflection,
                            extraction=extraction,
                            context_articles=ranked_articles[
                                : settings.reflection.context_articles_count
                            ],
                        )
                        log.reflection_done(feedback, round_n=round_n)
                    with logfire.span("writer.revise", round=round_n):
                        article, _writer_messages = await run_writer_agent(
                            brief,
                            topic=topic,
                            domain=domain,
                            config=settings.writer,
                            reflection_feedback=feedback,
                            additional_instructions=additional_instructions,
                            message_history=_writer_messages,
                        )
                        log.writer_done(article, round_n=round_n + 1)
            except Exception as e:
                _errors.append({"stage": "reflection", "error": str(e)})
                log.error("reflection", e)
                record_error("reflection")
        _timing["reflection"] = (time.perf_counter() - _stage_t0) * 1000
        record_stage("reflection", _timing["reflection"], domain.name)

    # Stage 5: Follow-up
    await _article_repo.set_pipeline_stage(_article_id, "followup")
    _stage_t0 = time.perf_counter()
    with logfire.span("pipeline.stage.followup", domain=domain.name):
        if settings.pipeline.followup:
            try:
                result = await run_followup_agent(
                    article,
                    topic=topic,
                    extraction_result=extraction,
                    config=settings.followup,
                    domain=domain,
                )
                used_facts = list(result.used_facts)
                used_quotes = list(result.used_quotes)
                log.usage_tracking_done(used_facts, used_quotes)
                log.followup_done(result.alternative_titles, result.followup_topics)
                _timing["followup"] = (time.perf_counter() - _stage_t0) * 1000
                record_stage("followup", _timing["followup"], domain.name)
                _total_ms = (time.perf_counter() - _pipeline_t0) * 1000
                record_pipeline_run(domain.name, "error" if _errors else "ok", _total_ms)
                log.done(len(result.sources or scraped_urls), len(_errors))
                await _persist_article_done(
                    repo=_article_repo,
                    article_id=_article_id,
                    article_html=article.html,
                    alternative_titles=list(result.alternative_titles),
                    followup_topics=list(result.followup_topics),
                    used_facts_texts=list(used_facts),
                    used_quotes_texts=list(used_quotes),
                    extraction=extraction,
                    embed_candidates=embed_candidates,
                    sources=list(result.sources or scraped_urls),
                    pipeline_timing=_timing,
                    errors=_errors,
                    total_duration_ms=_total_ms,
                    token_records=_token_records,
                    fallback_events=get_fallback_events(),
                    status="failed" if _errors else "done",
                )
                return dc_replace(
                    result,
                    article_id=str(_article_id),
                    used_facts=used_facts,
                    used_quotes=used_quotes,
                    sources=result.sources or scraped_urls,
                    scraped_urls=scraped_urls,
                    errors=_errors,
                    filter_reasons=_filter_reasons,
                    embed_candidates=embed_candidates,
                    timing=_timing,
                    token_usage=[
                        {
                            "agent": r.agent,
                            "model": r.model,
                            "input_tokens": r.input_tokens,
                            "output_tokens": r.output_tokens,
                            "duration_ms": round(r.duration_ms, 1),
                        }
                        for r in _token_records
                    ],
                    fallback_events=[
                        {
                            "agent": e.agent,
                            "failed_model": e.failed_model,
                            "error_type": e.error_type,
                            "error_message": e.error_message,
                        }
                        for e in get_fallback_events()
                    ],
                )
            except Exception as e:
                _errors.append({"stage": "followup", "error": str(e)})
                log.error("followup", e)
                record_error("followup")
    if settings.pipeline.followup:
        _timing["followup"] = (time.perf_counter() - _stage_t0) * 1000
        record_stage("followup", _timing["followup"], domain.name)

    sources = (
        list(
            {f.source_url for f in extraction.facts if f.source_url}
            | {q.source_url for q in extraction.quotes if q.source_url}
        )
        or scraped_urls
    )
    _total_ms = (time.perf_counter() - _pipeline_t0) * 1000
    _status = "error" if _errors else "ok"
    record_pipeline_run(domain.name, _status, _total_ms)
    log.done(len(sources), len(_errors))
    await _persist_article_done(
        repo=_article_repo,
        article_id=_article_id,
        article_html=article.html,
        alternative_titles=[],
        followup_topics=[],
        used_facts_texts=[],
        used_quotes_texts=[],
        extraction=extraction,
        embed_candidates=embed_candidates,
        sources=sources,
        pipeline_timing=_timing,
        errors=_errors,
        total_duration_ms=_total_ms,
        token_records=_token_records,
        fallback_events=get_fallback_events(),
        status="failed" if _errors else "done",
    )
    return ArticleOutput(
        html=article.html,
        article_id=str(_article_id),
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
            {
                "agent": r.agent,
                "model": r.model,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "duration_ms": round(r.duration_ms, 1),
            }
            for r in _token_records
        ],
        fallback_events=[
            {
                "agent": e.agent,
                "failed_model": e.failed_model,
                "error_type": e.error_type,
                "error_message": e.error_message,
            }
            for e in get_fallback_events()
        ],
    )


async def _persist_article_done(
    *,
    repo,
    article_id,
    article_html: str,
    alternative_titles: list[str],
    followup_topics: list[str],
    used_facts_texts: list[str],
    used_quotes_texts: list[str],
    extraction: ExtractionResult,
    embed_candidates: list[EmbedCandidate],
    sources: list[str],
    pipeline_timing: dict[str, float],
    errors: list[dict[str, str]],
    total_duration_ms: float,
    token_records,
    fallback_events,
    status: str = "done",
) -> None:
    """Translate agent-level types to DB rows and persist the completed Article.

    Lives at module level so both success-return paths (followup-OK and followup-skipped)
    use the same translation + write call.
    """
    from backend.db.models import (
        EmbedCandidate as DBEmbed,
    )
    from backend.db.models import (
        Fact as DBFact,
    )
    from backend.db.models import (
        FallbackEvent as DBFallbackEvent,
    )
    from backend.db.models import (
        Quote as DBQuote,
    )
    from backend.db.models import (
        UsageEvent as DBUsageEvent,
    )

    used_facts_set = set(used_facts_texts)
    used_quotes_set = set(used_quotes_texts)
    # article_id is set on each child explicitly so Pydantic-level validation passes;
    # the repo will overwrite it (no-op since it's the same value).
    db_facts = [
        DBFact(
            article_id=article_id,
            text=f.text,
            context=f.context,
            source_url=f.source_url,
            source_title=f.source_title,
            was_used=f.text in used_facts_set,
        )
        for f in extraction.facts
    ]
    db_quotes = [
        DBQuote(
            article_id=article_id,
            text=q.text,
            speaker=q.speaker,
            context=q.context,
            source_url=q.source_url,
            was_used=q.text in used_quotes_set,
        )
        for q in extraction.quotes
    ]
    db_embeds = [
        DBEmbed(
            article_id=article_id,
            url=e.url,
            title=e.title,
            source=e.source,
            thumbnail_url=e.thumbnail_url,
            description=e.description,
            channel=e.channel,
            competitor_source_url=e.competitor_source_url,
        )
        for e in embed_candidates
    ]
    db_usage = [
        DBUsageEvent(
            article_id=article_id,
            agent_name=r.agent,
            model=r.model,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            duration_ms=r.duration_ms,
        )
        for r in token_records
    ]
    db_fallbacks = [
        DBFallbackEvent(
            article_id=article_id,
            agent_name=e.agent,
            failed_model=e.failed_model,
            error_type=e.error_type,
            error_message=e.error_message,
        )
        for e in fallback_events
    ]
    await repo.complete(
        article_id,
        status=status,
        html=article_html or "",
        alternative_titles=alternative_titles,
        followup_topics=followup_topics,
        sources=sources,
        facts=db_facts,
        quotes=db_quotes,
        embed_candidates=db_embeds,
        usage_events=db_usage,
        fallback_events=db_fallbacks,
        pipeline_timing=pipeline_timing,
        errors=errors,
        total_duration_ms=total_duration_ms,
    )


def _filter_by_date(
    articles: list[ParsedArticle],
    cutoff_days: int,
    manual_urls: set[str],
) -> tuple[list[ParsedArticle], dict[str, str]]:
    from datetime import UTC, datetime, timedelta

    cutoff = datetime.now(UTC).date() - timedelta(days=cutoff_days)
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


_SocialSource = Literal["youtube", "twitter", "tiktok", "instagram", "facebook", "reddit"]

_SOCIAL_DOMAINS: dict[str, _SocialSource] = {
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "tiktok.com": "tiktok",
    "instagram.com": "instagram",
    "facebook.com": "facebook",
    "reddit.com": "reddit",
}


def _extract_social_from_search(
    results: list,
) -> tuple[list, list[EmbedCandidate]]:
    """Split search results into (scrapable, social_embed_candidates).

    Social media URLs are useless to scrape but valuable as embeds.
    """
    from urllib.parse import urlparse

    scrapable: list = []
    embeds: list[EmbedCandidate] = []
    for r in results:
        host = urlparse(r.url).netloc.removeprefix("www.")
        source: _SocialSource | None = None
        for domain, src in _SOCIAL_DOMAINS.items():
            if host == domain or host.endswith("." + domain):
                source = src
                break
        if source:
            embeds.append(
                EmbedCandidate(
                    url=r.url,
                    title=r.title,
                    source=source,
                    description=r.snippet or None,
                )
            )
        else:
            scrapable.append(r)
    return scrapable, embeds


_SOCIAL_URL_RE = re.compile(
    r"https?://(?:www\.)?"
    r"(?:youtube\.com/(?:watch|shorts|embed)[^\s\)\]\"'<>]*"
    r"|youtu\.be/[^\s\)\]\"'<>]+"
    r"|twitter\.com/\w+/status/[^\s\)\]\"'<>]+"
    r"|x\.com/\w+/status/[^\s\)\]\"'<>]+"
    r"|tiktok\.com/@[^\s\)\]\"'<>/]+/video/[^\s\)\]\"'<>]+"
    r"|instagram\.com/(?:p|reel|tv)/[^\s\)\]\"'<>/]+"
    r"|facebook\.com/(?:[^/]+/(?:posts|videos|reels)/|watch/\?v=)[^\s\)\]\"'<>]+"
    r"|reddit\.com/r/[^\s\)\]\"'<>]+)",
    re.IGNORECASE,
)


def _extract_social_from_content(
    pages: list,
) -> list[EmbedCandidate]:
    """Extract social media URLs embedded in scraped competitor article content.

    Regex-only, zero LLM cost. Complements _extract_social_from_search (which
    catches top-level social URLs) by surfacing embeds mentioned within articles.
    """
    from urllib.parse import urlparse

    seen: set[str] = set()
    candidates: list[EmbedCandidate] = []
    for page in pages:
        for match in _SOCIAL_URL_RE.finditer(page.content):
            url = match.group(0).rstrip(".,;)")
            if url in seen:
                continue
            seen.add(url)
            host = urlparse(url).netloc.removeprefix("www.")
            source: _SocialSource | None = None
            for domain, src in _SOCIAL_DOMAINS.items():
                if host == domain or host.endswith("." + domain):
                    source = src
                    break
            if source:
                candidates.append(
                    EmbedCandidate(
                        url=url, title=url, source=source, competitor_source_url=page.url
                    )
                )
    return candidates


def _rank_articles_by_extraction(
    articles: list[ParsedArticle], extraction: ExtractionResult
) -> list[ParsedArticle]:
    """Sort parsed articles by how much they contributed to the extraction.

    A fact counts twice as much as a quote (facts are more directly load-bearing for
    fact-checking; quotes are also ranked but less aggressively). Articles that didn't
    contribute anything fall to the end in their original order. Reviewer's competitor
    coverage is taken from the top of this list.
    """
    from collections import Counter

    score: Counter[str] = Counter()
    for f in extraction.facts:
        score[f.source_url] += 2
    for q in extraction.quotes:
        score[q.source_url] += 1
    return sorted(articles, key=lambda a: score[a.url], reverse=True)


def _merge_extraction(base: ExtractionResult, extra: ExtractionResult) -> ExtractionResult:
    seen_facts = {f.text for f in base.facts}
    seen_quotes = {q.text for q in base.quotes}
    merged_facts = base.facts + [f for f in extra.facts if f.text not in seen_facts]
    merged_quotes = base.quotes + [q for q in extra.quotes if q.text not in seen_quotes]
    merged_keywords = list(dict.fromkeys(base.keywords + extra.keywords))
    return ExtractionResult(facts=merged_facts, quotes=merged_quotes, keywords=merged_keywords)
