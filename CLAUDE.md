# ArticleWriter-v2 — Project Context

## Co to jest

System do automatycznego generowania artykułów prasowych oparty na wieloagentowym pipeline'ie (pydantic-ai). Wejście: temat + konfiguracja domeny. Wyjście: gotowy artykuł HTML + alternatywne tytuły + tematy powiązane.

Aktualnie działa jako produkcja dla **Styl.fm** (clickbait/lifestyle). Po refaktorze będzie niezależny od domeny — jeden silnik, wiele konfiguracji redakcyjnych.

## Stack

- **Backend**: Python 3.12, FastAPI, pydantic-ai (`agent.iter()`), pydantic-graph (zastępowane)
- **LLM**: Google Gemini (primary), OpenAI GPT, Groq, OpenRouter
- **Search**: Serper.dev (Google SERP, URL + snippet)
- **Scraping tier-1**: httpx + trafilatura (statyczny HTML)
- **Scraping tier-2**: Jina Reader r.jina.ai (managed headless, 500 RPM free z API key)
- **Scraping tier-3**: Firecrawl — placeholder, nie implementujemy na start
- **Rate limiting**: globalny `asyncio.Semaphore` dla Jiny (proces-level singleton, dzielony między userami)
- **Auth**: Kinde (OIDC JWT) — wzorzec z prawnik-ai-v2
- **Observability**: Logfire (OTEL metrics + spans)
- **Testy**: pytest + pytest-asyncio + respx

## Wzorce — kopiujemy z prawnik-ai-v2

Repo referencyjna: `C:\Users\czarn\Documents\A_PYTHON\prawnik-ai-v2`

- Protocol-based swappable auth (`NullAuthenticator` → `KindeAuthenticator`)
- Frozen dataclasses + `dataclasses.replace()` dla konfiguracji
- Per-agent `config.py` składane w `AppSettings`
- `agent.iter()` z budget enforcement; messages przekazywane między agentami
- Toolsets jako `FunctionToolset` factories
- Jinja2 dla promptów z warunkowymi sekcjami
- Logfire: `@logfire.instrument` + OTEL metrics
- `SubagentBus` (asyncio.Queue) dla SSE streaming

## Separacja silnika od domeny

Kluczowa zasada architektoniczna: **engine ≠ domain**.

- **Silnik** (`agents/`, `toolsets/`) — agnostic, wielokrotnego użytku
- **Domena** (`domains/{nazwa}/`) — `domain_config.py` + `guidelines.md` + example artykuły

Przykład: `domains/styl_fm/` vs `domains/the_economist/`

## Struktura katalogów (docelowa)

```
backend/
  main.py, config.py, paths.py
  auth/           — protocols, kinde, null, deps
  api/            — routery FastAPI
  services/       — session, metrics, settings

agents/
  _base/          — AgentConfig, SSEEvent, SubagentBus
  search/         — SearchAgent (Tavily queries)
  scraping/       — ScrapingAgent (Crawl4AI)
  parsing/        — ParsingAgent (content classification)
  extraction/     — ExtractionAgent (facts, quotes, keywords)
  instructions/   — InstructionsAgent (writing brief)
  writer/         — WriterAgent (article HTML)
  reflection/     — ReflectionAgent (QA review)
  followup/       — FollowUpAgent (titles, related topics)

domains/
  _base/          — DomainConfig protocol
  styl_fm/        — config, guidelines, example articles
  [kolejne...]

toolsets/
  search/         — Tavily toolset
  scraping/       — Crawl4AI toolset

tests/
  conftest.py, auth/, agents/, api/
```

## Env vars

```
GEMINI_API_KEY
OPENAI_API_KEY        (opcjonalnie)
GROQ_API_KEY          (opcjonalnie)
OPENROUTER_API_KEY    (opcjonalnie)
SERPER_API_KEY
JINA_API_KEY              (darmowy klucz dla 500 RPM)
KINDE_DOMAIN          (produkcja)
KINDE_AUDIENCE        (produkcja)
LOGFIRE_TOKEN         (produkcja)
```

## Status produkcji

ArticleWriter-v2 to fork z v1 (osobne repo `ArticleWriter`). v2 nie jest jeszcze na produkcji — produkcja nadal hosted z v1. Cutover na v2 = nowy Dockerfile + zmiana webhooków Make.com na endpoint `backend/main.py`.
