from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent

from agents._base.resilient import run_with_fallback
from agents._base.run_context import record_agent_call
from agents.stream_digest.config import StreamDigestAgentConfig

_SYSTEM_PROMPT = """\
Jesteś redaktorem analizującym transkrypcje polskiego radia informacyjnego.
Otrzymujesz zestaw fragmentów audio (chunków) z ~10 minut jednej audycji, \
każdy z częściową analizą (mówcy, tematy, fakty, cytaty z poprzedniego etapu).

Twoje zadanie:
1. Zidentyfikuj odrębne tematy/wiadomości omawiane w tym oknie czasowym \
   (zwykle 2-4 tematy na 10 minut).
2. Dla każdego tematu:
   - Nadaj mu zwięzły, dziennikarski tytuł (jak nagłówek artykułu).
   - Zidentyfikuj rozmówców — użyj prawdziwych imion i nazwisk jeśli padły \
     (np. "dr Marcin Borchardt, reżyser"), inaczej opisz rolę \
     (np. "prezenterka", "ekspert ds. cyfryzacji").
   - Zbierz fakty z różnych chunków dotyczące tego tematu.
   - Wybierz najlepsze cytaty (dosłowne, warte przytoczenia).
   - Napisz 2-3 zdaniowe streszczenie tego co powiedziano.
3. Ignoruj reklamy, dżingle, jingle stacji — nie włączaj ich do tematów.
4. Nie wymyślaj — operuj wyłącznie na dostarczonych transkrypcjach.
5. Jeśli cały materiał to muzyka/reklamy, zwróć pustą listę stories.\
"""


class DigestSpeaker(BaseModel):
    name_or_role: str
    description: str | None = None


class DigestFact(BaseModel):
    text: str
    speaker: str | None = None
    chunk_start_seconds: float = 0.0


class DigestQuote(BaseModel):
    text: str
    speaker: str | None = None


class DigestStory(BaseModel):
    title: str
    start_seconds: float
    end_seconds: float
    speakers: list[DigestSpeaker] = []
    facts: list[DigestFact] = []
    quotes: list[DigestQuote] = []
    summary: str = ""


class StreamDigestResult(BaseModel):
    stories: list[DigestStory] = []
    window_start_seconds: float = 0.0
    window_end_seconds: float = 0.0


@dataclass
class ChunkSummary:
    chunk_start: float
    chunk_end: float
    raw_transcript: str
    speakers: list[dict]
    topics: list[dict]
    facts: list[dict]
    quotes: list[dict]


def _format_chunks(chunks: list[ChunkSummary]) -> str:
    parts: list[str] = []
    for c in chunks:
        speakers_txt = ", ".join(f"{s['label']}: {s['description']}" for s in c.speakers) or "brak"
        facts_txt = "\n".join(f"  - {f['text']}" for f in c.facts) or "  brak"
        quotes_txt = "\n".join(f'  "{q["text"]}"' for q in c.quotes) or "  brak"
        parts.append(
            f"--- Chunk {c.chunk_start:.0f}s–{c.chunk_end:.0f}s ---\n"
            f"Transkrypcja: {c.raw_transcript or '(brak)'}\n"
            f"Mówcy: {speakers_txt}\n"
            f"Fakty:\n{facts_txt}\n"
            f"Cytaty:\n{quotes_txt}"
        )
    return "\n\n".join(parts)


async def run_stream_digest_agent(
    chunks: list[ChunkSummary],
    *,
    config: StreamDigestAgentConfig,
) -> StreamDigestResult:
    """Aggregate N chunks into a digest of stories. Soft-fails to empty result."""
    if not chunks:
        return StreamDigestResult()

    window_start = chunks[0].chunk_start
    window_end = chunks[-1].chunk_end
    formatted = _format_chunks(chunks)
    user_prompt = (
        f"Oto {len(chunks)} chunków z przedziału "
        f"{window_start:.0f}s–{window_end:.0f}s. Przeanalizuj:\n\n{formatted}"
    )

    def _factory(model: str) -> tuple[Agent[Any, Any], str]:
        return Agent(model, output_type=StreamDigestResult), _SYSTEM_PROMPT

    t0 = time.perf_counter()
    try:
        result, model_used = await run_with_fallback(
            (config.model, *config.fallback_models),
            agent_factory=_factory,
            user_prompt=user_prompt,
            agent_name="stream_digest",
        )
    except Exception:
        return StreamDigestResult(
            window_start_seconds=window_start,
            window_end_seconds=window_end,
        )

    u = result.usage()
    record_agent_call(
        "stream_digest",
        model_used,
        u.input_tokens or 0,
        u.output_tokens or 0,
        (time.perf_counter() - t0) * 1000,
    )
    out = result.output
    out.window_start_seconds = window_start
    out.window_end_seconds = window_end
    return out
