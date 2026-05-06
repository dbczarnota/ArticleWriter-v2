# backend/api/v2.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID

import logfire
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query
from pydantic import BaseModel

from agents.pipeline.runner import run_pipeline
from backend.api.schemas import ArticleRequest, ArticleUpdate, DomainConfigUpdate
from backend.auth.deps import get_current_org, get_current_user
from backend.auth.protocols import AuthenticatedUser
from backend.config import AppSettings, apply_org_models
from backend.db.models import DiscoveryTopic, Org, OrgConfig
from backend.domain import DomainConfig, get_domain_config
from backend.repositories import (
    get_article_repo,
    get_discovery_repo,
    get_org_config_repo,
    get_org_repo,
)
from backend.repositories.protocols import (
    ArticleRepository,
    DiscoveryRepository,
    OrgConfigRepository,
    OrgRepository,
)
from backend.secrets import Secrets, get_secrets

router = APIRouter(prefix="/v2")

# Lifted to module scope — rebuilt per-call inside _apply_article_domain_overrides
# before this move, which was wasteful.
_DOMAIN_OVERRIDE_KEY_MAP = {
    "search_freshness": "default_search_freshness",
    "num_queries": "default_num_queries",
    "max_results": "default_max_results",
    "min_source_signals": "default_min_source_signals",
    "max_facts": "max_facts_in_article",
    "max_quotes": "max_quotes_in_article",
    "reflection_context_articles": "default_reflection_context_articles",
}
_DOMAIN_OVERRIDE_TUPLE_FIELDS = {"media_search_languages", "example_articles", "example_titles"}


def _build_app_settings(*, req: ArticleRequest, org_domain_name: str, domain):
    """Build AppSettings the same way for both regular write_article and
    the discovery topic bridge. Includes:
    - apply_org_models from DomainConfig (per-agent model overrides)
    - per-request agent overrides via from_request
    - reflection.max_rounds from domain.reflection_rounds
    Returns the assembled AppSettings."""
    from dataclasses import replace as dc_replace

    base = AppSettings(domain=org_domain_name)
    base = apply_org_models(base, domain)
    if domain.reflection_rounds != 1:
        base = dc_replace(
            base,
            reflection=dc_replace(base.reflection, max_rounds=domain.reflection_rounds),
        )
    return AppSettings.from_request(req, base=base)


@router.post("/write_article", status_code=202)
async def write_article(
    req: ArticleRequest,
    background_tasks: BackgroundTasks,
    user: AuthenticatedUser = Depends(get_current_user),
    org: Org = Depends(get_current_org),
    org_config_repo: OrgConfigRepository = Depends(get_org_config_repo),
    article_repo: ArticleRepository = Depends(get_article_repo),
) -> dict:
    """Start article generation in the background and return immediately.

    Returns 202 Accepted with {id, status, topic} so the frontend can navigate
    to the article and poll GET /v2/articles/{id} until status != 'running'.
    """
    # Pull secrets inside the function rather than as a FastAPI Depends arg.
    # When `cfg` was an arg, instrument_fastapi serialized it into the span's
    # `fastapi.arguments.values` and Logfire's scrubber had to redact each
    # api_key field. Cleaner not to attempt the serialization at all.
    cfg = get_secrets()
    domain = await get_domain_config(org.code, org.domain_name, org_config_repo)
    if domain is None:
        raise HTTPException(
            status_code=412,
            detail=f"No domain config found for org '{org.code}'. Run seed script or configure via PUT /v2/domain-config.",
        )

    if req.domain_overrides:
        domain = _apply_article_domain_overrides(domain, req.domain_overrides)

    # Build settings: org models first (lower priority), per-request agent overrides on top.
    app_settings = _build_app_settings(req=req, org_domain_name=org.domain_name, domain=domain)

    article_id = await article_repo.create_running(
        org_code=org.code,
        author_user_id=user.id,
        author_email=user.email,
        author_name=(req.author_name or "").strip() or None,
        domain_name=org.domain_name,
        topic=req.topic,
        additional_instructions=req.additional_instructions,
        input_urls=list(req.urls or []),
    )

    # Note: no logfire.set_baggage(...) here. FastAPI BackgroundTasks runs
    # AFTER the response has been sent, by which point any context manager
    # opened around add_task() has already exited — so endpoint-level baggage
    # would be a no-op for the pipeline run. The article.created event above
    # already carries article_id/org_code as explicit kwargs (so it's
    # queryable), and _run_pipeline_inner re-sets baggage at runner scope to
    # cover every span emitted during the actual pipeline execution.
    background_tasks.add_task(
        _run_pipeline_background,
        article_id=article_id,
        req=req,
        app_settings=app_settings,
        domain=domain,
        cfg=cfg,
        org_code=org.code,
        author_user_id=user.id,
    )

    return {"id": str(article_id), "status": "running", "topic": req.topic}


