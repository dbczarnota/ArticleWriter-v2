"""Quick e2e test — edit TOPIC and DOMAIN, then: uv run python run.py"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

TOPIC = "Melania Trump nie wytrzymała przy królu Karolu. Upomniała męża,"
DOMAIN = "styl_fm"

# Optional: paste URLs to scrape in addition to search results
URLS: list[str] = ["https://wydarzenia.styl.fm/921530.melania-trump-nie-wytrzymala-przy-krolu-karolu-upomniala-meza-a-ekspertka-ujawnila-jego-bezczelna-odpowiedz"]

# Optional: extra guidance for the writing agents
ADDITIONAL_INSTRUCTIONS: str | None = None

# Search freshness — leave None to use domain default (styl_fm = qdr:d = last 24h)
# Options: "qdr:h" (hour), "qdr:d" (day), "qdr:w" (week), "qdr:m" (month), "qdr:y" (year)
SEARCH_FRESHNESS: str | None = None

OUTPUT_FILE = "output.html"

# Set to your Make.com webhook URL to push the result after generation, or None to skip
MAKE_WEBHOOK_URL: str | None = "https://hook.eu1.make.com/gs74hirsewkmxbvpp15tpgb78ohl4g28"

# Job ID passed to Make.com as "ID" field (matches v1 behaviour)
JOB_ID: str = "test-1"


async def main() -> None:
    from backend.config import AppSettings
    from domains.registry import load_domain
    from agents.pipeline.runner import run_pipeline

    from agents._base.config import SearchAgentConfig
    search_cfg = SearchAgentConfig(search_freshness=SEARCH_FRESHNESS) if SEARCH_FRESHNESS else SearchAgentConfig()
    settings = AppSettings(domain=DOMAIN, search=search_cfg)
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
    )

    agent_models = {
        "search":         settings.search.model,
        "scraping_filter": settings.scraping.filter_model,
        "parsing":        settings.parsing.model,
        "extraction":     settings.extraction.model,
        "adaptive_search": settings.adaptive_search_agent.model,
        "instructions":   settings.instructions.model,
        "writer":         settings.writer.model,
        "reflection":     settings.reflection.model,
        "usage_tracking": settings.usage_tracking.model,
        "followup":       settings.followup.model,
    }

    from v1_compat import to_v1_html
    html_out = to_v1_html(result, agent_models=agent_models)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_out)

    print(f"\nHTML saved to {OUTPUT_FILE} ({len(result.html)} chars)")
    print(f"Alternative titles: {result.alternative_titles}")
    print(f"Followup topics:    {result.followup_topics}")
    print(f"Sources ({len(result.sources)}): {result.sources[:3]}")
    if result.errors:
        print(f"Errors: {result.errors}")

    if MAKE_WEBHOOK_URL:
        import httpx
        payload = {"ID": JOB_ID, "article_text": html_out, "topic": TOPIC}
        async with httpx.AsyncClient() as client:
            resp = await client.post(MAKE_WEBHOOK_URL, json=payload, timeout=30)
            resp.raise_for_status()
        print(f"Sent to Make.com → {resp.status_code}")


asyncio.run(main())
