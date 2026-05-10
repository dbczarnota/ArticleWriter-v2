# backend/api/v2.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID

import logfire
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
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

_MAX_CONCURRENT_RUNNING_PER_ORG = 5


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


@router.post(
    "/write_article",
    status_code=202,
    summary="Start article generation for the calling org",
    tags=["articles"],
)
async def write_article(
    req: ArticleRequest,
    background_tasks: BackgroundTasks,
    user: AuthenticatedUser = Depends(get_current_user),
    org: Org = Depends(get_current_org),
    org_config_repo: OrgConfigRepository = Depends(get_org_config_repo),
    article_repo: ArticleRepository = Depends(get_article_repo),
) -> dict:
    """Creates an article row in `running` state and kicks off the multi-agent
    pipeline as a background task. Returns 202 immediately with `{id, status,
    topic}` so the frontend can navigate to the article and poll
    GET /v2/articles/{id} until `status != 'running'`. Domain config is
    resolved per the calling org's `org_code`; per-request `domain_overrides`
    are merged on top of the stored org defaults.
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

    running_count = await article_repo.count_running_for_org(org.code)
    if running_count >= _MAX_CONCURRENT_RUNNING_PER_ORG:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Org has {running_count} articles currently running "
                f"(cap: {_MAX_CONCURRENT_RUNNING_PER_ORG}). Wait for one to finish."
            ),
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
        social_media_attachments=list(req.social_media_attachments or []),
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
        article_repo=article_repo,
    )

    # `id` kept as a deprecated alias; consumers should migrate to `article_id`,
    # which is what the discovery-bridge endpoint also returns. One-canonical-name
    # contract reduces the if/else in clients.
    return {
        "id": str(article_id),
        "article_id": str(article_id),
        "status": "running",
        "topic": req.topic,
    }


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
    article_repo: ArticleRepository | None = None,
) -> None:
    """Discovery-bridge background task: marks the source topic consumed
    AS the pipeline begins, then delegates to the regular pipeline.
    Marking inside the task instead of inside the endpoint means a pod
    death between add_task and task start leaves the topic open, not
    orphaned in 'consumed' state with no article."""
    try:
        await discovery_repo.mark_topic_consumed(
            topic_id=topic_id,
            article_id=article_id,
            items_at_consume=items_at_consume,
            org_code=org_code,
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
        article_repo=article_repo,
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
    article_repo: ArticleRepository | None = None,
) -> None:
    """Run the pipeline and persist the result. Errors are swallowed here —
    runner already marks the article as failed in the DB on exceptions.

    Wall-clock-bounded by `app_settings.pipeline.total_timeout_s` (default 15 min).
    On timeout `asyncio.wait_for` injects `CancelledError` (a `BaseException`)
    into the runner — the runner's `except Exception` doesn't catch it, so
    we mark the article failed here ourselves. Otherwise the row stays in
    `running` until the next pod restart's startup sweeper.
    """
    import asyncio

    from backend.repositories import get_article_repo

    if article_repo is None:
        article_repo = get_article_repo()

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
                raw_facts_text=req.raw_facts_text,
                article_template=req.article_template,
                editor_extraction=req.editor_extraction,
                skip_web_research=req.skip_web_research,
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
        try:
            await article_repo.mark_failed(
                article_id,
                error_status="failed",
                errors=[
                    {
                        "stage": "pipeline",
                        "error": f"Total pipeline timeout ({app_settings.pipeline.total_timeout_s}s)",
                    }
                ],
            )
        except Exception as mark_err:
            logfire.error(
                "pipeline.mark_failed_after_timeout_failed",
                article_id=str(article_id),
                error_type=type(mark_err).__name__,
                error_message=str(mark_err)[:500],
            )
    except Exception:
        # Belt-and-suspenders: runner normally marks failures itself, but
        # if it raised before reaching the persistence step the row would
        # be stuck in `running`. Only mark when status is still `running`
        # to avoid clobbering a real status set by the runner.
        try:
            row = await article_repo.get(article_id, org_code=org_code)
            if row is not None and row.status == "running":
                await article_repo.mark_failed(
                    article_id,
                    error_status="failed",
                    errors=[
                        {
                            "stage": "pipeline",
                            "error": "Pipeline raised before reaching persistence.",
                        }
                    ],
                )
        except Exception:
            pass


@router.post(
    "/extract_editor_facts",
    summary="Preview LLM-extracted facts and quotes from editor's raw text and/or image",
    tags=["articles"],
)
async def extract_editor_facts_endpoint(
    topic: str = Form(...),
    raw_facts_text: str | None = Form(None),
    language: str | None = Form(None),
    image: UploadFile | None = File(None),
    video: UploadFile | None = File(None),
    image_instructions: str | None = Form(None),
    org: Org = Depends(get_current_org),
    org_config_repo: OrgConfigRepository = Depends(get_org_config_repo),
) -> dict:
    """Modal step 1 → step 2 transition. Accepts multipart with topic + optional
    raw_facts_text, image, and/or video. Runs all extractions in parallel, tags
    each item's `source` so the modal can show 📷/🎬 badges. Language defaults
    to the org's domain config when not provided."""
    import asyncio

    import logfire

    from agents.pipeline._helpers import extract_facts_from_media, extract_facts_from_text

    text = (raw_facts_text or "").strip()
    image_bytes = await image.read() if image is not None else b""
    image_media_type = (image.content_type if image is not None else None) or "image/jpeg"
    video_bytes = await video.read() if video is not None else b""
    video_media_type = (video.content_type if video is not None else None) or "video/mp4"

    if not text and not image_bytes and not video_bytes:
        raise HTTPException(
            status_code=400,
            detail="At least one of raw_facts_text, image, or video must be provided",
        )
    if text and len(text) > 10_000:
        raise HTTPException(
            status_code=400, detail="raw_facts_text must be at most 10 000 characters"
        )
    if image_bytes and len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="image must be at most 10 MiB")
    # Videos can be large — 100 MiB cap.
    if video_bytes and len(video_bytes) > 100 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="video must be at most 100 MiB")

    domain = await get_domain_config(org.code, org.domain_name, org_config_repo)
    if not language:
        language = (domain.language if domain else None) or "pl"
    base_settings = AppSettings(domain=org.domain_name)
    if domain:
        base_settings = apply_org_models(base_settings, domain)
    config = base_settings.media_extraction

    with logfire.span(
        "api.extract_editor_facts",
        topic=topic,
        text_len=len(text),
        has_image=bool(image_bytes),
        has_video=bool(video_bytes),
    ):
        tasks = []
        text_idx: int | None = None
        image_idx: int | None = None
        video_idx: int | None = None
        if text:
            text_idx = len(tasks)
            tasks.append(extract_facts_from_text(text, topic, language, config))
        if image_bytes:
            image_idx = len(tasks)
            tasks.append(
                extract_facts_from_media(
                    image_bytes,
                    image_media_type,
                    topic,
                    language,
                    config,
                    source_marker="editor-provided-photo",
                    image_instructions=image_instructions or None,
                )
            )
        if video_bytes:
            video_idx = len(tasks)
            tasks.append(
                extract_facts_from_media(
                    video_bytes,
                    video_media_type,
                    topic,
                    language,
                    config,
                    source_marker="editor-provided-video",
                    image_instructions=image_instructions or None,
                )
            )
        results = await asyncio.gather(*tasks)
        text_result = results[text_idx] if text_idx is not None else None
        image_result = results[image_idx] if image_idx is not None else None
        video_result = results[video_idx] if video_idx is not None else None

    facts: list[dict] = []
    quotes: list[dict] = []
    keywords: list[str] = []
    for result, source in [
        (text_result, "editor-provided"),
        (image_result, "editor-provided-photo"),
        (video_result, "editor-provided-video"),
    ]:
        if result is None:
            continue
        facts.extend({"text": f.text, "context": f.context, "source": source} for f in result.facts)
        quotes.extend(
            {"text": q.text, "speaker": q.speaker, "context": q.context, "source": source}
            for q in result.quotes
        )
        keywords.extend(result.keywords)
    keywords = list(dict.fromkeys(keywords))

    return {"facts": facts, "quotes": quotes, "keywords": keywords}