async def _run_pipeline_from_topic_background(
    *,
    topic_id: UUID,
    items_at_consume: int,
    discovery_repo: DiscoveryRepository,
    article_id: UUID,
    req: ArticleRequest,
    app_settings: AppSettings,
    domain,
    cfg: Secrets,
    org_code: str,
    author_user_id: str,
) -> None:
    """Discovery-bridge background task: marks the source topic consumed
    AS the pipeline begins, then delegates to the regular pipeline.
    Marking inside the task instead of inside the endpoint means a pod
    death between add_task and task start leaves the topic open, not
    orphaned in 'consumed' state with no article."""
    try:
        await discovery_repo.mark_topic_consumed(
            topic_id=topic_id, article_id=article_id, items_at_consume=items_at_consume
        )
        logfire.info(
            "discovery.topic.write_article_started",
            topic_id=str(topic_id),
            article_id=str(article_id),
            items_count=items_at_consume,
        )
    except Exception as e:
        # If the consumed-marking fails, still try to write the article.
        # The topic stays open, which is the safer default.
        logfire.warn(
            "discovery.topic.consume_marker_failed",
            topic_id=str(topic_id),
            article_id=str(article_id),
            error_type=type(e).__name__,
            error_message=str(e)[:500],
        )
    await _run_pipeline_background(
        article_id=article_id,
        req=req,
        app_settings=app_settings,
        domain=domain,
        cfg=cfg,
        org_code=org_code,
        author_user_id=author_user_id,
    )


async def _run_pipeline_background(
    *,
    article_id: UUID,
    req: ArticleRequest,
    app_settings: AppSettings,
    domain,
    cfg: Secrets,
    org_code: str,
    author_user_id: str,
) -> None:
    """Run the pipeline and persist the result. Errors are swallowed here —
    runner already marks the article as failed in the DB on exceptions.

    Wall-clock-bounded by `app_settings.pipeline.total_timeout_s` (default 15 min).
    On timeout the runner's exception handler marks the article failed before
    asyncio.wait_for re-raises TimeoutError, so the user never sees a
    perpetually-running article even if every per-call timeout misfires.
    """
    import asyncio

    try:
        await asyncio.wait_for(
            run_pipeline(
                req.topic,
                settings=app_settings,
                domain=domain,
                serper_api_key=cfg.serper_api_key,
                jina_api_key=cfg.jina_api_key,
                urls=req.urls or None,
                additional_instructions=req.additional_instructions,
                org_code=org_code,
                author_user_id=author_user_id,
                _article_id=article_id,
            ),
            timeout=app_settings.pipeline.total_timeout_s,
        )
    except TimeoutError:
        logfire.error(
            "pipeline.total_timeout_hit",
            article_id=str(article_id),
            org_code=org_code,
            timeout_s=app_settings.pipeline.total_timeout_s,
        )
        # Runner's exception handler still marks the article as failed.
    except Exception:
        # Runner handles DB failure marking internally for non-timeout errors.
        pass


