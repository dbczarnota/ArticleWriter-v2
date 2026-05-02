# backend/main.py
import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.v2 import router as v2_router

_PROMPT_FALSE_POSITIVES = {
    "cookie",  # parser prompt: "remove cookie banners"
    "auth",  # filter prompt: "AUTHORITY — established outlets..." / "authoritative"
}


def _scrub_callback(m: logfire.ScrubMatch):
    # Whitelist words that appear in legitimate prompt content. password/token/secret/
    # credentials/api_key/etc. stay scrubbed by default.
    if m.pattern_match.group(0).lower() in _PROMPT_FALSE_POSITIVES:
        return m.value
    return None


logfire.configure(
    send_to_logfire="if-token-present",
    service_name="articlewriter-v2",
    console=logfire.ConsoleOptions(min_log_level="warn"),
    scrubbing=logfire.ScrubbingOptions(callback=_scrub_callback),
)
logfire.instrument_pydantic_ai()

app = FastAPI(title="ArticleWriter v2", version="2.0")
logfire.instrument_fastapi(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v2_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
