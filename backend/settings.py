# backend/settings.py
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    serper_api_key: str
    jina_api_key: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    serper_key = os.environ.get("SERPER_API_KEY", "")
    if not serper_key:
        raise RuntimeError("SERPER_API_KEY environment variable is required")
    return Settings(
        serper_api_key=serper_key,
        jina_api_key=os.environ.get("JINA_API_KEY") or None,
    )