@router.get("/me")
async def get_me(user: AuthenticatedUser = Depends(get_current_user)) -> dict:
    """Return the current user from JWT (or NullAuth fallback for run.py)."""
    return user.model_dump()


@router.get("/orgs")
async def list_my_orgs(
    user: AuthenticatedUser = Depends(get_current_user),
    org_repo: OrgRepository = Depends(get_org_repo),
) -> list[dict]:
    """List orgs the current user belongs to (per JWT claim), enriched with
    domain_name from our DB. Orgs not yet synced/mapped are returned with
    `domain_name=None` so the frontend can prompt for setup."""
    orgs = await org_repo.list_for_user(user.org_codes)
    return [
        {
            "code": o.code,
            "name": o.name,
            "domain_name": o.domain_name or None,
        }
        for o in orgs
    ]


@router.get("/articles")
async def list_articles(
    org: Org = Depends(get_current_org),
    article_repo: ArticleRepository = Depends(get_article_repo),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    created_after: datetime | None = Query(None),
    created_before: datetime | None = Query(None),
) -> list[dict]:
    """Tenant-filtered article list, newest first. Returns minimal projection;
    full article via GET /v2/articles/{id}.

    `created_after` / `created_before` accept ISO-8601 datetimes (e.g.
    '2026-04-28T00:00:00Z') and bound the result inclusively. None means
    no bound on that side."""
    articles = await article_repo.list_by_org(
        org_code=org.code,
        limit=limit,
        offset=offset,
        created_after=created_after,
        created_before=created_before,
    )
    return [
        {
            "id": str(a.id),
            "topic": a.topic,
            "status": a.status,
            "pipeline_stage": a.pipeline_stage,
            "marked_done": a.marked_done,
            "domain_name": a.domain_name,
            "author_user_id": a.author_user_id,
            "author_email": a.author_email,
            "author_name": a.author_name,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            "total_duration_ms": a.total_duration_ms,
        }
        for a in articles
    ]


@router.get("/articles/{article_id}")
async def get_article(
    article_id: UUID,
    org: Org = Depends(get_current_org),
    article_repo: ArticleRepository = Depends(get_article_repo),
) -> dict:
    """Full article including all child rows (facts, quotes, embed candidates,
    usage events, fallback events). Returns 404 when the article doesn't
    exist OR exists but belongs to a different org — no existence leak across
    tenants."""
    article = await article_repo.get(article_id, org_code=org.code)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return {
        "id": str(article.id),
        "org_code": article.org_code,
        "author_user_id": article.author_user_id,
        "author_email": article.author_email,
        "author_name": article.author_name,
        "domain_name": article.domain_name,
        "topic": article.topic,
        "additional_instructions": article.additional_instructions,
        "input_urls": article.input_urls,
        "status": article.status,
        "pipeline_stage": article.pipeline_stage,
        "marked_done": article.marked_done,
        "marked_done_by_name": article.marked_done_by_name,
        "html": article.html,
        "alternative_titles": article.alternative_titles,
        "followup_topics": article.followup_topics,
        "sources": article.sources,
        "pipeline_timing": article.pipeline_timing,
        "errors": article.errors,
        "total_duration_ms": article.total_duration_ms,
        "insufficient_sources_detail": article.insufficient_sources_detail,
        "created_at": article.created_at.isoformat() if article.created_at else None,
        "completed_at": article.completed_at.isoformat() if article.completed_at else None,
        "facts": [
            {
                "id": str(f.id),
                "text": f.text,
                "context": f.context,
                "source_urls": list(f.source_urls),
                "was_used": f.was_used,
            }
            for f in article.facts
        ],
        "quotes": [
            {
                "id": str(q.id),
                "text": q.text,
                "speaker": q.speaker,
                "context": q.context,
                "source_urls": list(q.source_urls),
                "was_used": q.was_used,
            }
            for q in article.quotes
        ],
        "embed_candidates": [
            {
                "id": str(e.id),
                "url": e.url,
                "title": e.title,
                "source": e.source,
                "thumbnail_url": e.thumbnail_url,
                "description": e.description,
                "channel": e.channel,
                "competitor_source_url": e.competitor_source_url,
            }
            for e in article.embed_candidates
        ],
        "usage_events": [
            {
                "id": str(u.id),
                "agent_name": u.agent_name,
                "model": u.model,
                "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens,
                "duration_ms": u.duration_ms,
                "occurred_at": u.occurred_at.isoformat() if u.occurred_at else None,
            }
            for u in article.usage_events
        ],
        "fallback_events": [
            {
                "id": str(fe.id),
                "agent_name": fe.agent_name,
                "failed_model": fe.failed_model,
                "error_type": fe.error_type,
                "error_message": fe.error_message,
                "occurred_at": fe.occurred_at.isoformat() if fe.occurred_at else None,
            }
            for fe in article.fallback_events
        ],
    }


