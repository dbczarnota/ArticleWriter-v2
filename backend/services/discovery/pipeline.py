"""Per-item processing: classify -> match-or-create-topic -> persist."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import logfire

from agents._base.config import ExtractionAgentConfig
from agents.discovery.classifier.agent import run_classifier_agent
from agents.discovery.topic_matcher.agent import (
    TopicCandidate,
    run_topic_matcher_agent,
)
from agents.discovery.topic_writer.agent import run_topic_writer_agent
from backend.db.models import DiscoveryItem
from backend.domain import DomainConfig
from backend.repositories.protocols import DiscoveryRepository
from backend.services.discovery.canonicalize import canonicalize_url
from backend.services.discovery.feed_fetcher import RawFeedItem


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


async def process_item(
    *,
    raw: RawFeedItem,
    org_code: str,
    domain: DomainConfig,
    feed_id: UUID,
    repo: DiscoveryRepository,
) -> DiscoveryItem:
    canonical = canonicalize_url(raw.url)

    with logfire.set_baggage(
        org_code=org_code,
        feed_id=str(feed_id),
        item_canonical_url=canonical,
    ):
        existing = await repo.get_item_by_url(org_code=org_code, canonical_url=canonical)
        if existing is not None:
            await repo.add_item_to_feed_link(item_id=existing.id, feed_id=feed_id)
            logfire.info(
                "discovery.item.duplicate",
                item_id=str(existing.id),
                feed_id=str(feed_id),
                canonical_url=canonical,
            )
            return existing

        # Classify
        classifier_decision = await run_classifier_agent(
            title=raw.title,
            summary=raw.summary,
            categories=domain.discovery_categories,
            config=_classifier_config(domain),
        )
        logfire.info(
            "discovery.item.categorized",
            categories=list(classifier_decision.categories),
            confidences=dict(classifier_decision.confidences),
            reasoning=classifier_decision.reasoning,
        )

        # Match
        active_topics = await repo.list_active_topics(
            org_code=org_code,
            window_days=domain.discovery_topic_matching_window_days,
        )
        candidates = [TopicCandidate(id=t.id, title=t.title, blurb=t.blurb) for t in active_topics]
        match_decision = await run_topic_matcher_agent(
            title=raw.title,
            summary=raw.summary,
            candidates=candidates,
            config=_matcher_config(domain),
        )
        logfire.info(
            "discovery.item.match_attempt",
            candidates_count=len(candidates),
            matched_topic_id=str(match_decision.matched_topic_id)
            if match_decision.matched_topic_id
            else None,
            reasoning=match_decision.reasoning,
        )

        # Persist item AFTER matcher/writer decision so a crash in either
        # step doesn't leave an orphan. If the matcher said "match", we
        # set topic_id directly. If "new topic", we create the topic
        # first, then upsert the item with its topic_id already set.
        topic_id_for_item = match_decision.matched_topic_id
        if topic_id_for_item is None:
            descriptor = await run_topic_writer_agent(
                title=raw.title, summary=raw.summary, config=_writer_config(domain)
            )
            topic = await repo.create_topic(
                org_code=org_code,
                title=descriptor.title,
                blurb=descriptor.blurb,
                categories=list(classifier_decision.categories),
            )
            topic_id_for_item = topic.id

        item = DiscoveryItem(
            org_code=org_code,
            canonical_url=canonical,
            guid=raw.guid,
            title=raw.title[:1024],
            summary=raw.summary,
            published_at=raw.published_at,
            categories=list(classifier_decision.categories),
            category_confidences=dict(classifier_decision.confidences) or None,
            topic_id=topic_id_for_item,
        )
        item = await repo.upsert_item(item)
        await repo.add_item_to_feed_link(item_id=item.id, feed_id=feed_id)

        # attach_item_to_topic also unions categories and bumps last_activity_at.
        await repo.attach_item_to_topic(
            item_id=item.id,
            topic_id=topic_id_for_item,
            item_categories=list(classifier_decision.categories),
        )
        if match_decision.matched_topic_id is not None:
            logfire.info(
                "discovery.topic.matched",
                topic_id=str(match_decision.matched_topic_id),
                item_id=str(item.id),
            )
            await repo.check_resurface(
                topic_id=match_decision.matched_topic_id,
                threshold=domain.discovery_followup_threshold,
            )

        # Mark processed
        item.processed_at = datetime.now(UTC)
        item = await repo.upsert_item(item)
        logfire.info(
            "discovery.item.processed",
            item_id=str(item.id),
            categories=list(item.categories),
            topic_id=str(item.topic_id) if item.topic_id else None,
            was_new_topic=match_decision.matched_topic_id is None,
        )
        return item
