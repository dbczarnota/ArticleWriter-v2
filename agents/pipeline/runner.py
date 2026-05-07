# agents/pipeline/runner.py
from __future__ import annotations

import asyncio
import time
from uuid import UUID

import logfire

from agents._base.resilient import InsufficientSourcesError
from agents._base.run_context import get_fallback_events, init_collector
from agents._base.types import ArticleOutput, EmbedCandidate
from agents.extraction.agent import ExtractionResult, run_extraction_agent
from agents.followup.agent import run_followup_agent
from agents.instructions.agent import WritingBrief, run_instructions_agent
from agents.media_search.agent import run_media_search
from agents.parsing.agent import run_parsing_agent
from agents.pipeline._adaptive_search import adaptive_search_loop
from agents.pipeline._helpers import (
    extract_social_from_content,
    extract_social_from_search,
    filter_by_date,
    rank_articles_by_extraction,
)
from agents.pipeline._persistence import persist_article_done
from agents.reflection.agent import run_reflection_agent
from agents.scraping.agent import run_scraping_agent
from agents.search.agent import run_search_agent
from agents.writer.agent import ArticleHtml, run_writer_agent
from backend.config import AppSettings
from backend.domain import DomainConfig
from backend.services.metrics import record_error, record_pipeline_run, record_stage


