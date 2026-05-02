"""Quick e2e test — edit TOPIC and DOMAIN, then: uv run python run.py"""

import asyncio
import os
import sys

import logfire
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

load_dotenv()

_PROMPT_FALSE_POSITIVES = {"cookie", "auth"}  # see backend/main.py for rationale


def _scrub_callback(m: logfire.ScrubMatch):
    if m.pattern_match.group(0).lower() in _PROMPT_FALSE_POSITIVES:
        return m.value
    return None


logfire.configure(
    send_to_logfire="if-token-present",
    service_name="articlewriter-v2-cli",
    console=logfire.ConsoleOptions(min_log_level="warn"),
    scrubbing=logfire.ScrubbingOptions(callback=_scrub_callback),
)
logfire.instrument_pydantic_ai()

TOPIC = "Melania Trump nie wytrzymała przy królu Karolu. Upomniała męża,"
DOMAIN = "styl_fm"

# Optional: paste URLs to scrape in addition to search results
URLS: list[str] = [
    "https://wydarzenia.styl.fm/921530.melania-trump-nie-wytrzymala-przy-krolu-karolu-upomniala-meza-a-ekspertka-ujawnila-jego-bezczelna-odpowiedz"
]

# Optional: extra guidance for the writing agents
ADDITIONAL_INSTRUCTIONS: str | None = None

# Search freshness — leave None to use domain default (styl_fm = qdr:d = last 24h)
# Options: "qdr:h" (hour), "qdr:d" (day), "qdr:w" (week), "qdr:m" (month), "qdr:y" (year)
SEARCH_FRESHNESS: str | None = "qdr:5d"

DEBUG = True  # rich pipeline logs in terminal

OUTPUT_FILE = "output.html"

# Set to your Make.com webhook URL to push the result after generation, or None to skip
MAKE_WEBHOOK_URL: str | None = "https://hook.eu1.make.com/gs74hirsewkmxbvpp15tpgb78ohl4g28"

# Job ID passed to Make.com as "ID" field (matches v1 behaviour)
JOB_ID: str = "test-1"


async def main() -> None:
    from agents._base.config import SearchAgentConfig
    from agents.pipeline.runner import run_pipeline
    from backend.config import AppSettings
    from domains.registry import load_domain

    settings = AppSettings(
        domain=DOMAIN,
        search=SearchAgentConfig(
            max_results=10, num_queries=5, search_freshness=SEARCH_FRESHNESS or "qdr:w"
        ),
    )

    domain = load_domain(DOMAIN)

    serper_key = os.environ["SERPER_API_KEY"]
    jina_key = os.environ.get("JINA_API_KEY")

    print(f"Running pipeline: topic={TOPIC!r}, domain={DOMAIN!r}")
    result = await run_pipeline(
        TOPIC,
        settings=settings,
        domain=domain,
        serper_api_key=serper_key,
        jina_api_key=jina_key,
        urls=URLS or None,
        additional_instructions=ADDITIONAL_INSTRUCTIONS,
        debug=DEBUG,
    )

    agent_models = {
        "search": settings.search.model,
        "scraping_filter": settings.scraping.filter_model,
        "parsing": settings.parsing.model,
        "extraction": settings.extraction.model,
        "adaptive_search": settings.adaptive_search_agent.model,
        "instructions": settings.instructions.model,
        "writer": settings.writer.model,
        "reflection": settings.reflection.model,
        "usage_tracking": settings.usage_tracking.model,
        "followup": settings.followup.model,
    }

    from v1_compat import to_v1_html

    html_out = to_v1_html(result, agent_models=agent_models)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_out)

    print(f"\nHTML saved to {OUTPUT_FILE} ({len(result.html)} chars)")
    print(f"Alternative titles: {result.alternative_titles}")
    print(f"Followup topics:    {result.followup_topics}")
    print(f"Sources ({len(result.sources)}): {result.sources[:3]}")
    if result.embed_candidates:
        from collections import Counter

        counts = Counter(c.source for c in result.embed_candidates)
        print(f"Embed candidates ({len(result.embed_candidates)}): {dict(counts)}")
        for c in result.embed_candidates[:5]:
            print(f"  [{c.source}] {c.title[:60]} — {c.url[:70]}")
    else:
        print("Embed candidates: none found")
    if result.errors:
        print(f"Errors: {result.errors}")

    print(f"\n--- Token usage ({len(result.token_usage)} agent calls) ---")
    total_in = total_out = 0
    for r in result.token_usage:
        print(
            f"  {r['agent']:20s} {r['model']:45s}  in={r['input_tokens']:6d}  out={r['output_tokens']:5d}  {r['duration_ms']:7.0f}ms"
        )
        total_in += r["input_tokens"]
        total_out += r["output_tokens"]
    print(f"  {'TOTAL':20s} {'':45s}  in={total_in:6d}  out={total_out:5d}")

    print("\n--- Timing ---")
    for stage, ms in result.timing.items():
        print(f"  {stage:20s} {ms:8.0f}ms")

    if result.fallback_events:
        print(f"\n--- Fallback events ({len(result.fallback_events)}) ---")
        for e in result.fallback_events:
            print(
                f"  [{e['agent']}] {e['failed_model']} failed: {e['error_type']}: {e['error_message'][:80]}"
            )
    else:
        print("\nFallback events: none (all primary models succeeded)")

    if MAKE_WEBHOOK_URL:
        import httpx

        payload = {"ID": JOB_ID, "article_text": html_out, "topic": TOPIC}
        async with httpx.AsyncClient() as client:
            resp = await client.post(MAKE_WEBHOOK_URL, json=payload, timeout=30)
            resp.raise_for_status()
        print(f"Sent to Make.com → {resp.status_code}")


asyncio.run(main())
