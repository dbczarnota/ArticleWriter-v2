"""Classify stream topics and link them to Discovery topics."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import logfire
import sqlalchemy as sa

from agents._base.config import ExtractionAgentConfig
from agents.discovery.classifier.agent import run_classifier_agent
from agents.discovery.topic_matcher.agent import TopicCandidate, run_topic_matcher_agent
from agents.discovery.topic_writer.agent import run_topic_writer_agent
from backend.database import get_session_maker
from backend.domain import DomainConfig
from backend.repositories import get_discovery_repo

_BATCH = 20
"""Max stream topics to classify per scheduler tick."""


def _classifier_config(domain: DomainConfig) -> ExtractionAgentConfig:
    return ExtractionAgentConfig(
        model=domain.discovery_classifier_model,
        fallback_models=tuple(domain.discovery_classifier_fallback_models),
    )


def _matcher_config(domain: DomainConfig) -> ExtractionAgentConfig:
    return ExtractionAgentConfig(
        model=domain.discovery_matcher_model,
        fallback_models=tuple(domain.discovery_matcher_fallback_models),
    )


def _writer_config(domain: DomainConfig) -> ExtractionAgentConfig:
    return ExtractionAgentConfig(
        model=domain.discovery_topic_writer_model,
        fallback_models=tuple(domain.discovery_topic_writer_fallback_models),
    )


async def process_unclassified_stream_topics(org_code: str, domain: DomainConfig) -> int:
    """Find unclassified stream topics for org, classify and link to DiscoveryTopics.
    Returns the number of topics processed."""
    from backend.db.models import StreamSubscription, StreamTopic

    sm = get_session_maker()
    if sm is None:
        return 0

    async with sm() as session:
        result = await session.execute(
            sa.select(StreamTopic)
            .join(StreamSubscription, StreamTopic.subscription_id == StreamSubscription.id)  # type: ignore[arg-type]
            .where(
                StreamSubscription.org_code == org_code,  # type: ignore[arg-type]
                StreamTopic.classified_at.is_(None),  # type: ignore[union-attr]
            )
            .limit(_BATCH)
        )
        topics = list(result.scalars().all())

    if not topics:
        return 0

    repo = get_discovery_repo()
    processed = 0
    for topic in topics:
        try:
            await _process_one(topic.id, topic.title, topic.summary, org_code, domain, repo)
            processed += 1
        except Exception as exc:
            logfire.warn(
                "stream.classify.failed",
                stream_topic_id=str(topic.id),
                org_code=org_code,
                error=str(exc)[:300],
            )
    return processed


async def _process_one(
    stream_topic_id,
    title: str,
    summary: str,
    org_code: str,
    domain: DomainConfig,
    repo,
) -> None:
    from backend.db.models import DiscoveryTopic, StreamTopic

    t0 = time.perf_counter()

    classifier_decision = await run_classifier_agent(
        title=title,
        summary=summary,
        categories=domain.discovery_categories,
        config=_classifier_config(domain),
    )

    active_topics = await repo.list_active_topics(
        org_code=org_code,
        window_days=domain.discovery_topic_matching_window_days,
    )
    candidates = [TopicCandidate(id=t.id, title=t.title, blurb=t.blurb) for t in active_topics]
    match_decision = await run_topic_matcher_agent(
        title=title,
        summary=summary,
        candidates=candidates,
        config=_matcher_config(domain),
    )

    discovery_topic_id = match_decision.matched_topic_id
    if discovery_topic_id is None:
        descriptor = await run_topic_writer_agent(
            title=title,
            summary=summary,
            language=domain.language,
            config=_writer_config(domain),
        )
        new_topic = await repo.create_topic(
            org_code=org_code,
            title=descriptor.title,
            blurb=descriptor.blurb,
            categories=list(classifier_decision.categories),
        )
        discovery_topic_id = new_topic.id

    now = datetime.now(UTC)
    sm = get_session_maker()
    async with sm() as session:  # type: ignore[union-attr]
        stream_topic = await session.get(StreamTopic, stream_topic_id)
        if stream_topic is None:
            return
        stream_topic.categories = list(classifier_decision.categories)
        stream_topic.topic_id = discovery_topic_id
        stream_topic.classified_at = now
        session.add(stream_topic)

        # Bump the discovery topic's last_activity_at and union categories
        disc_topic = await session.get(DiscoveryTopic, discovery_topic_id)
        if disc_topic is not None:
            existing = set(disc_topic.categories)
            existing.update(classifier_decision.categories)
            disc_topic.categories = sorted(existing)
            disc_topic.last_activity_at = now
            session.add(disc_topic)

        await session.commit()

    logfire.info(
        "stream.classify.done",
        stream_topic_id=str(stream_topic_id),
        discovery_topic_id=str(discovery_topic_id),
        categories=list(classifier_decision.categories),
        was_new_topic=match_decision.matched_topic_id is None,
        duration_ms=(time.perf_counter() - t0) * 1000,
    )
