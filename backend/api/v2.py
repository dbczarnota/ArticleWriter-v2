# backend/api/v2.py
from __future__ import annotations
import dataclasses
from fastapi import APIRouter, Depends, HTTPException
from agents.pipeline.runner import run_pipeline
from backend.api.schemas import ArticleRequest
from backend.config import AppSettings
from backend.settings import Settings, get_settings
from domains.registry import load_domain

router = APIRouter(prefix="/v2")


@router.post("/write_article")
async def write_article(
    req: ArticleRequest,
    cfg: Settings = Depends(get_settings),
) -> dict:
    app_settings = AppSettings.from_request(req)
    try:
        domain = load_domain(app_settings.domain)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=exc.args[0])
    result = await run_pipeline(
        req.topic,
        settings=app_settings,
        domain=domain,
        serper_api_key=cfg.serper_api_key,
        jina_api_key=cfg.jina_api_key,
        urls=req.urls or None,
        additional_instructions=req.additional_instructions,
    )
    return dataclasses.asdict(result)
