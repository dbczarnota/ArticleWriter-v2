# backend/main.py
import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.v2 import router as v2_router


def _scrub_callback(m: logfire.ScrubMatch):
    # The parser prompt mentions "cookie banners" which trips the default cookie scrubber.
    # Allow the literal substring "cookie" through; password/token/secret/etc. stay scrubbed.
    if m.pattern_match.group(0).lower() == "cookie":
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
