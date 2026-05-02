# backend/api/v2.py
from __future__ import annotations

import dataclasses

from fastapi import APIRouter, Depends, HTTPException

from agents._base.resilient import AllModelsFailedError, InsufficientSourcesError
from agents.pipeline.runner import run_pipeline
from backend.api.schemas import ArticleRequest
from backend.config import AppSettings
from backend.secrets import Secrets, get_secrets
from domains.registry import load_domain

router = APIRouter(prefix="/v2")


@router.post("/write_article")
async def write_article(
    req: ArticleRequest,
    cfg: Secrets = Depends(get_secrets),
) -> dict:
    app_settings = AppSettings.from_request(req)
    try:
        domain = load_domain(app_settings.domain)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=exc.args[0]) from exc
    try:
        result = await run_pipeline(
            req.topic,
            settings=app_settings,
            domain=domain,
            serper_api_key=cfg.serper_api_key,
            jina_api_key=cfg.jina_api_key,
            urls=req.urls or None,
            additional_instructions=req.additional_instructions,
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
