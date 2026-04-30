from __future__ import annotations
from pydantic import BaseModel


class ArticleRequest(BaseModel):
    id: str
    topic: str
    domain: str = "styl_fm"
    urls: list[str] = []
    domains_filter: list[str] = []
    agents: dict[str, dict] = {}
    pipeline: dict[str, bool] = {}
    additional_instructions: str | None = None