class InstagramFetchRequest(BaseModel):
    url: str
    topic: str
    language: str | None = None
    image_instructions: str | None = None


@router.post(
    "/fetch_instagram_facts",
    summary="Fetch an Instagram post and extract facts and quotes",
    tags=["articles"],
)
async def fetch_instagram_facts_endpoint(
    body: InstagramFetchRequest,
    org: Org = Depends(get_current_org),
    org_config_repo: OrgConfigRepository = Depends(get_org_config_repo),
) -> dict:
    """Downloads an Instagram post by URL, then runs parallel extraction:
    vision agent on the media, text agent on description + comments.
    All items are tagged 'editor-provided-instagram'.
    """
    import asyncio

    import logfire

    from agents.pipeline._helpers import extract_facts_from_media, extract_facts_from_text
    from toolsets.apify.instagram.fetcher import (
        ApifyInstagramFetcher,
        HttpxInstagramFetcher,
        parse_shortcode,
    )

    try:
        shortcode = parse_shortcode(body.url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    secrets = get_secrets()
    fetcher = (
        ApifyInstagramFetcher(secrets.apify_api_token)
        if secrets.apify_api_token
        else HttpxInstagramFetcher()
    )
    try:
        post = await fetcher.fetch(shortcode)
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    domain = await get_domain_config(org.code, org.domain_name, org_config_repo)
    language = body.language or (domain.language if domain else None) or "pl"
    base_settings = AppSettings(domain=org.domain_name)
    if domain:
        base_settings = apply_org_models(base_settings, domain)
    config = base_settings.media_extraction
    source = "editor-provided-instagram"

    parts: list[str] = []
    if post.description:
        parts.append(f"## Opis posta\n{post.description}")
    if post.comments:
        parts.append("## Komentarze\n" + "\n".join(f"- {c}" for c in post.comments))
    text = "\n\n".join(parts)

    logfire.info(
        "api.fetch_instagram_facts extraction_input",
        shortcode=shortcode,
        description_len=len(post.description),
        comments_count=len(post.comments),
        has_media=bool(post.media_bytes),
        media_type=post.media_type if post.media_bytes else None,
        text_preview=text[:500],
    )
    with logfire.span(
        "api.fetch_instagram_facts", topic=body.topic, has_media=bool(post.media_bytes)
    ):
        tasks = []
        text_idx: int | None = None
        media_idx: int | None = None
        if text:
            text_idx = len(tasks)
            tasks.append(extract_facts_from_text(text, body.topic, language, config))
        if post.media_bytes:
            media_idx = len(tasks)
            tasks.append(
                extract_facts_from_media(
                    post.media_bytes,
                    post.media_type,
                    body.topic,
                    language,
                    config,
                    source_marker=source,
                    image_instructions=body.image_instructions or None,
                )
            )
        results = await asyncio.gather(*tasks)
        text_result = results[text_idx] if text_idx is not None else None
        media_result = results[media_idx] if media_idx is not None else None

    facts: list[dict] = []
    quotes: list[dict] = []
    keywords: list[str] = []
    for result, src in [(text_result, source), (media_result, source)]:
        if result is None:
            continue
        facts.extend({"text": f.text, "context": f.context, "source": src} for f in result.facts)
        quotes.extend(
            {"text": q.text, "speaker": q.speaker, "context": q.context, "source": src}
            for q in result.quotes
        )
        keywords.extend(result.keywords)
    keywords = list(dict.fromkeys(keywords))
    return {
        "facts": facts,
        "quotes": quotes,
        "keywords": keywords,
        "media_url": post.media_url,
        "media_type": post.media_type if post.media_url else "",
    }


class XFetchRequest(BaseModel):
    url: str
    topic: str
    language: str | None = None


@router.post(
    "/fetch_x_facts",
    summary="Fetch an X.com post and extract facts and quotes",
    tags=["articles"],
)
async def fetch_x_facts_endpoint(
    body: XFetchRequest,
    org: Org = Depends(get_current_org),
    org_config_repo: OrgConfigRepository = Depends(get_org_config_repo),
) -> dict:
    """Fetches an X.com (Twitter) post + replies via Apify, then runs text
    extraction. All items are tagged 'editor-provided-x'.
    Requires APIFY_API_TOKEN — returns 422 when token is missing.
    """
    import logfire

    from agents.pipeline._helpers import extract_facts_from_text
    from toolsets.apify.x.fetcher import ApifyXFetcher

    secrets = get_secrets()
    if not secrets.apify_api_token:
        raise HTTPException(status_code=422, detail="APIFY_API_TOKEN not configured")

    try:
        post = await ApifyXFetcher(secrets.apify_api_token).fetch(body.url)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    domain = await get_domain_config(org.code, org.domain_name, org_config_repo)
    language = body.language or (domain.language if domain else None) or "pl"
    base_settings = AppSettings(domain=org.domain_name)
    if domain:
        base_settings = apply_org_models(base_settings, domain)
    config = base_settings.extraction
    source = "editor-provided-x"

    parts: list[str] = []
    if post.text:
        parts.append(f"## Post na X.com (@{post.author})\n{post.text}")
    if post.comments:
        parts.append("## Odpowiedzi (X.com)\n" + "\n".join(f"- {c}" for c in post.comments))
    text = "\n\n".join(parts)

    if not text:
        return {
            "facts": [],
            "quotes": [],
            "keywords": [],
            "media_url": post.media_url,
            "media_type": post.media_type,
        }

    logfire.info(
        "api.fetch_x_facts extraction_input",
        author=post.author,
        text_preview=text[:500],
        comments_count=len(post.comments),
    )
    with logfire.span("api.fetch_x_facts", topic=body.topic):
        result = await extract_facts_from_text(text, body.topic, language, config)

    facts = [{"text": f.text, "context": f.context, "source": source} for f in result.facts]
    quotes = [
        {"text": q.text, "speaker": q.speaker, "context": q.context, "source": source}
        for q in result.quotes
    ]
    keywords = list(dict.fromkeys(result.keywords))
    return {
        "facts": facts,
        "quotes": quotes,
        "keywords": keywords,
        "media_url": post.media_url,
        "media_type": post.media_type,
    }


_ALLOWED_CDN_HOSTS = {
    # Instagram / Facebook CDN
    "cdninstagram.com",
    "fbcdn.net",
    "instagram.com",
    # Twitter / X CDN
    "twimg.com",
}


@router.get(
    "/download_media",
    summary="Proxy-download a social media CDN file (bypasses cross-origin restriction)",
    tags=["articles"],
)
async def download_media(
    url: str = Query(..., description="CDN URL to download"),
    org: Org = Depends(get_current_org),
) -> None:
    """Fetches a CDN media URL server-side and returns it as a browser download.

    Only CDN hostnames from known Instagram/Twitter domains are allowed to prevent
    this endpoint from being used as an open proxy.
    """
    from urllib.parse import urlparse

    import httpx
    from fastapi.responses import Response as FastAPIResponse

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not any(host == h or host.endswith(f".{h}") for h in _ALLOWED_CDN_HOSTS):
        raise HTTPException(
            status_code=422,
            detail=f"URL host {host!r} is not an allowed CDN domain",
        )

    referer = (
        "https://www.instagram.com/" if "instagram" in host or "fbcdn" in host else "https://x.com/"
    )
    cdn_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": referer,
        "Accept": "*/*",
        "Accept-Language": "pl,en;q=0.9",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            r = await client.get(url, headers=cdn_headers)
            r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502, detail=f"CDN returned {exc.response.status_code}"
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    content_type = r.headers.get("content-type", "application/octet-stream")
    # Reject if CDN returned JSON/HTML instead of media — URL likely expired
    if content_type.startswith(("application/json", "text/html", "text/plain")):
        raise HTTPException(
            status_code=502,
            detail=f"CDN returned {content_type!r} — link may have expired",
        )

    path_part = (parsed.path or "").split("/")[-1].split("?")[0] or "media"
    return FastAPIResponse(
        content=r.content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{path_part}"'},
    )


@router.get(
    "/download_social_post",
    summary="Download media from an Instagram or X.com post via Apify",
    tags=["articles"],
)
async def download_social_post(
    url: str = Query(..., description="Instagram or X.com post URL"),
    org: Org = Depends(get_current_org),
) -> None:
    """Fetches media from a social post through Apify and returns it as a browser download."""
    from urllib.parse import urlparse

    import httpx
    from fastapi.responses import Response as FastAPIResponse

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    secrets = get_secrets()

    if "instagram.com" in host:
        from toolsets.apify.instagram.fetcher import (
            ApifyInstagramFetcher,
            HttpxInstagramFetcher,
            parse_shortcode,
        )

        try:
            shortcode = parse_shortcode(url)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        fetcher = (
            ApifyInstagramFetcher(secrets.apify_api_token)
            if secrets.apify_api_token
            else HttpxInstagramFetcher()
        )
        try:
            post = await fetcher.fetch(shortcode)
        except RuntimeError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        ext = "mp4" if post.media_type == "video/mp4" else "jpg"
        return FastAPIResponse(
            content=post.media_bytes,
            media_type=post.media_type,
            headers={"Content-Disposition": f'attachment; filename="instagram_media.{ext}"'},
        )

    elif "twitter.com" in host or "x.com" in host:
        from toolsets.apify.x.fetcher import ApifyXFetcher

        if not secrets.apify_api_token:
            raise HTTPException(status_code=422, detail="APIFY_API_TOKEN not configured")

        try:
            post = await ApifyXFetcher(secrets.apify_api_token).fetch(url)
        except (ValueError, RuntimeError) as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        if not post.media_url:
            raise HTTPException(status_code=404, detail="No media found in this post")

        cdn_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": "https://x.com/",
            "Accept": "*/*",
        }
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                r = await client.get(post.media_url, headers=cdn_headers)
                r.raise_for_status()
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        ext = "mp4" if post.media_type == "video/mp4" else "jpg"
        return FastAPIResponse(
            content=r.content,
            media_type=post.media_type or r.headers.get("content-type", "application/octet-stream"),
            headers={"Content-Disposition": f'attachment; filename="x_media.{ext}"'},
        )

    else:
        raise HTTPException(status_code=422, detail=f"Unsupported platform: {host!r}")


