# backend/secrets.py
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Secrets:
    serper_api_key: str
    jina_api_key: str | None = None
    apify_api_token: str | None = None


@lru_cache(maxsize=1)
def get_secrets() -> Secrets:
    serper_key = os.environ.get("SERPER_API_KEY", "")
    if not serper_key:
        raise RuntimeError("SERPER_API_KEY environment variable is required")
    return Secrets(
        serper_api_key=serper_key,
        jina_api_key=os.environ.get("JINA_API_KEY") or None,
        apify_api_token=os.environ.get("APIFY_API_TOKEN") or None,
    )
