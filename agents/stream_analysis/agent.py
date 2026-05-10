from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent, BinaryContent

from agents._base.resilient import run_with_fallback
from agents._base.run_context import record_agent_call
from agents.stream_analysis.config import StreamAnalysisAgentConfig

_SYSTEM_PROMPT = """\
Jesteś analizatorem treści radiowych i telewizyjnych. Otrzymujesz fragment audio \
ze streamu informacyjnego (ok. 2 minuty).

Twoje zadania:
1. Zidentyfikuj wszystkich mówców — opisz każdego krótko na podstawie głosu i kontekstu \
(np. "kobieta, prezenterka", "mężczyzna, gość studia, polityk").

2. Wyciągnij tematy informacyjne. Każdy temat to jeden spójny wątek/rozmowa i zawiera:
   - title: zwięzły tytuł
   - confidence: pewność (0.0–1.0)
   - start_offset_seconds: od kiedy temat zaczyna się w tym chunku (od 0)
   - end_offset_seconds: do kiedy (null = do końca chunka)
   - facts: lista faktów TYLKO dotyczących tego tematu
   - quotes: lista cytatów TYLKO dotyczących tego tematu

   Każdy fakt zawiera:
   - text: treść faktu
   - speaker_label: kto powiedział (label z listy mówców)
   - timestamp_offset_seconds: kiedy padło (od początku chunka)

   Każdy cytat zawiera:
   - text: dosłowna wypowiedź
   - speaker_label: kto powiedział

   Cytaty — zasada: cytuj TYLKO gości, ekspertów, polityków, rozmówców — NIE cytuj \
prowadzących/prezenterów. Pytania prowadzącego to nie cytat — to kontekst rozmowy.

3. Wykryj zmiany tematu/rozmowy (topic_transitions):
   - timestamp_offset_seconds: kiedy nastąpiła zmiana (od początku chunka)
   - description: co się skończyło i co zaczęło \
(np. "koniec wywiadu z ekspertem ds. klimatu, nowy serwis informacyjny")
   - Sygnały: przywitanie nowego gościa, dżingiel przejściowy, zmiana prowadzącego.

Ważne:
- Fakty i cytaty muszą być zagnieżdżone w konkretnym temacie — nie ma osobnej listy globalnej.
- Muzyka i piosenki: NIE transkrybuj tekstu piosenek. Jeśli chunk zawiera muzykę, \
  raw_transcript zostaw pusty lub wpisz tylko słowa mówione (zapowiedzi, komentarze lektora). \
  Piosenka to nie jest treść mówiona — traktuj ją jak ciszę.
- Reklamy: podobnie — nie transkrybuj tekstu reklam. Dżingiel sygnalizujący zmianę tematu \
  wpisz jako topic_transition, ale samej treści reklamowej nie przepisuj.
- Nie wymyślaj — tylko to co słyszysz.\
"""


class TopicFact(BaseModel):
    text: str
    speaker_label: str | None = None
    timestamp_offset_seconds: float = 0.0


class TopicQuote(BaseModel):
    text: str
    speaker_label: str | None = None


class DetectedSpeaker(BaseModel):
    label: str
    description: str


class StreamTopic(BaseModel):
    title: str
    confidence: float = 1.0
    start_offset_seconds: float = 0.0
    end_offset_seconds: float | None = None
    facts: list[TopicFact] = []
    quotes: list[TopicQuote] = []


class TopicTransition(BaseModel):
    timestamp_offset_seconds: float
    description: str


class StreamChunkResult(BaseModel):
    speakers: list[DetectedSpeaker] = []
    topics: list[StreamTopic] = []
    topic_transitions: list[TopicTransition] = []
    raw_transcript: str = ""


async def run_stream_analysis_agent(
    audio_bytes: bytes,
    chunk_start_seconds: float,
    *,
    chunk_start_at: datetime,
    program_name: str | None = None,
    config: StreamAnalysisAgentConfig,
) -> StreamChunkResult:
    """Analyze a single audio chunk. Returns StreamChunkResult. Soft-fails to empty result."""
    clock_str = chunk_start_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    program_str = f" | Program: {program_name}" if program_name else ""
    user_prompt: list[Any] = [
        f"Fragment audio: {clock_str}{program_str} (sekunda {chunk_start_seconds:.0f} od początku nasłuchu). Przeanalizuj:",
        BinaryContent(data=audio_bytes, media_type="audio/mp3"),
    ]

    def _factory(model: str) -> tuple[Agent[Any, Any], str]:
        return Agent(model, output_type=StreamChunkResult), _SYSTEM_PROMPT

    t0 = time.perf_counter()
    try:
        result, model_used = await run_with_fallback(
            (config.model, *config.fallback_models),
            agent_factory=_factory,
            user_prompt=user_prompt,
            agent_name="stream_analysis",
        )
    except Exception:
        return StreamChunkResult()

    u = result.usage()
    record_agent_call(
        "stream_analysis",
        model_used,
        u.input_tokens or 0,
        u.output_tokens or 0,
        (time.perf_counter() - t0) * 1000,
    )
    return result.output
