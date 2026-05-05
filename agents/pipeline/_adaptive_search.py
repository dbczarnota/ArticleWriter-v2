# agents/pipeline/_adaptive_search.py
"""Adaptive-search loop body — pulled out of runner.py.

Each iteration creates one Logfire span `pipeline.stage.adaptive_search.round`
plus one sub-span per substage (decide / serper / scraping / parsing /
extraction). The DB pipeline_stage column is set to a fine-grained label like
'adaptive_search.r2.scraping' so the UI spinner can show what we're actually
waiting on.

The outer caller wraps this in asyncio.wait_for with a single budget cap
(AdaptiveSearchAgentConfig.total_timeout_s).
"""

from __future__ import annotations

from uuid import UUID

import logfire

from agents._base.types import ParsedArticle
from agents.adaptive_search.agent import run_adaptive_search_agent
from agents.extraction.agent import ExtractionResult, run_extraction_agent
from agents.parsing.agent import run_parsing_agent
from agents.pipeline._helpers import merge_extraction
from agents.scraping.agent import run_scraping_agent
from backend.config import AppSettings
from backend.domain import DomainConfig
from toolsets.scraping.serper import search as serper_search


async def adaptive_search_loop(
    *,
    article_repo,
    article_id: UUID | None,
    topic: str,
    domain: DomainConfig,
    settings: AppSettings,
    articles: list[ParsedArticle],
    extraction: ExtractionResult,
    search_results,
    target_signals: int,
    serper_api_key: str,
    jina_api_key: str | None,
    log,
) -> tuple[list[ParsedArticle], ExtractionResult]:
    def _emit_round_completed(
        *,
        round_idx: int,
        exit_reason: str,
        signals_before: int,
        signals_after: int,
        decision_needs_more: bool | None,
        queries: list[str],
        new_urls: int,
        articles_extracted: int,
        facts_added: int,
        quotes_added: int,
    ) -> None:
        logfire.info(
            "pipeline.adaptive_search.round.completed",
            round=round_idx,
            exit_reason=exit_reason,
            signals_before=signals_before,
            signals_after=signals_after,
            target=target_signals,
            decision_needs_more=decision_needs_more,
            queries=queries[:10],
            queries_count=len(queries),
            new_urls=new_urls,
            articles_extracted=articles_extracted,
            facts_added=facts_added,
            quotes_added=quotes_added,
        )

    seen_urls: set[str] = {r.url for r in search_results}
    for _round in range(settings.adaptive_search_agent.max_additional_rounds):
        round_idx = _round + 1
        signals_before = len(extraction.facts) + len(extraction.quotes)
        with logfire.span(
            "pipeline.stage.adaptive_search.round",
            round=round_idx,
            signals_before=signals_before,
            target=target_signals,
        ) as round_span:
            # Decide
            await article_repo.set_pipeline_stage(
                article_id, f"adaptive_search.r{round_idx}.decide"
            )
            with logfire.span("pipeline.stage.adaptive_search.decide", round=round_idx):
                decision = await run_adaptive_search_agent(
                    extraction,
                    topic=topic,
                    config=settings.adaptive_search_agent,
                    target_signals=target_signals,
                )
                log.adaptive_search_done(decision, round_idx)
            round_span.set_attribute("decision_needs_more", decision.needs_more_research)
            round_span.set_attribute("queries_generated", len(decision.additional_queries))

            # Stop if agent is satisfied AND we've met the floor.
            if (
                not decision.needs_more_research or not decision.additional_queries
            ) and signals_before >= target_signals:
                round_span.set_attribute("exit_reason", "satisfied")
                _emit_round_completed(
                    round_idx=round_idx,
                    exit_reason="satisfied",
                    signals_before=signals_before,
                    signals_after=signals_before,
                    decision_needs_more=decision.needs_more_research,
                    queries=list(decision.additional_queries),
                    new_urls=0,
                    articles_extracted=0,
                    facts_added=0,
                    quotes_added=0,
                )
                break
            if not decision.additional_queries:
                round_span.set_attribute("exit_reason", "agent_gave_up")
                _emit_round_completed(
                    round_idx=round_idx,
                    exit_reason="agent_gave_up",
                    signals_before=signals_before,
                    signals_after=signals_before,
                    decision_needs_more=decision.needs_more_research,
                    queries=[],
                    new_urls=0,
                    articles_extracted=0,
                    facts_added=0,
                    quotes_added=0,
                )
                break

            # Serper
            await article_repo.set_pipeline_stage(
                article_id, f"adaptive_search.r{round_idx}.serper"
            )
            with logfire.span(
                "pipeline.stage.adaptive_search.serper",
                round=round_idx,
                queries_count=len(decision.additional_queries),
            ) as serper_span:
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
                serper_span.set_attribute("new_urls_found", len(extra_results))
            if not extra_results:
                round_span.set_attribute("exit_reason", "no_new_urls")
                _emit_round_completed(
                    round_idx=round_idx,
                    exit_reason="no_new_urls",
                    signals_before=signals_before,
                    signals_after=signals_before,
                    decision_needs_more=decision.needs_more_research,
                    queries=list(decision.additional_queries),
                    new_urls=0,
                    articles_extracted=0,
                    facts_added=0,
                    quotes_added=0,
                )
                break

            # Scraping
            await article_repo.set_pipeline_stage(
                article_id, f"adaptive_search.r{round_idx}.scraping"
            )
            with logfire.span(
                "pipeline.stage.adaptive_search.scraping",
                round=round_idx,
                urls_count=len(extra_results),
            ):
                extra_scraped, _ = await run_scraping_agent(
                    extra_results,
                    topic,
                    scraping_config=settings.scraping,
                    jina_api_key=jina_api_key,
                )

            # Parsing
            await article_repo.set_pipeline_stage(
                article_id, f"adaptive_search.r{round_idx}.parsing"
            )
            with logfire.span(
                "pipeline.stage.adaptive_search.parsing",
                round=round_idx,
                pages_count=len(extra_scraped),
            ) as parsing_span:
                extra_articles = await run_parsing_agent(
                    extra_scraped, config=settings.parsing
                )
                parsing_span.set_attribute("articles_count", len(extra_articles))
            articles = articles + extra_articles  # extend pool for downstream rerank

            # Extraction
            await article_repo.set_pipeline_stage(
                article_id, f"adaptive_search.r{round_idx}.extraction"
            )
            with logfire.span(
                "pipeline.stage.adaptive_search.extraction",
                round=round_idx,
                articles_count=len(extra_articles),
            ) as extraction_span:
                extra_extraction = await run_extraction_agent(
                    extra_articles,
                    topic=topic,
                    language=domain.language,
                    config=settings.extraction,
                )
                extraction_span.set_attribute(
                    "facts_extracted", len(extra_extraction.facts)
                )
                extraction_span.set_attribute(
                    "quotes_extracted", len(extra_extraction.quotes)
                )
            extraction = merge_extraction(extraction, extra_extraction)
            log.extraction_done(extraction)

            signals_after = len(extraction.facts) + len(extraction.quotes)
            round_span.set_attribute("signals_after", signals_after)

            # Early exit if we hit the floor — don't waste a budget on another round.
            if signals_after >= target_signals:
                round_span.set_attribute("exit_reason", "target_met")
                _emit_round_completed(
                    round_idx=round_idx,
                    exit_reason="target_met",
                    signals_before=signals_before,
                    signals_after=signals_after,
                    decision_needs_more=decision.needs_more_research,
                    queries=list(decision.additional_queries),
                    new_urls=len(extra_results),
                    articles_extracted=len(extra_articles),
                    facts_added=len(extra_extraction.facts),
                    quotes_added=len(extra_extraction.quotes),
                )
                break
            round_span.set_attribute("exit_reason", "loop_continues")
            _emit_round_completed(
                round_idx=round_idx,
                exit_reason="loop_continues",
                signals_before=signals_before,
                signals_after=signals_after,
                decision_needs_more=decision.needs_more_research,
                queries=list(decision.additional_queries),
                new_urls=len(extra_results),
                articles_extracted=len(extra_articles),
                facts_added=len(extra_extraction.facts),
                quotes_added=len(extra_extraction.quotes),
            )
    return articles, extraction
