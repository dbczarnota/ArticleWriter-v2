# agents/pipeline/_persistence.py
"""Pipeline → DB row translation.

Extracted from runner.py to keep the orchestration entry point under a
reasonable line count. Both success-return paths (followup-OK and
followup-skipped) share the same translation + write call.
"""

from __future__ import annotations

from agents._base.types import EmbedCandidate
from agents.extraction.agent import ExtractionResult


async def persist_article_done(
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
    """Translate agent-level types to DB rows and persist the completed Article."""
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
            source_urls=list(f.source_urls),
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
            source_urls=list(q.source_urls),
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
