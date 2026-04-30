# agents/pipeline/runner.py
from __future__ import annotations

from agents._base.types import ArticleOutput
from agents.extraction.agent import ExtractionResult
from agents.search.agent import run_search_agent
from agents.scraping.agent import run_scraping_agent
from agents.parsing.agent import run_parsing_agent
from agents.extraction.agent import run_extraction_agent
from agents.adaptive_search.agent import run_adaptive_search_agent
from agents.instructions.agent import run_instructions_agent
from agents.writer.agent import run_writer_agent
from agents.reflection.agent import run_reflection_agent
from agents.followup.agent import run_followup_agent
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
) -> ArticleOutput:
    # Stage 1: Research
    search_results = await run_search_agent(
        topic,
        config=settings.search,
        domain_language=domain.language,
        serper_api_key=serper_api_key,
    )
    scraped = await run_scraping_agent(
        search_results,
        topic,
        scraping_config=settings.scraping,
        jina_api_key=jina_api_key,
    )
    articles = await run_parsing_agent(scraped, config=settings.parsing)
    extraction = await run_extraction_agent(
        articles,
        topic=topic,
        language=domain.language,
        config=settings.extraction,
    )

    # Stage 2: Adaptive search loop
    if settings.pipeline.adaptive_search:
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

    # Stage 3: Writing
    brief = await run_instructions_agent(
        extraction,
        topic=topic,
        domain=domain,
        config=settings.instructions,
    )
    article = await run_writer_agent(
        brief,
        topic=topic,
        domain=domain,
        config=settings.writer,
    )

    # Stage 4: Reflection
    if settings.pipeline.reflection:
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
        )

    # Stage 5: Follow-up
    if settings.pipeline.followup:
        return await run_followup_agent(
            article,
            topic=topic,
            extraction_result=extraction,
            config=settings.followup,
        )

    sources = list(
        {f.source_url for f in extraction.facts} | {q.source_url for q in extraction.quotes}
    )
    return ArticleOutput(
        html=article.html,
        alternative_titles=[],
        followup_topics=[],
        used_facts=[],
        used_quotes=[],
        sources=sources,
    )


def _merge_extraction(base: ExtractionResult, extra: ExtractionResult) -> ExtractionResult:
    seen_facts = {f.text for f in base.facts}
    seen_quotes = {q.text for q in base.quotes}
    merged_facts = base.facts + [f for f in extra.facts if f.text not in seen_facts]
    merged_quotes = base.quotes + [q for q in extra.quotes if q.text not in seen_quotes]
    merged_keywords = list(dict.fromkeys(base.keywords + extra.keywords))
    return ExtractionResult(facts=merged_facts, quotes=merged_quotes, keywords=merged_keywords)