def _ensure_user_urls(sources: list[str], user_urls: list[str] | None) -> list[str]:
    """User-supplied seed URLs are non-negotiable inputs and must always
    appear in the article's sources, even when the extraction LLM yielded
    no facts/quotes from them. Editors enter URLs because they expect
    those pages to be in the writer's context — silently dropping them
    when extraction comes back empty broke that contract."""
    if not user_urls:
        return sources
    seen = set(sources)
    return sources + [u for u in user_urls if u not in seen]


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
    with logfire.set_baggage(
        article_id=str(article_id) if article_id else "no-article-id",
        org_code=org_code,
        user_id=author_user_id,
    ):
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
                additional_instructions=additional_instructions,
                input_urls=list(urls or []),
            )

        # Apply domain freshness default when the caller hasn't explicitly overridden it
        if settings.search.search_freshness == SearchAgentConfig().search_freshness:
            settings = dc_replace(
                settings,
                search=dc_replace(
                    settings.search, search_freshness=domain.default_search_freshness
                ),
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
            settings.reflection.context_articles_count
            == ReflectionAgentConfig().context_articles_count
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

        # Snapshot the *effective* inputs once all domain/per-request overrides have
        # been applied. Any future "why did the writer behave that way?" investigation
        # can answer it from this single event. No secrets here — Settings dataclasses
        # don't carry api_keys, those are passed positionally.
        from dataclasses import asdict as _asdict

        try:
            _domain_dict = _asdict(domain)
        except TypeError:
            _domain_dict = dict(getattr(domain, "__dict__", {}))
        _settings_dict = _asdict(settings)
        logfire.info(
            "pipeline.run.inputs",
            topic=topic,
            urls=list(urls or []),
            additional_instructions=additional_instructions or "",
            domain=_domain_dict,
            settings=_settings_dict,
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

        # Audit point: every URL Serper handed us, before the scraping LLM filter sees it.
        # Lets a post-mortem distinguish "Serper returned nothing" from "filter rejected
        # everything" from "scraping itself failed" — three very different failure modes
        # that all surface as 0 articles downstream.
        logfire.info(
            "pipeline.research.completed",
            urls_returned=len(search_results),
            urls=[
                {"url": r.url, "title": (r.title or "")[:200], "snippet": (r.snippet or "")[:200]}
                for r in search_results[:30]
            ],
        )

        # Promote social media URLs discovered via organic search to embed_candidates
        # and remove them from the scraping list (they don't scrape usefully).
        # NB: media_search now runs LATER (post-rerank) so it can see actual article context.
        search_results, _search_embeds = extract_social_from_search(search_results)

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
        _content_embeds = extract_social_from_content(scraped)

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

        # Audit point: how many scraped pages survived parsing (raw HTML →
        # structured ParsedArticle). A drop from N pages to 0 articles means
        # the parser LLM rejected everything (paywall, error pages, off-topic).
        logfire.info(
            "pipeline.parsing.completed",
            pages_in=len(scraped),
            articles_out=len(articles),
            articles=[{"url": a.url, "title": (a.title or "")[:200]} for a in articles[:30]],
        )

        if settings.pipeline.cutoff_days > 0:
            articles, _date_reasons = filter_by_date(
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

        # Audit point: did extraction actually produce signals to write from?
        # 0 facts and 0 quotes here is the canary for `insufficient_sources`
        # downstream. Adaptive search may save us, but seeing the gap explicitly
        # makes the failure mode obvious.
        logfire.info(
            "pipeline.extraction.completed",
            articles_in=len(articles),
            facts_count=len(extraction.facts),
            quotes_count=len(extraction.quotes),
            keywords_count=len(extraction.keywords),
        )

        # Stage 2: Adaptive search loop
        # Skip adaptive search entirely when initial extraction already
        # meets the signal target — the decide-agent call costs an LLM
        # round-trip per pipeline run that has nothing to add.
        _initial_signals = len(extraction.facts) + len(extraction.quotes)
        _target = settings.pipeline.min_source_signals
        if settings.pipeline.adaptive_search and _initial_signals >= _target:
            logfire.info(
                "pipeline.adaptive_search.skipped",
                reason="signals_already_sufficient",
                signal_count=_initial_signals,
                target=_target,
            )
        if settings.pipeline.adaptive_search and _initial_signals < _target:
            _stage_t0 = time.perf_counter()
            await _article_repo.set_pipeline_stage(_article_id, "adaptive_search")
            with logfire.span(
                "pipeline.stage.adaptive_search",
                domain=domain.name,
                target_signals=_target,
                initial_signals=len(extraction.facts) + len(extraction.quotes),
                max_rounds_budget=settings.adaptive_search_agent.max_additional_rounds,
                total_timeout_s=settings.adaptive_search_agent.total_timeout_s,
            ):
                try:
                    articles, extraction = await asyncio.wait_for(
                        adaptive_search_loop(
                            article_repo=_article_repo,
                            article_id=_article_id,
                            topic=topic,
                            domain=domain,
                            settings=settings,
                            articles=articles,
                            extraction=extraction,
                            search_results=search_results,
                            target_signals=_target,
                            serper_api_key=serper_api_key,
                            jina_api_key=jina_api_key,
                            log=log,
                        ),
                        timeout=settings.adaptive_search_agent.total_timeout_s,
                    )
                except TimeoutError as e:
                    # Hard cap hit — keep whatever was collected, soft-fail downstream.
                    _errors.append(
                        {
                            "stage": "adaptive_search",
                            "error": (
                                f"total stage timeout after "
                                f"{settings.adaptive_search_agent.total_timeout_s:.0f}s"
                            ),
                        }
                    )
                    log.error("adaptive_search", e)
                    record_error("adaptive_search")
                    logfire.warn(
                        "pipeline.adaptive_search.budget_exhausted",
                        timeout_s=settings.adaptive_search_agent.total_timeout_s,
                        signals_collected=len(extraction.facts) + len(extraction.quotes),
                        target=_target,
                    )
                except Exception as e:
                    _errors.append({"stage": "adaptive_search", "error": str(e)})
                    log.error("adaptive_search", e)
                    record_error("adaptive_search")
            _timing["adaptive_search"] = (time.perf_counter() - _stage_t0) * 1000
            record_stage("adaptive_search", _timing["adaptive_search"], domain.name)

        # Rerank parsed articles by their contribution to extraction; reused below for both
        # media_search context AND reviewer's competitor-coverage block.
        ranked_articles = rank_articles_by_extraction(articles, extraction)

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

        # Audit point: which social/video sources actually returned candidates,
        # and any per-source errors that didn't kill the stage but produced no
        # results (e.g. Reddit rate-limit, Serper quota for /images).
        _by_source: dict[str, int] = {}
        for _e in embed_candidates:
            _by_source[_e.source] = _by_source.get(_e.source, 0) + 1
        logfire.info(
            "pipeline.media_search.completed",
            embeds_total=len(embed_candidates),
            by_source=_by_source,
            errors=media_errors,
        )

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
                logfire.warn(
                    "pipeline.guardrail.insufficient_sources",
                    facts=len(extraction.facts),
                    quotes=len(extraction.quotes),
                    min_required=settings.pipeline.min_source_signals,
                    upstream_errors_count=len(_errors),
                )
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
                    _final_sources = _ensure_user_urls(list(result.sources or scraped_urls), urls)
                    log.done(len(_final_sources), len(_errors))
                    await persist_article_done(
                        repo=_article_repo,
                        article_id=_article_id,
                        article_html=article.html,
                        alternative_titles=list(result.alternative_titles),
                        followup_topics=list(result.followup_topics),
                        used_facts_texts=list(used_facts),
                        used_quotes_texts=list(used_quotes),
                        extraction=extraction,
                        embed_candidates=embed_candidates,
                        sources=_final_sources,
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
                        sources=_final_sources,
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

        sources = _ensure_user_urls(
            list(
                {url for f in extraction.facts for url in f.source_urls if url}
                | {url for q in extraction.quotes for url in q.source_urls if url}
            )
            or scraped_urls,
            urls,
        )
        _total_ms = (time.perf_counter() - _pipeline_t0) * 1000
        _status = "error" if _errors else "ok"
        record_pipeline_run(domain.name, _status, _total_ms)
        log.done(len(sources), len(_errors))
        await persist_article_done(
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
