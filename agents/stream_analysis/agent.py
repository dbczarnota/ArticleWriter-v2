from __future__ import annotations

import time
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

2. Wyciągnij tematy informacyjne (topics) z timestampami:
   - start_offset_seconds: kiedy ten temat się zaczyna w tym chunku (liczone od 0).
   - end_offset_seconds: kiedy się kończy (lub null jeśli trwa do końca chunka).
   - Każdy odrębny wątek/rozmowa to osobny temat.

3. Wykryj zmiany tematu/rozmowy (topic_transitions):
   - Zaznacz każde miejsce, gdzie temat wyraźnie się zmienia lub pojawia nowy gość.
   - timestamp_offset_seconds: czas zmiany od początku tego chunka.
   - Opisz krótko co się skończyło i co zaczęło \
(np. "koniec rozmowy o budżecie, nowy gość: ekspert ds. klimatu").
   - Sygnały zmiany: przywitanie nowego gościa, dżingiel przejściowy, \
nagła zmiana prowadzącego lub tematu.

4. Wyciągnij fakty — konkretne twierdzenia o rzeczywistości (daty, liczby, zdarzenia):
   - Przypisz każdy fakt do mówcy (speaker_label).
   - Podaj timestamp_offset_seconds od początku chunka.
   - Przypisz do tematu (topic_title) — użyj dokładnie tego samego tytułu co w topics.

5. Wyciągnij cytaty — dosłowne wypowiedzi warte przytoczenia:
   - Przypisz do mówcy (speaker_label) i tematu (topic_title).

Ignoruj muzykę, dżingle i reklamy jako treść — ale jeśli dżingiel SYGNALIZUJE zmianę \
tematu, zaznacz go jako topic_transition. Nie wymyślaj — operuj wyłącznie na tym co słyszysz.\
"""


class DetectedSpeaker(BaseModel):
    label: str
    description: str


class StreamFact(BaseModel):
    text: str
    speaker_label: str | None = None
    timestamp_offset_seconds: float = 0.0
    topic_title: str | None = None


class StreamQuote(BaseModel):
    text: str
    speaker_label: str | None = None
    context: str | None = None
    topic_title: str | None = None


class StreamTopic(BaseModel):
    title: str
    confidence: float = 1.0
    start_offset_seconds: float = 0.0
    end_offset_seconds: float | None = None


class TopicTransition(BaseModel):
    timestamp_offset_seconds: float
    description: str


class StreamChunkResult(BaseModel):
    speakers: list[DetectedSpeaker] = []
    topics: list[StreamTopic] = []
    facts: list[StreamFact] = []
    quotes: list[StreamQuote] = []
    topic_transitions: list[TopicTransition] = []
    raw_transcript: str = ""


async def run_stream_analysis_agent(
    audio_bytes: bytes,
    chunk_start_seconds: float,
    *,
    config: StreamAnalysisAgentConfig,
) -> StreamChunkResult:
    """Analyze a single audio chunk. Returns StreamChunkResult.
    Soft-fails to empty result on LLM error.
    """
    user_prompt: list[Any] = [
        f"Fragment audio od sekundy {chunk_start_seconds:.0f}. Przeanalizuj:",
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