@router.get(
    "/me",
    summary="Return the calling user's identity",
    tags=["users"],
)
async def get_me(user: AuthenticatedUser = Depends(get_current_user)) -> dict:
    """Returns the current user resolved from the bearer JWT (or the
    NullAuth fallback identity used by `run.py` in local-dev). Used by the
    frontend on boot to show name/email and to gate UI on the user's
    `org_codes` claim.
    """
    return user.model_dump()


@router.get(
    "/orgs",
    summary="List orgs the calling user belongs to",
    tags=["orgs"],
)
async def list_my_orgs(
    user: AuthenticatedUser = Depends(get_current_user),
    org_repo: OrgRepository = Depends(get_org_repo),
) -> list[dict]:
    """Returns the orgs declared in the user's JWT `org_codes` claim,
    enriched with each org's `domain_name` from our DB. Orgs not yet
    synced or mapped come back with `domain_name=None` so the frontend can
    prompt for first-time setup via PUT /v2/domain-config.
    """
    orgs = await org_repo.list_for_user(user.org_codes)
    return [
        {
            "code": o.code,
            "name": o.name,
            "domain_name": o.domain_name or None,
        }
        for o in orgs
    ]


@router.get(
    "/articles",
    summary="List articles for the calling org",
    tags=["articles"],
)
async def list_articles(
    org: Org = Depends(get_current_org),
    article_repo: ArticleRepository = Depends(get_article_repo),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    created_after: datetime | None = Query(None),
    created_before: datetime | None = Query(None),
) -> list[dict]:
    """Returns a tenant-filtered article list (newest first) using a minimal
    projection — fetch the full article via GET /v2/articles/{id}. Filtered
    by the calling org's `org_code`; supports pagination (`limit`/`offset`)
    and inclusive ISO-8601 bounds via `created_after` / `created_before`.
    """
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


@router.get(
    "/articles/{article_id}",
    summary="Get one article with all child rows",
    tags=["articles"],
)
async def get_article(
    article_id: UUID,
    org: Org = Depends(get_current_org),
    article_repo: ArticleRepository = Depends(get_article_repo),
) -> dict:
    """Returns one full article including its facts, quotes, embed
    candidates, usage events, and fallback events. Returns 404 when the
    article does not exist or belongs to a different org — no existence
    leak across tenants. Polled by the frontend during pipeline execution
    to surface live `pipeline_stage` updates.
    """
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
        "facebook_teasers": article.facebook_teasers,
        "social_media_attachments": article.social_media_attachments,
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


@router.patch(
    "/articles/{article_id}",
    summary="Mark an article done / undone",
    tags=["articles"],
)
async def patch_article(
    article_id: UUID,
    body: ArticleUpdate,
    org: Org = Depends(get_current_org),
    article_repo: ArticleRepository = Depends(get_article_repo),
) -> dict:
    """Partial update of an article — currently flips the `marked_done`
    flag and records `marked_done_by_name` on transitions to true. Used by
    the editor UI to dismiss a finished article from the active list;
    scoped to the calling org's `org_code`.
    """
    await article_repo.set_marked_done(
        article_id,
        org_code=org.code,
        marked_done=body.marked_done,
        marked_done_by_name=body.marked_done_by_name if body.marked_done else None,
    )
    return {"ok": True}


