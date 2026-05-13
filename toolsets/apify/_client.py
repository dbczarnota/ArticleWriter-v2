# toolsets/apify/_client.py
"""Base Apify HTTP client with Logfire observability and cost tracking."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

import httpx
import logfire

from agents._base.run_context import record_apify_run

# Default cost per run (USD) per actor. Override or extend via APIFY_ACTOR_COSTS env var
# (JSON dict), e.g.: {"apify~instagram-scraper": 0.03, "some~new-actor": 0.10}
# Env var values take precedence over defaults below — update ConfigMap, no rebuild needed.
_PRICE_PER_ITEM_DEFAULTS: dict[str, float] = {
    "apify~instagram-scraper": 0.03,
    "apidojo~twitter-scraper-lite": 0.05,
}
_PRICE_PER_ITEM: dict[str, float] = {
    **_PRICE_PER_ITEM_DEFAULTS,
    **json.loads(os.environ.get("APIFY_ACTOR_COSTS", "{}")),
}

_DEFAULT_TIMEOUT = 180.0
_BASE_URL = "https://api.apify.com/v2"


@dataclass
class ApifyResult:
    items: list[dict]
    actor: str
    run_id: str | None
    item_count: int
    estimated_cost_usd: float
    latency_ms: float


class ApifyClient:
    """Thin wrapper around Apify run-sync-get-dataset-items.

    Emits a Logfire span per actor run with item count, estimated cost,
    and latency so every platform (Instagram, X, TikTok, …) is observable
    from one place without duplicating instrumentation.
    """

    def __init__(self, api_token: str, timeout: float = _DEFAULT_TIMEOUT) -> None:
        self._token = api_token
        self._timeout = timeout

    async def run_actor(
        self,
        actor: str,
        input_data: dict,
        *,
        service: str = "",
    ) -> ApifyResult:
        """Run *actor* synchronously and return the dataset items.

        Args:
            actor: Apify actor slug, e.g. ``"apify~instagram-scraper"``.
            input_data: Actor input JSON.
            service: Human label for Logfire (e.g. ``"instagram"``, ``"x"``).
                     Defaults to the actor name.
        """
        service = service or actor
        url = f"{_BASE_URL}/acts/{actor}/run-sync-get-dataset-items"

        with logfire.span(
            "apify.run_actor",
            actor=actor,
            service=service,
        ) as span:
            t0 = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    r = await client.post(
                        url,
                        params={"token": self._token},
                        json=input_data,
                    )
                    r.raise_for_status()
                    items: list[dict] = r.json()
            except Exception as exc:
                latency_ms = (time.monotonic() - t0) * 1000
                logfire.error(
                    "apify.run_actor failed",
                    actor=actor,
                    service=service,
                    error=str(exc),
                    latency_ms=round(latency_ms),
                )
                raise

            latency_ms = (time.monotonic() - t0) * 1000
            item_count = len(items)
            price_per = _PRICE_PER_ITEM.get(actor, 0.0)
            estimated_cost = price_per * max(item_count, 1)

            # Log first item's text fields so Logfire traces show what the actor returned.
            first_text = ""
            if items:
                first = items[0]
                first_text = (
                    first.get("text")
                    or first.get("full_text")
                    or first.get("caption")
                    or first.get("description")
                    or ""
                )

            span.set_attribute("item_count", item_count)
            span.set_attribute("estimated_cost_usd", round(estimated_cost, 6))
            span.set_attribute("latency_ms", round(latency_ms))
            span.set_attribute("first_item_text_preview", first_text[:300])

            logfire.info(
                "apify.run_actor ok",
                actor=actor,
                service=service,
                item_count=item_count,
                estimated_cost_usd=round(estimated_cost, 6),
                latency_ms=round(latency_ms),
                first_item_text_preview=first_text[:300],
            )
            record_apify_run(actor, service, estimated_cost)

            return ApifyResult(
                items=items,
                actor=actor,
                run_id=None,
                item_count=item_count,
                estimated_cost_usd=estimated_cost,
                latency_ms=latency_ms,
            )
