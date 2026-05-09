from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent

from agents._base.resilient import run_with_fallback
from agents._base.run_context import record_agent_call
from agents.stream_digest.config import StreamDigestAgentConfig

_SYSTEM_PROMPT = """\
Jesteś redaktorem analizującym transkrypcje polskiego radia informacyjnego.

Otrzymujesz dwa rodzaje danych:
1. POPRZEDNIE DIGESRY — wyniki poprzednich przebiegów tego agenta (do zaktualizowania).
2. NOWE CHUNKI — świeże fragmenty audio (~10 minut) z częściową analizą.

## Kluczowa zasada: granulacja tematów

ŁĄCZ tematy gdy:
- To jest ta sama rozmowa/wywiad toczący się przez kilka chunków lub digestów \
  (nawet jeśli wcześniej były jako oddzielne tematy — scal je w jeden).
- Ci sami rozmówcy kontynuują dyskusję na ten sam wątek.
- Nowy chunk to bezpośrednia kontynuacja tematu z poprzedniego digestu.

ROZDZIELAJ tematy gdy:
- To serwis informacyjny / wiadomości: każda odrębna wiadomość to osobny temat, \
  nawet jeśli lektor jest ten sam.
- Temat wyraźnie się zmienia — inni rozmówcy, inny kontekst, brak ciągłości narracji.
- Nowy wywiad zaczyna się od nowa (nowe przywitanie, nowy gość).

Heurystyki pomocnicze:
- Jeden prowadzący + jeden gość przez wiele chunków → prawie zawsze jeden temat.
- Lektor czyta kolejne wiadomości bez rozmówców → każda wiadomość to osobny temat.
- Wiele chunków z tym samym tytułem w poprzednich digestach → zdecydowanie scal.

## Pozostałe zadania

1. Przejrzyj poprzednie digesry i nowe chunki razem jako całość.
2. Zwróć KOMPLETNĄ, zaktualizowaną listę tematów — zarówno starych (zmodyfikowanych/uzupełnionych) \
   jak i nowych. Możesz:
   - Zaktualizować lub rozbudować istniejący temat o nowe fakty/cytaty.
   - Połączyć kilka poprzednich tematów jeśli to ta sama ciągła rozmowa.
   - Dodać nowy temat z nowych chunków.
   - Usunąć temat, który okazał się reklamą/dżinglem.
3. Identyfikacja rozmówców — priorytet:
   - Jeśli gdziekolwiek (stary digest lub nowy chunk) pojawia się imię i nazwisko osoby, \
     użyj go wszędzie gdzie ta osoba się pojawia.
   - Przykład: jeśli wcześniej była "prezenterka", a teraz usłyszałeś "Karolina Lewicka" — \
     zaktualizuj jej opis we wszystkich tematach.
   - Dodaj tytuł/rolę jeśli znana (np. "Karolina Lewicka, prezenterka TOK FM").
4. Dla każdego tematu:
   - Zwięzły, dziennikarski tytuł.
   - Lista zidentyfikowanych rozmówców z pełnymi danymi.
   - Fakty zebrane ze wszystkich chunków i digestów dotyczące tego tematu.
   - Najlepsze cytaty (dosłowne).
   - 2-3 zdaniowe streszczenie.
5. Ignoruj reklamy, dżingle i muzykę — nie włączaj ich do tematów.
6. Nie wymyślaj — operuj wyłącznie na dostarczonych danych.
7. Jeśli cały materiał to muzyka/reklamy, zwróć pustą listę stories.\
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
    topic_transitions: list[dict] = field(default_factory=list)


def _format_chunks(chunks: list[ChunkSummary]) -> str:
    parts: list[str] = []
    for c in chunks:
        speakers_txt = ", ".join(f"{s['label']}: {s['description']}" for s in c.speakers) or "brak"
        facts_txt = "\n".join(f"  - {f['text']}" for f in c.facts) or "  brak"
        quotes_txt = "\n".join(
            f'  "{q["text"]}"' + (f" [{q['speaker_label']}]" if q.get("speaker_label") else "")
            for q in c.quotes
        ) or "  brak"
        transitions_txt = (
            "\n".join(
                f"  [{c.chunk_start + t['timestamp_offset_seconds']:.0f}s] {t['description']}"
                for t in c.topic_transitions
            )
            or "  brak"
        )
        parts.append(
            f"--- Chunk {c.chunk_start:.0f}s–{c.chunk_end:.0f}s ---\n"
            f"Transkrypcja: {c.raw_transcript or '(brak)'}\n"
            f"Mówcy: {speakers_txt}\n"
            f"Zmiany tematu:\n{transitions_txt}\n"
            f"Fakty:\n{facts_txt}\n"
            f"Cytaty:\n{quotes_txt}"
        )
    return "\n\n".join(parts)


def _format_previous_digests(digests: list[StreamDigestResult]) -> str:
    if not digests:
        return "(brak poprzednich digestów)"
    parts: list[str] = []
    for i, d in enumerate(digests, 1):
        stories_txt: list[str] = []
        for s in d.stories:
            speakers = ", ".join(sp.name_or_role for sp in s.speakers) or "nieznani"
            facts = "\n".join(f"    - {f.text}" for f in s.facts) or "    brak"
            quotes = "\n".join(
                f'    "{q.text}"' + (f" [{q.speaker}]" if q.speaker else "")
                for q in s.quotes
            ) or "    brak"
            stories_txt.append(
                f"  Temat: {s.title}\n"
                f"  Czas: {s.start_seconds:.0f}s–{s.end_seconds:.0f}s\n"
                f"  Rozmówcy: {speakers}\n"
                f"  Streszczenie: {s.summary or '(brak)'}\n"
                f"  Fakty:\n{facts}\n"
                f"  Cytaty:\n{quotes}"
            )
        digest_block = "\n\n".join(stories_txt) or "  (brak tematów — muzyka/reklamy)"
        parts.append(
            f"[Digest {i}: {d.window_start_seconds:.0f}s–{d.window_end_seconds:.0f}s]\n"
            + digest_block
        )
    return "\n\n".join(parts)


async def run_stream_digest_agent(
    chunks: list[ChunkSummary],
    *,
    config: StreamDigestAgentConfig,
    previous_digests: list[StreamDigestResult] | None = None,
) -> StreamDigestResult:
    """Aggregate N chunks into a digest of stories, optionally updating previous digests."""
    if not chunks and not previous_digests:
        return StreamDigestResult()

    prev = previous_digests or []
    window_start = prev[0].window_start_seconds if prev else (chunks[0].chunk_start if chunks else 0.0)
    window_end = chunks[-1].chunk_end if chunks else (prev[-1].window_end_seconds if prev else 0.0)

    prev_section = _format_previous_digests(prev)
    chunks_section = _format_chunks(chunks) if chunks else "(brak nowych chunków)"

    user_prompt = (
        f"=== POPRZEDNIE DIGESRY (do zaktualizowania) ===\n\n"
        f"{prev_section}\n\n"
        f"=== NOWE CHUNKI DO PRZEANALIZOWANIA ({len(chunks)} chunków, "
        f"{window_start:.0f}s–{window_end:.0f}s) ===\n\n"
        f"{chunks_section}"
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
