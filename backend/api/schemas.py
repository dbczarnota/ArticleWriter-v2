from __future__ import annotations
from pydantic import BaseModel, field_validator


class ArticleRequest(BaseModel):
    id: str
    topic: str
    domain: str = "styl_fm"
    urls: list[str] = []
    domains_filter: list[str] = []
    agents: dict[str, dict] = {}
    pipeline: dict[str, bool] = {}
    additional_instructions: str | None = None

    @field_validator("topic", mode="before")
    @classmethod
    def _validate_topic(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("topic must not be empty")
        if len(v) > 300:
            raise ValueError("topic must be at most 300 characters")
        return v

    @field_validator("additional_instructions", mode="before")
    @classmethod
    def _validate_additional_instructions(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if len(v) > 2000:
            raise ValueError("additional_instructions must be at most 2000 characters")
        return v