@router.patch("/articles/{article_id}")
async def patch_article(
    article_id: UUID,
    body: ArticleUpdate,
    org: Org = Depends(get_current_org),
    article_repo: ArticleRepository = Depends(get_article_repo),
) -> dict:
    """Partial update — currently only `marked_done` flag."""
    await article_repo.set_marked_done(
        article_id,
        org_code=org.code,
        marked_done=body.marked_done,
        marked_done_by_name=body.marked_done_by_name if body.marked_done else None,
    )
    return {"ok": True}


@router.get("/domain-config")
async def get_domain_config_endpoint(
    org: Org = Depends(get_current_org),
    org_config_repo: OrgConfigRepository = Depends(get_org_config_repo),
) -> dict:
    """Return the current org's domain config. 404 if not yet configured."""
    config = await org_config_repo.get(org.code)
    if config is None:
        raise HTTPException(status_code=404, detail="Domain config not found for this org")
    return _org_config_to_dict(config, domain_name=org.domain_name)


@router.put("/domain-config")
async def put_domain_config_endpoint(
    body: DomainConfigUpdate,
    org: Org = Depends(get_current_org),
    org_repo: OrgRepository = Depends(get_org_repo),
    org_config_repo: OrgConfigRepository = Depends(get_org_config_repo),
) -> dict:
    """Upsert the org's domain config. Returns the saved config.

    `domain_name` is dispatched to the orgs table (it doesn't live in
    org_configs); everything else is upserted on org_configs.
    """
    patch = body.model_dump(exclude_unset=True)
    new_domain_name = patch.pop("domain_name", None)
    effective_domain = org.domain_name
    if new_domain_name is not None and new_domain_name != org.domain_name:
        await org_repo.set_domain_name(org.code, new_domain_name)
        effective_domain = new_domain_name
    # Load the existing row so unset fields keep their stored values.
    existing = await org_config_repo.get(org.code)
    existing_data = existing.model_dump() if existing is not None else {}
    existing_data.pop("org_code", None)
    merged = {**existing_data, **patch}
    config = OrgConfig(org_code=org.code, **merged)
    saved = await org_config_repo.upsert(config)
    return _org_config_to_dict(saved, domain_name=effective_domain)


def _topic_to_json(
    t: DiscoveryTopic,
    *,
    new_items_since_consume: int = 0,
    item_count: int = 0,
    feed_hosts: list[str] | None = None,
    topic_image_url: str | None = None,
) -> dict:
    return {
        "id": str(t.id),
        "title": t.title,
        "blurb": t.blurb,
        "categories": list(t.categories),
        "status": t.status,
        "first_seen_at": t.first_seen_at.isoformat() if t.first_seen_at else None,
        "last_activity_at": t.last_activity_at.isoformat() if t.last_activity_at else None,
        "consumed_article_id": str(t.consumed_article_id) if t.consumed_article_id else None,
        "consumed_at": t.consumed_at.isoformat() if t.consumed_at else None,
        "items_at_consume": t.items_at_consume,
        "new_items_since_consume": new_items_since_consume,
        "item_count": item_count,
        "feed_hosts": feed_hosts or [],
        "topic_image_url": topic_image_url,
    }