@router.get(
    "/domain-config",
    summary="Get the calling org's domain config",
    tags=["domain-config"],
)
async def get_domain_config_endpoint(
    org: Org = Depends(get_current_org),
    org_config_repo: OrgConfigRepository = Depends(get_org_config_repo),
) -> dict:
    """Returns the editorial / pipeline configuration stored for the
    calling org (guidelines, search params, agent models, discovery feeds,
    example articles, etc.). Returns 404 when the org has not yet been
    configured — the frontend uses that to gate the Settings UI into
    first-run mode.
    """
    config = await org_config_repo.get(org.code)
    if config is None:
        raise HTTPException(status_code=404, detail="Domain config not found for this org")
    return _org_config_to_dict(config, domain_name=org.domain_name)


@router.put(
    "/domain-config",
    summary="Upsert the calling org's domain config",
    tags=["domain-config"],
)
async def put_domain_config_endpoint(
    body: DomainConfigUpdate,
    org: Org = Depends(get_current_org),
    org_repo: OrgRepository = Depends(get_org_repo),
    org_config_repo: OrgConfigRepository = Depends(get_org_config_repo),
) -> dict:
    """Upserts the calling org's editorial config and returns the saved
    state. `domain_name` is dispatched to the `orgs` table (it does not
    live in `org_configs`); everything else is merged onto the existing
    `org_configs` row, so unset fields keep their previously stored
    values. Used by the Settings UI to persist editor changes.
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


@router.get(
    "/discovery/topics",
    summary="List Discovery topics for the calling org",
    tags=["discovery-topics"],
)
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
    """Returns clustered story topics surfaced by the Discovery pipeline,
    filtered by the calling org's `org_code`. Supports filtering by
    `category`, `status`, `feed_id`, and a `since` cutoff; pagination via
    `limit`/`offset`. The `sort` query param is one of `last_activity` /
    `first_seen` / `item_count` and drives the order in which topics
    appear in the editor sidebar.
    """
    if sort not in _SORT_KEYS:
        raise HTTPException(status_code=400, detail=f"Invalid sort: {sort}")

    # NOTE: we pull the full set (cap 200) and re-sort in Python because
    # sort keys include derived fields (item_count) we haven't denormalized
    # to SQL yet. Acceptable while orgs have <=200 active topics; beyond
    # that we need item_count on the topic row. See backlog: a future
    # plan should denormalize discovery_topics.item_count.
    rows = await discovery_repo.list_topics_for_ui(
        org_code=org.code,
        categories=category or None,
        statuses=status or None,
        since=since,
        feed_id=feed_id,
        limit=200,
        offset=0,
    )
    # Batch-count stream sources per topic to avoid N+1
    from backend.database import get_db_backend, get_session_maker

    stream_counts: dict[str, int] = {}
    if get_db_backend() == "postgres" and rows:
        import sqlalchemy as _sa

        from backend.db.models import StreamTopic

        topic_ids = [t.id for t in rows]
        _sm = get_session_maker()
        _st = StreamTopic.__table__  # type: ignore[attr-defined]
        async with _sm() as _session:  # type: ignore[union-attr]
            _res = await _session.execute(
                _sa.select(_st.c.topic_id, _sa.func.count().label("cnt"))
                .where(_st.c.topic_id.in_(topic_ids))
                .group_by(_st.c.topic_id)
            )
            for row in _res.all():
                stream_counts[str(row.topic_id)] = row.cnt

    out: list[dict] = []
    for t in rows:
        items = await discovery_repo.list_items_for_topic(topic_id=t.id, org_code=org.code)
        new_count = (
            sum(1 for it in items if it.fetched_at > t.consumed_at)
            if t.consumed_at is not None
            else 0
        )
        entry = _topic_to_json(
            t,
            new_items_since_consume=new_count,
            item_count=len(items),
            feed_hosts=_hosts_from_items(items),
            topic_image_url=_topic_image_from_items(items),
        )
        entry["stream_source_count"] = stream_counts.get(str(t.id), 0)
        out.append(entry)

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


@router.get(
    "/discovery/topics/{topic_id}",
    summary="Get one Discovery topic with its items",
    tags=["discovery-topics"],
)
async def get_discovery_topic(
    topic_id: UUID,
    org: Org = Depends(get_current_org),
    discovery_repo: DiscoveryRepository = Depends(get_discovery_repo),
) -> dict:
    """Returns a single Discovery topic plus every RSS item clustered into
    it, scoped to the calling org's `org_code`. Returns 404 if the topic
    does not exist or belongs to another org. Used by the topic-detail
    drawer in the UI to render the source list before the editor decides
    whether to write an article.
    """
    topic = await discovery_repo.get_topic(topic_id=topic_id, org_code=org.code)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    items = await discovery_repo.list_items_for_topic(topic_id=topic_id, org_code=org.code)
    new_count = sum(
        1 for it in items if topic.consumed_at is not None and it.fetched_at > topic.consumed_at
    )

    # Stream sources linked to this discovery topic
    from sqlmodel import select as sm_select

    from backend.database import get_db_backend, get_session_maker

    stream_sources: list[dict] = []
    if get_db_backend() == "postgres":
        from backend.db.models import StreamSubscription, StreamTopic

        _sm = get_session_maker()
        async with _sm() as _session:  # type: ignore[union-attr]
            _subs_res = await _session.execute(
                sm_select(StreamSubscription).where(StreamSubscription.org_code == org.code)  # type: ignore[arg-type]
            )
            _subs = {s.id: s.name for s in _subs_res.scalars().all()}
            _st_res = await _session.execute(
                sm_select(StreamTopic).where(StreamTopic.topic_id == topic_id)  # type: ignore[arg-type]
            )
            for st in _st_res.scalars().all():
                stream_sources.append({
                    "id": str(st.id),
                    "subscription_id": str(st.subscription_id),
                    "subscription_name": _subs.get(st.subscription_id, ""),
                    "title": st.title,
                    "windows": st.windows,
                })

    return {
        **_topic_to_json(
            topic,
            new_items_since_consume=new_count,
            item_count=len(items),
            feed_hosts=_hosts_from_items(items),
            topic_image_url=_topic_image_from_items(items),
        ),
        "stream_sources": stream_sources,
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


@router.post(
    "/discovery/topics/{topic_id}/dismiss",
    summary="Dismiss a Discovery topic",
    tags=["discovery-topics"],
)
async def dismiss_discovery_topic(
    topic_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    org: Org = Depends(get_current_org),
    discovery_repo: DiscoveryRepository = Depends(get_discovery_repo),
) -> dict:
    """Marks a Discovery topic as `dismissed`, removing it from the
    default editor sidebar (open + resurfaced). The topic and its items
    are kept in the DB so future RSS items will not re-cluster into a
    fresh duplicate; restore via POST /discovery/topics/{topic_id}/restore.
    """
    topic = await discovery_repo.get_topic(topic_id=topic_id, org_code=org.code)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    await discovery_repo.dismiss_topic(topic_id=topic_id, org_code=org.code)
    logfire.info("discovery.topic.dismissed", topic_id=str(topic_id), user_id=user.id)
    return {"id": str(topic_id), "status": "dismissed"}


@router.post(
    "/discovery/topics/{topic_id}/restore",
    summary="Restore a dismissed Discovery topic",
    tags=["discovery-topics"],
)
async def restore_discovery_topic(
    topic_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    org: Org = Depends(get_current_org),
    discovery_repo: DiscoveryRepository = Depends(get_discovery_repo),
) -> dict:
    """Reverses a prior dismissal by flipping the topic's status back to
    `open`, returning it to the default editor sidebar. Use when a topic
    was dismissed by mistake or has become newsworthy again; scoped to
    the calling org's `org_code`.
    """
    topic = await discovery_repo.get_topic(topic_id=topic_id, org_code=org.code)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    await discovery_repo.restore_topic(topic_id=topic_id, org_code=org.code)
    logfire.info(
        "discovery.topic.restored",
        topic_id=str(topic_id),
        user_id=user.id,
        org_code=org.code,
    )
    return {"id": str(topic_id), "status": "open"}


class WriteFromTopicOverrides(BaseModel):
    """Optional overrides supplied from the pre-write dialog. When omitted,
    the article is written using the topic's title + blurb + every item's
    URL — same as the pre-dialog behavior."""

    topic_override: str | None = None
    additional_instructions: str | None = None
    urls: list[str] | None = None


@router.post(
    "/discovery/topics/{topic_id}/write_article",
    status_code=202,
    summary="Write an article from a Discovery topic",
    tags=["discovery-topics"],
)
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
    """Bridges a Discovery topic into the article-generation pipeline,
    using the topic's title + blurb + clustered item URLs as the seed.
    Optional `overrides` from the pre-write dialog can replace the topic,
    instructions, or URL set. Returns 202 immediately; the pipeline runs
    as a background task and the source topic is marked `consumed` once
    the task starts.
    """
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
        # Explicit empty list means "no pre-seeded URLs" — respect that.
        # `None` (not present) is what falls back to all topic items.
        urls = list(overrides.urls)
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

    running_count = await article_repo.count_running_for_org(org.code)
    if running_count >= _MAX_CONCURRENT_RUNNING_PER_ORG:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Org has {running_count} articles currently running "
                f"(cap: {_MAX_CONCURRENT_RUNNING_PER_ORG}). Wait for one to finish."
            ),
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
        article_repo=article_repo,
    )

    return {"topic_id": str(topic_id), "article_id": str(article_id), "status": "running"}


@router.get(
    "/discovery/items",
    summary="List raw Discovery RSS items",
    tags=["discovery-items"],
)
async def list_discovery_items(
    org: Org = Depends(get_current_org),
    discovery_repo: DiscoveryRepository = Depends(get_discovery_repo),
    feed_id: UUID | None = Query(default=None),
    category: list[str] = Query(default_factory=list),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """Returns the raw RSS items ingested for the calling org, before /
    independent of topic clustering. Each item carries its `topic_id` (or
    `None` if not yet clustered). Filterable by `feed_id` and
    `category`; used by the Discovery debug view to inspect what the
    crawler has actually pulled in.
    """
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


@router.get(
    "/discovery/feeds",
    summary="List Discovery RSS feeds with health stats",
    tags=["discovery-feeds"],
)
async def list_discovery_feeds(
    org: Org = Depends(get_current_org),
    discovery_repo: DiscoveryRepository = Depends(get_discovery_repo),
    org_config_repo: OrgConfigRepository = Depends(get_org_config_repo),
) -> list[dict]:
    """Returns each RSS feed configured for the calling org, with runtime
    health (`last_fetched_at`, `last_error`, `error_count`, `disabled`)
    plus a 24-hour ingestion count. Feeds whose URL was removed from the
    org's config are excluded — leftover rows persist for referential
    integrity but do not surface in the UI.
    """
    from datetime import UTC, timedelta

    feeds = await discovery_repo.list_feeds_for_org(org.code)
    # Only show feeds that are still in the domain config. discovery_feeds
    # rows persist after the editor removes a URL from Settings (we don't
    # delete the row because discovery_item_feed links would dangle), but
    # they shouldn't appear in the sidebar anymore.
    domain = await get_domain_config(org.code, org.domain_name, org_config_repo)
    if domain is not None:
        configured_urls = {cfg.url for cfg in domain.discovery_feeds}
        feeds = [f for f in feeds if f.feed_url in configured_urls]

    since = datetime.now(UTC) - timedelta(hours=24)
    out: list[dict] = []
    for f in feeds:
        items_24h = await discovery_repo.count_items_for_feed_since(feed_id=f.id, since=since)
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


@router.post(
    "/discovery/feeds/{feed_id}/reset",
    summary="Reset a Discovery feed's error state",
    tags=["discovery-feeds"],
)
async def reset_discovery_feed(
    feed_id: UUID,
    org: Org = Depends(get_current_org),
    discovery_repo: DiscoveryRepository = Depends(get_discovery_repo),
) -> dict:
    """Clears `error_count` and the `disabled` flag on a feed, allowing
    the scheduler to attempt fetches again. Use after fixing an upstream
    feed issue (URL change, transient outage); 404s if the feed is not
    bound to the calling org.
    """
    feeds = await discovery_repo.list_feeds_for_org(org.code)
    if not any(f.id == feed_id for f in feeds):
        raise HTTPException(status_code=404, detail="Feed not found")
    await discovery_repo.reset_feed_errors(feed_id)
    return {"id": str(feed_id), "error_count": 0, "disabled": False}


@router.get(
    "/discovery/categories",
    summary="List Discovery categories for the calling org",
    tags=["discovery-categories"],
)
async def list_discovery_categories(
    org: Org = Depends(get_current_org),
    org_config_repo: OrgConfigRepository = Depends(get_org_config_repo),
) -> list[dict]:
    """Returns the editor-defined classification tags (name + description)
    that the Discovery classifier uses to label incoming items. Sourced
    from the org's domain config; returns an empty list when the org has
    no config yet. Used to populate the category filter chips above the
    topics list.
    """
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
        "article_templates": config.article_templates,
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
