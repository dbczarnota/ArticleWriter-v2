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

Otrzymujesz trzy rodzaje danych:
1. ZNANE TEMATY Z OSTATNICH GODZIN — pamięć długoterminowa (tematy z ostatnich 6h, z ID).
2. POPRZEDNIE DIGESRY — wyniki ostatnich przebiegów tego agenta (szczegółowe).
3. NOWE CHUNKI — świeże fragmenty audio (~10 minut) z częściową analizą.

Traktuj ZNANE TEMATY jako punkt wyjścia — jeśli nowy materiał dotyczy już istniejącego \
tematu, zaktualizuj go zamiast tworzyć nowy. Jeśli nie ma historii, zacznij od zera.

## Kluczowa zasada: selekcja tematów newsowych

Twoim głównym zadaniem jest wyciąganie **tematów newsowych** — wiadomości, które mogłyby \
trafić na portal informacyjny. Każdy temat oznacz polem `is_news`.

`is_news: true` — temat newsowy:
- Konkretne wydarzenie polityczne, gospodarcze, społeczne, zagraniczne, kryminalne.
- Informacja o decyzji, wypadku, zmianie prawa, wyniku wyborów, proteście, katastrofie itp.
- Wywiad z ekspertem na temat aktualnego wydarzenia lub problemu społecznego.

`is_news: false` — temat NIE jest newsowy:
- Rozmowa filozoficzna, moralizatorska, ogólna refleksja bez zakorzenienia w bieżących \
  wydarzeniach (np. ogólne rozważania o etyce, wartościach, stylu życia).
- Poradnikowe treści lifestyle, zdrowie, kultura osobista.
- Promocja książki/produktu bez newsa w tle.
- Muzyka, dżingle, reklamy — tych w ogóle nie dodawaj.

Zwróć wszystkie tematy (zarówno `is_news: true` jak i `false`) — redaktor zdecyduje co \
opublikować. Ale skup się na newsach — jeśli treść jest niejednoznaczna, oznacz `is_news: false`.

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
   - `is_news: true/false` zgodnie z definicją powyżej.
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
    is_news: bool = True
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
    # topics now contain nested facts and quotes
    topics: list[dict]
    topic_transitions: list[dict] = field(default_factory=list)


@dataclass
class TopicContext:
    """Snapshot of a StreamTopic row — passed as long-term memory to the digest agent."""

    topic_id: str
    title: str
    is_news: bool
    first_seen_at: str
    last_seen_at: str
    summary: str
    speakers: list[dict] = field(default_factory=list)
    facts: list[dict] = field(default_factory=list)
    quotes: list[dict] = field(default_factory=list)
    window_start_seconds: float = 0.0
    window_end_seconds: float = 0.0


def _format_topic(topic: dict, chunk_start: float) -> str:
    abs_start = chunk_start + topic.get("start_offset_seconds", 0)
    abs_end_raw = topic.get("end_offset_seconds")
    abs_end = chunk_start + abs_end_raw if abs_end_raw is not None else None
    time_range = f"{abs_start:.0f}s–{abs_end:.0f}s" if abs_end is not None else f"{abs_start:.0f}s–"
    lines = [f"  Temat: {topic['title']} [{time_range}]"]
    for f in topic.get("facts", []):
        who = f" [{f['speaker_label']}]" if f.get("speaker_label") else ""
        ts = f" @{chunk_start + f.get('timestamp_offset_seconds', 0):.0f}s"
        lines.append(f"    Fakt: {f['text']}{who}{ts}")
    for q in topic.get("quotes", []):
        who = f" [{q['speaker_label']}]" if q.get("speaker_label") else ""
        lines.append(f'    Cytat: "{q["text"]}"{who}')
    return "\n".join(lines)


def _format_chunks(chunks: list[ChunkSummary]) -> str:
    parts: list[str] = []
    for c in chunks:
        speakers_txt = ", ".join(f"{s['label']}: {s['description']}" for s in c.speakers) or "brak"
        transitions_txt = (
            "\n".join(
                f"  [{c.chunk_start + t['timestamp_offset_seconds']:.0f}s] {t['description']}"
                for t in c.topic_transitions
            )
            or "  brak"
        )
        topics_txt = "\n".join(_format_topic(t, c.chunk_start) for t in c.topics) or "  (brak)"
        parts.append(
            f"--- Chunk {c.chunk_start:.0f}s–{c.chunk_end:.0f}s ---\n"
            f"Transkrypcja: {c.raw_transcript or '(brak)'}\n"
            f"Mówcy: {speakers_txt}\n"
            f"Zmiany tematu:\n{transitions_txt}\n"
            f"Tematy (z faktami i cytatami):\n{topics_txt}"
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
            quotes = (
                "\n".join(
                    f'    "{q.text}"' + (f" [{q.speaker}]" if q.speaker else "") for q in s.quotes
                )
                or "    brak"
            )
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


def _format_historical_topics(topics: list[TopicContext]) -> str:
    if not topics:
        return "(brak tematów z ostatnich godzin)"
    parts: list[str] = []
    for t in topics:
        news_flag = "📰 NEWS" if t.is_news else "💬 nie-news"
        speakers = ", ".join(sp.get("name_or_role", "?") for sp in t.speakers) or "nieznani"
        facts = "\n".join(f"    - {f.get('text', '')}" for f in t.facts) or "    brak"
        quotes = (
            "\n".join(
                f'    "{q.get("text", "")}"'
                + (f" [{q.get('speaker', '')}]" if q.get("speaker") else "")
                for q in t.quotes
            )
            or "    brak"
        )
        parts.append(
            f"  [{news_flag}] Temat: {t.title} [ID: {t.topic_id}]\n"
            f"  Czas w strumieniu: {t.window_start_seconds:.0f}s – {t.window_end_seconds:.0f}s\n"
            f"  Pierwsze pojawienie: {t.first_seen_at} | Ostatnie: {t.last_seen_at}\n"
            f"  Rozmówcy: {speakers}\n"
            f"  Streszczenie: {t.summary or '(brak)'}\n"
            f"  Fakty:\n{facts}\n"
            f"  Cytaty:\n{quotes}"
        )
    return "\n\n".join(parts)


async def run_stream_digest_agent(
    chunks: list[ChunkSummary],
    *,
    config: StreamDigestAgentConfig,
    previous_digests: list[StreamDigestResult] | None = None,
    historical_topics: list[TopicContext] | None = None,
) -> StreamDigestResult:
    """Aggregate N chunks into a digest of stories, optionally updating previous digests."""
    if not chunks and not previous_digests and not historical_topics:
        return StreamDigestResult()

    prev = previous_digests or []
    window_start = (
        prev[0].window_start_seconds if prev else (chunks[0].chunk_start if chunks else 0.0)
    )
    window_end = chunks[-1].chunk_end if chunks else (prev[-1].window_end_seconds if prev else 0.0)

    hist_section = _format_historical_topics(historical_topics or [])
    prev_section = _format_previous_digests(prev)
    chunks_section = _format_chunks(chunks) if chunks else "(brak nowych chunków)"

    user_prompt = (
        f"=== ZNANE TEMATY Z OSTATNICH GODZIN (pamięć długoterminowa) ===\n\n"
        f"{hist_section}\n\n"
        f"=== POPRZEDNIE DIGESRY (ostatnie przebiegi) ===\n\n"
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