def _topic_image_from_items(items: list) -> str | None:
    """Pick the oldest item's image as the topic's hero image. Falls back
    through later items if the originator had no image — UX wants *some*
    thumbnail when one exists in the topic."""
    ordered = sorted(items, key=lambda it: it.fetched_at)
    for it in ordered:
        if it.image_url:
            return it.image_url
    return None


def _hosts_from_items(items: list) -> list[str]:
    """Top-3 hostnames by frequency across items' canonical URLs."""
    from collections import Counter
    from urllib.parse import urlparse

    counts: Counter[str] = Counter()
    for it in items:
        try:
            host = urlparse(it.canonical_url).hostname or ""
        except (ValueError, AttributeError):
            host = ""
        if host:
            counts[host] += 1
    return [h for h, _ in counts.most_common(3)]


# ---------------------------------------------------------------------------
# Discovery — topics
# ---------------------------------------------------------------------------


_SORT_KEYS = {"last_activity", "first_seen", "item_count"}


@router.get("/discovery/topics")
async def list_discovery_topics(
    org: Org = Depends(get_current_org),
    discovery_repo: DiscoveryRepository = Depends(get_discovery_repo),
    category: list[str] = Query(default_factory=list),
    status: list[str] = Query(default_factory=lambda: ["open", "resurfaced"]),
    feed_id: UUID | None = Query(default=None),
    since: datetime | None = None,
    sort: str = Query("last_activity"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    if sort not in _SORT_KEYS:
        raise HTTPException(status_code=400, detail=f"Invalid sort: {sort}")

    # Fetch all matching topics (without limit/offset) so we can sort by
    # derived fields (item_count) before paginating. The repo orders by
    # last_activity_at DESC; we re-sort per the requested key. Org-scope
    # caps total topic count, so pulling the full set into Python is fine.
    rows = await discovery_repo.list_topics_for_ui(
        org_code=org.code,
        categories=category or None,
        statuses=status or None,
        since=since,
        feed_id=feed_id,
        limit=10_000,
        offset=0,
    )
    out: list[dict] = []
    for t in rows:
        items = await discovery_repo.list_items_for_topic(topic_id=t.id, org_code=org.code)
        new_count = (
            sum(1 for it in items if it.fetched_at > t.consumed_at)
            if t.consumed_at is not None
            else 0
        )
        out.append(
            _topic_to_json(
                t,
                new_items_since_consume=new_count,
                item_count=len(items),
                feed_hosts=_hosts_from_items(items),
                topic_image_url=_topic_image_from_items(items),
            )
        )

    if sort == "first_seen":
        # Ascending: the user picks "First seen" because they want to see
        # the OLDEST topics surface first ("what's been around the longest").
        # DESC would just duplicate the default last_activity meaning.
        out.sort(key=lambda x: x["first_seen_at"] or "")
    elif sort == "item_count":
        # Tie-break by last_activity so equal-count topics still order
        # predictably (most recently active first).
        out.sort(key=lambda x: (x["item_count"], x["last_activity_at"] or ""), reverse=True)
    else:  # last_activity (default)
        out.sort(key=lambda x: x["last_activity_at"] or "", reverse=True)

    return out[offset : offset + limit]


@router.get("/discovery/topics/{topic_id}")
async def get_discovery_topic(
    topic_id: UUID,
    org: Org = Depends(get_current_org),
    discovery_repo: DiscoveryRepository = Depends(get_discovery_repo),
) -> dict:
    topic = await discovery_repo.get_topic(topic_id=topic_id, org_code=org.code)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    items = await discovery_repo.list_items_for_topic(topic_id=topic_id, org_code=org.code)
    new_count = sum(
        1 for it in items if topic.consumed_at is not None and it.fetched_at > topic.consumed_at
    )
    return {
        **_topic_to_json(
            topic,
            new_items_since_consume=new_count,
            item_count=len(items),
            feed_hosts=_hosts_from_items(items),
            topic_image_url=_topic_image_from_items(items),
        ),
        "items": [
            {
                "id": str(it.id),
                "canonical_url": it.canonical_url,
                "title": it.title,
                "summary": it.summary,
                "image_url": it.image_url,
                "categories": list(it.categories),
                "fetched_at": it.fetched_at.isoformat() if it.fetched_at else None,
                "published_at": it.published_at.isoformat() if it.published_at else None,
            }
            for it in items
        ],
    }


@router.post("/discovery/topics/{topic_id}/dismiss")
async def dismiss_discovery_topic(
    topic_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    org: Org = Depends(get_current_org),
    discovery_repo: DiscoveryRepository = Depends(get_discovery_repo),
) -> dict:
    topic = await discovery_repo.get_topic(topic_id=topic_id, org_code=org.code)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    await discovery_repo.dismiss_topic(topic_id=topic_id, org_code=org.code)
    logfire.info("discovery.topic.dismissed", topic_id=str(topic_id), user_id=user.id)
    return {"id": str(topic_id), "status": "dismissed"}


@router.post("/discovery/topics/{topic_id}/restore")
async def restore_discovery_topic(
    topic_id: UUID,
    org: Org = Depends(get_current_org),
    discovery_repo: DiscoveryRepository = Depends(get_discovery_repo),
) -> dict:
    topic = await discovery_repo.get_topic(topic_id=topic_id, org_code=org.code)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    await discovery_repo.restore_topic(topic_id=topic_id, org_code=org.code)
    return {"id": str(topic_id), "status": "open"}


class WriteFromTopicOverrides(BaseModel):
    """Optional overrides supplied from the pre-write dialog. When omitted,
    the article is written using the topic's title + blurb + every item's
    URL — same as the pre-dialog behavior."""

    topic_override: str | None = None
    additional_instructions: str | None = None
    urls: list[str] | None = None


@router.post("/discovery/topics/{topic_id}/write_article", status_code=202)
async def write_article_from_discovery_topic(
    topic_id: UUID,
    background_tasks: BackgroundTasks,
    overrides: WriteFromTopicOverrides | None = Body(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    org: Org = Depends(get_current_org),
    discovery_repo: DiscoveryRepository = Depends(get_discovery_repo),
    article_repo: ArticleRepository = Depends(get_article_repo),
    org_config_repo: OrgConfigRepository = Depends(get_org_config_repo),
) -> dict:
    topic = await discovery_repo.get_topic(topic_id=topic_id, org_code=org.code)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    items = await discovery_repo.list_items_for_topic(topic_id=topic_id, org_code=org.code)
    all_urls = [it.canonical_url for it in items]

    # Editor's choice: deselect discovered URLs, add their own, mix both.
    # Same trust boundary as POST /v2/write_article — the regular flow
    # already accepts arbitrary URLs from the user, so there's nothing
    # to gate beyond the auth check.
    if overrides and overrides.urls is not None:
        urls = list(overrides.urls) or all_urls
    else:
        urls = all_urls

    final_topic = (
        overrides.topic_override.strip()
        if overrides and overrides.topic_override and overrides.topic_override.strip()
        else topic.title
    )
    # Editor's textarea takes precedence; fall back to topic.blurb (same as
    # the no-overrides path) when not provided. Empty string explicitly
    # wipes the blurb — interpret that as "no instructions at all".
    if overrides is not None and overrides.additional_instructions is not None:
        final_instructions: str | None = overrides.additional_instructions.strip() or None
    else:
        final_instructions = topic.blurb

    cfg = get_secrets()
    domain = await get_domain_config(org.code, org.domain_name, org_config_repo)
    if domain is None:
        raise HTTPException(
            status_code=412,
            detail=f"No domain config found for org '{org.code}'.",
        )
    given = getattr(user, "given_name", None) or ""
    family = getattr(user, "family_name", None) or ""
    author_name = f"{given} {family}".strip() or (user.email or None)

    req = ArticleRequest(
        topic=final_topic,
        urls=urls,
        additional_instructions=final_instructions,
        author_name=author_name,
    )
    app_settings = _build_app_settings(req=req, org_domain_name=org.domain_name, domain=domain)

    article_id = await article_repo.create_running(
        org_code=org.code,
        author_user_id=user.id,
        author_email=user.email,
        author_name=req.author_name,
        domain_name=org.domain_name,
        topic=req.topic,
        additional_instructions=req.additional_instructions,
        input_urls=urls,
    )

    background_tasks.add_task(
        _run_pipeline_from_topic_background,
        topic_id=topic_id,
        items_at_consume=len(urls),
        discovery_repo=discovery_repo,
        article_id=article_id,
        req=req,
        app_settings=app_settings,
        domain=domain,
        cfg=cfg,
        org_code=org.code,
        author_user_id=user.id,
    )

    return {"topic_id": str(topic_id), "article_id": str(article_id), "status": "running"}


@router.get("/discovery/items")
async def list_discovery_items(
    org: Org = Depends(get_current_org),
    discovery_repo: DiscoveryRepository = Depends(get_discovery_repo),
    feed_id: UUID | None = Query(default=None),
    category: list[str] = Query(default_factory=list),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    items = await discovery_repo.list_items_for_org(
        org_code=org.code,
        feed_id=feed_id,
        categories=category or None,
        limit=limit,
        offset=offset,
    )
    return [
        {
            "id": str(it.id),
            "canonical_url": it.canonical_url,
            "title": it.title,
            "summary": it.summary,
            "image_url": it.image_url,
            "categories": list(it.categories),
            "topic_id": str(it.topic_id) if it.topic_id else None,
            "fetched_at": it.fetched_at.isoformat() if it.fetched_at else None,
            "published_at": it.published_at.isoformat() if it.published_at else None,
        }
        for it in items
    ]


# ---------------------------------------------------------------------------
# Discovery — feeds + categories
# ---------------------------------------------------------------------------


@router.get("/discovery/feeds")
async def list_discovery_feeds(
    org: Org = Depends(get_current_org),
    discovery_repo: DiscoveryRepository = Depends(get_discovery_repo),
) -> list[dict]:
    from datetime import UTC, timedelta

    feeds = await discovery_repo.list_feeds_for_org(org.code)
    since = datetime.now(UTC) - timedelta(hours=24)
    out: list[dict] = []
    for f in feeds:
        items_24h = await discovery_repo.count_items_for_feed_since(
            feed_id=f.id, since=since
        )
        out.append(
            {
                "id": str(f.id),
                "feed_url": f.feed_url,
                "last_fetched_at": f.last_fetched_at.isoformat() if f.last_fetched_at else None,
                "last_error": f.last_error,
                "error_count": f.error_count,
                "disabled": f.disabled,
                "items_24h_count": items_24h,
            }
        )
    return out


@router.post("/discovery/feeds/{feed_id}/reset")
async def reset_discovery_feed(
    feed_id: UUID,
    org: Org = Depends(get_current_org),
    discovery_repo: DiscoveryRepository = Depends(get_discovery_repo),
) -> dict:
    feeds = await discovery_repo.list_feeds_for_org(org.code)
    if not any(f.id == feed_id for f in feeds):
        raise HTTPException(status_code=404, detail="Feed not found")
    await discovery_repo.reset_feed_errors(feed_id)
    return {"id": str(feed_id), "error_count": 0, "disabled": False}


@router.get("/discovery/categories")
async def list_discovery_categories(
    org: Org = Depends(get_current_org),
    org_config_repo: OrgConfigRepository = Depends(get_org_config_repo),
) -> list[dict]:
    domain = await get_domain_config(org.code, org.domain_name, org_config_repo)
    if domain is None:
        return []
    return [{"name": c.name, "description": c.description} for c in domain.discovery_categories]


def _apply_article_domain_overrides(domain: DomainConfig, overrides: dict) -> DomainConfig:
    """Apply per-article domain_overrides dict onto a DomainConfig instance.

    Keys use DomainConfigUpdate naming (e.g. 'search_freshness', 'max_facts').
    A mapping translates the few names that differ between the schema and DomainConfig.
    List values are converted to tuples where DomainConfig expects tuples.
    """
    from dataclasses import replace as dc_replace

    patches: dict = {}
    for k, v in overrides.items():
        # Empty list/dict means "no override for this field" — caller cannot
        # explicitly request "clear the org default to []" via the request body.
        # This is intentional: per-article overrides are positive-only.
        if v is None or v == "" or v == [] or v == {}:
            continue
        dc_key = _DOMAIN_OVERRIDE_KEY_MAP.get(k, k)
        if k in _DOMAIN_OVERRIDE_TUPLE_FIELDS and isinstance(v, list):
            v = tuple(v)
        patches[dc_key] = v

    return dc_replace(domain, **patches) if patches else domain


def _org_config_to_dict(config: OrgConfig, *, domain_name: str | None = None) -> dict:
    return {
        "org_code": config.org_code,
        "domain_name": domain_name or "",
        "description": config.description,
        "language": config.language,
        "target_word_count": config.target_word_count,
        "max_facts": config.max_facts,
        "max_quotes": config.max_quotes,
        "search_freshness": config.search_freshness,
        "num_queries": config.num_queries,
        "max_results": config.max_results,
        "min_source_signals": config.min_source_signals,
        "max_pages_to_scrape": config.max_pages_to_scrape,
        "youtube_search": config.youtube_search,
        "twitter_search": config.twitter_search,
        "facebook_search": config.facebook_search,
        "news_search": config.news_search,
        "tiktok_search": config.tiktok_search,
        "instagram_search": config.instagram_search,
        "reddit_search": config.reddit_search,
        "media_search_languages": config.media_search_languages,
        "media_search_num": config.media_search_num,
        "media_search_max_query_tiers": config.media_search_max_query_tiers,
        "youtube_sort_by_date": config.youtube_sort_by_date,
        "reflection_context_articles": config.reflection_context_articles,
        "guidelines": config.guidelines,
        "html_format": config.html_format,
        "reflection_stance": config.reflection_stance,
        "reflection_rounds": config.reflection_rounds,
        "example_articles": config.example_articles,
        "example_titles": config.example_titles,
        "agent_models": config.agent_models,
        "agent_fallback_models": config.agent_fallback_models,
        "discovery_enabled": config.discovery_enabled,
        "discovery_feeds": config.discovery_feeds,
        "discovery_categories": config.discovery_categories,
        "discovery_topic_matching_window_days": config.discovery_topic_matching_window_days,
        "discovery_followup_threshold": config.discovery_followup_threshold,
        "discovery_classifier_model": config.discovery_classifier_model,
        "discovery_matcher_model": config.discovery_matcher_model,
        "discovery_topic_writer_model": config.discovery_topic_writer_model,
        "discovery_classifier_fallback_models": config.discovery_classifier_fallback_models,
        "discovery_matcher_fallback_models": config.discovery_matcher_fallback_models,
        "discovery_topic_writer_fallback_models": config.discovery_topic_writer_fallback_models,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }
