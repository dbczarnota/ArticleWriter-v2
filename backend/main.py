# backend/main.py
import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.v2 import router as v2_router

logfire.configure(
    send_to_logfire="if-token-present",
    service_name="articlewriter-v2",
    console=logfire.ConsoleOptions(min_log_level="warn"),
)
logfire.instrument_pydantic_ai()

app = FastAPI(title="ArticleWriter v2", version="2.0")
logfire.instrument_fastapi(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v2_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
