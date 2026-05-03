# backend/api/v2.py
from __future__ import annotations

import dataclasses
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from agents._base.resilient import AllModelsFailedError, InsufficientSourcesError
from agents.pipeline.runner import run_pipeline
from backend.api.schemas import ArticleRequest, DomainConfigUpdate
from backend.auth.deps import get_current_org, get_current_user
from backend.auth.protocols import AuthenticatedUser
from backend.config import AppSettings
from backend.db.models import Org, OrgConfig
from backend.domain import get_domain_config
from backend.repositories import get_article_repo, get_org_config_repo, get_org_repo
from backend.repositories.protocols import ArticleRepository, OrgConfigRepository, OrgRepository
from backend.secrets import Secrets, get_secrets

router = APIRouter(prefix="/v2")


@router.post("/write_article")
async def write_article(
    req: ArticleRequest,
    cfg: Secrets = Depends(get_secrets),
    user: AuthenticatedUser = Depends(get_current_user),
    org: Org = Depends(get_current_org),
    org_config_repo: OrgConfigRepository = Depends(get_org_config_repo),
) -> dict:
    """Generate an article and persist it under the authenticated user's org.

    Auth: Authorization: Bearer <jwt> + X-Org-Code header.
    Tenant: org.domain_name (resolved from X-Org-Code via DB) overrides any
    domain in the request body — operators cannot pivot to other editorial
    brands by request payload.
    """
    # Build settings from request body, then force-override domain to the org's domain.
    app_settings = AppSettings.from_request(req)
    if app_settings.domain != org.domain_name:
        from dataclasses import replace

        app_settings = replace(app_settings, domain=org.domain_name)
    domain = await get_domain_config(org.code, org.domain_name, org_config_repo)
    if domain is None:
        raise HTTPException(
            status_code=412,
            detail=f"No domain config found for org '{org.code}'. Run seed script or configure via PUT /v2/domain-config.",
        )
    try:
        result = await run_pipeline(
            req.topic,
            settings=app_settings,
            domain=domain,
            serper_api_key=cfg.serper_api_key,
            jina_api_key=cfg.jina_api_key,
            urls=req.urls or None,
            additional_instructions=req.additional_instructions,
            org_code=org.code,
            author_user_id=user.id,
        )
    except InsufficientSourcesError as exc:
        # 422 unprocessable: pipeline ran but couldn't gather enough source material
        # to ground the article (Serper/Jina credit issues, all sources rejected, etc.).
        # Refusing to return a hallucinated article is the correct behavior.
        raise HTTPException(
            status_code=422,
            detail={
                "error": "insufficient_sources",
                "message": str(exc),
                "facts_count": exc.facts_count,
                "quotes_count": exc.quotes_count,
                "min_required": exc.min_required,
                "upstream_errors": exc.upstream_errors,
            },
        ) from exc
    except AllModelsFailedError as exc:
        raise HTTPException(status_code=503, detail=f"All LLM models failed: {exc}") from exc
    return dataclasses.asdict(result)


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
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """Tenant-filtered article list, newest first. Returns minimal projection;
    full article via GET /v2/articles/{id}."""
    articles = await article_repo.list_by_org(
        org_code=org.code, limit=limit, offset=offset
    )
    return [
        {
            "id": str(a.id),
            "topic": a.topic,
            "status": a.status,
            "domain_name": a.domain_name,
            "author_user_id": a.author_user_id,
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
        "domain_name": article.domain_name,
        "topic": article.topic,
        "status": article.status,
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
                "source_url": f.source_url,
                "source_title": f.source_title,
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
                "source_url": q.source_url,
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


@router.get("/domain-config")
async def get_domain_config_endpoint(
    org: Org = Depends(get_current_org),
    org_config_repo: OrgConfigRepository = Depends(get_org_config_repo),
) -> dict:
    """Return the current org's domain config. 404 if not yet configured."""
    config = await org_config_repo.get(org.code)
    if config is None:
        raise HTTPException(status_code=404, detail="Domain config not found for this org")
    return _org_config_to_dict(config)


@router.put("/domain-config")
async def put_domain_config_endpoint(
    body: DomainConfigUpdate,
    org: Org = Depends(get_current_org),
    org_config_repo: OrgConfigRepository = Depends(get_org_config_repo),
) -> dict:
    """Upsert the org's domain config. Returns the saved config."""
    config = OrgConfig(org_code=org.code, **body.model_dump())
    saved = await org_config_repo.upsert(config)
    return _org_config_to_dict(saved)


def _org_config_to_dict(config: OrgConfig) -> dict:
    return {
        "org_code": config.org_code,
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
        "example_articles": config.example_articles,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }
