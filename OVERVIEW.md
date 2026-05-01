# ArticleWriter-v2 — Opis projektu i kierunek rozwoju

## 1. Cel projektu

Automatyczny system generowania artykułów prasowych. Użytkownik podaje temat; system przeszukuje internet, ekstrakcuje fakty i cytaty, a następnie pisze gotowy artykuł HTML zgodnie z wytycznymi redakcyjnymi skonfigurowanej domeny.

Obecna wersja jest ściśle powiązana z **Styl.fm** (clickbait/lifestyle). Refaktor oddziela silnik od domeny, umożliwiając obsługę dowolnego stylu redakcyjnego (tabloidy, prasa biznesowa, press releases).

---

## 2. Pipeline — jak działa silnik

Sekwencja 9 agentów pydantic-ai. Każdy agent otrzymuje wiadomości od poprzedniego (conversation history lub tool responses):

```
[topic + domain config]
        │
        ▼
1. SearchAgent           → queries, SEO keywords
        │
        ▼
2. SearchResultFilter    → Serper.dev → snippet pre-filter (LLM)
   (wbudowany w          → odrzuca URLe gdzie snippet nie rokuje
    ScrapingAgent)       → fetch tylko obiecujących URLi
        │
        ▼
3. ScrapingAgent         → scraped pages (Markdown)   ← httpx/trafilatura/Jina (tylko pre-filtered)
        │
        ▼
4. ParsingAgent          → cleaned articles            ← classifies: article vs. other
        │
        ▼
5. ExtractionAgent       → facts[], quotes[], keywords[]
        │
        ▼
6. AdaptiveSearchAgent   → "mam dość?" jeśli nie: 1–2 dodatkowe queries → wróć do 2.
   (opcjonalny, flaga)     jeśli tak: przejdź dalej
        │
        ▼
7. InstructionsAgent     → writing brief (prompt)      ← uses domain guidelines + examples
        │
        ▼
8. WriterAgent           → article HTML (round 1)
        │
        ▼
9. ReflectionAgent       → improvement feedback        (opcjonalny, flaga)
        │
        ▼
10. WriterAgent          → article HTML (round 2)
        │
        ▼
11. FollowUpAgent        → 10 alt titles, 5 related topics, used facts tracking
        │
        ▼
[HTML report + webhook → Make.com]
```

Opcjonalny `LlmKnowledgeAgent` (między 1 i 2) dostarcza fakty z wiedzy modelu bez scraping.

### Wzorzec: snippet pre-filter przed scrapingiem

Serper zwraca tytuł + snippet dla każdego URLa — LLM ocenia snippety **zanim** pójdziemy po pełną treść. Fetch tylko tych URLi, gdzie snippet sugeruje relevantność.

```
Serper → [url, title, snippet][] → LLM ocenia snippety → odrzuca słabe
       → httpx/trafilatura tylko dla wybranych URLi
```

Inspiracja: Claude Code robi to samo — `WebSearch` zwraca snippety, agent sam decyduje które URLe warte `WebFetch`. Efekt: mniej requestów, szybciej, taniej. Wbudowane w `ScrapingAgent` (nie osobny krok).

### Freshness control

Serper obsługuje parametr `tbs` (przekazywany wprost do Google). Konfigurowalny w `SearchAgentConfig`:

```python
search_freshness: str = "qdr:w"   # domyślnie: ostatni tydzień
# qdr:h=godzina, qdr:d=24h, qdr:w=tydzień, qdr:m=miesiąc
```

Można nadpisać per-request. Zapobiega pisaniu newsa na bazie źródeł sprzed roku.

### Opcjonalne źródła: YouTube + Twitter/X

Konfigurowane per-domena (`DomainConfig`). Silnik ich nie wymaga — to add-on dla domen newsowych/sportowych.

**YouTube Data API v3** — darmowe (10k jednostek/dobę, 100 jednostek per search = 100 searchów/dobę):
- Zwraca linki do filmów z tytułem i opisem
- Flaga: `youtube_search: bool = False` w `DomainConfig`
- Use case: sport (bramki, skróty), celebryci (wywiady, materiały wideo)

**Twitter/X via `site:x.com` w Serper** — best-effort, bez dodatkowych kosztów:
- Serper wysyła `q="temat site:x.com"` → Google zwraca zaindeksowane publiczne posty
- Nie real-time (opóźnienie godzin), nie kompletne — traktujemy jako secondary sources
- Flaga: `twitter_search: bool = False` w `DomainConfig`

**Facebook via `site:facebook.com` w Serper** — best-effort, bez dodatkowych kosztów:
- Działa dla publicznych stron i fanpage'y indeksowanych przez Google
- Graph API jest za bardzo zamknięte po 2018, scraping niestabilny — nie używamy
- Flaga: `facebook_search: bool = False` w `DomainConfig`

**Instagram/TikTok** — nie implementujemy (brak stabilnego API, osobny projekt).

### Typy danych: kontekst przy faktach i cytatach

Każdy fakt i cytat niesie obowiązkowy `context` — skąd pochodzi i czego dotyczy.  
Eliminuje problem "fakt bez kontekstu = różna interpretacja przez WriterAgent."

```python
@dataclass
class Fact:
    text: str        # "zarobił 2 miliony złotych"
    context: str     # "Dawid Podsiadło, trasa Małomiasteczkowy 2025"
    source_url: str
    source_title: str

@dataclass
class Quote:
    text: str        # "To był najpiękniejszy rok w moim życiu"
    speaker: str     # "Dawid Podsiadło"
    context: str     # "o trasie koncertowej, wywiad dla Gazety Wyborczej"
    source_url: str
```

### Kontrola długości — w DomainConfig

`WriterAgent` dostaje N wybranych faktów, nie wszystkie. Wyboru dokonuje `InstructionsAgent`.

```python
@dataclass
class DomainConfig:
    target_word_count: int = 600      # styl.fm: krótkie, clickbaitowe
    max_facts_in_article: int = 8
    max_quotes_in_article: int = 3
    # inne domeny mogą mieć target_word_count=2000, max_facts=20
```

Nieużyte fakty trafiają do raportu (już teraz śledzony w FollowUpAgent).

### Wzorzec AdaptiveSearchAgent (inspiracja: dzhng/deep-research, Karpathy ratchet)

Zamiast z góry zakodowanej liczby queries, agent po ekstrakcji ocenia pokrycie:
- "Mam wystarczająco faktów i cytatów → kontynuuj"
- "Brakuje mi X → wygeneruj 1–2 dodatkowe queries, zescrape, dołącz do zebranych danych"

Max 1–2 rundy dogłębne (depth=1), żeby koszt pozostał deterministyczny.  
Kontrolowane przez `PipelineFlags.adaptive_search: bool = True` — można wyłączyć per-request.

---

## 3. Separacja silnika od domeny

**Silnik** — agnostic:
- Agenci, toolsets, scraping, ekstrakcja, retry logic
- Nie wie nic o stylu pisania, nie ma wbudowanych wytycznych

**Domena** — konfiguracja redakcyjna:
```
domains/styl_fm/
  config.py          — DomainConfig (nazwa, opis, prompty bazowe)
  guidelines.md      — "Biblia Redaktora" (zasady pisania, słownictwo)
  examples.py        — Przykładowe artykuły do benchmarkingu
```

Przykłady domen:
- `styl_fm` — clickbait, celebryci, emocje (istniejąca)
- `the_economist` — analityczny, neutralny ton, data-driven
- `press_release` — korporacyjny, suchy, fakty
- `washington_post` — długa forma, investigative

Tworzenie nowej domeny = dodanie katalogu w `domains/` bez zmian w silniku.

---

## 4. System konfiguracji

Wzorzec z prawnik-ai-v2: frozen dataclasses + `AppSettings.from_request()`.

**Co jest konfigurowalne per-request:**
- Model dla każdego agenta (np. `writer_model = "gemini-2.5-pro"`)
- Thinking mode per-agent (`off` / `minimal` / `low` / `medium` / `high`)
- Tool call budget per-agent
- Flagi pipeline: `provide_llm_facts`, `enable_reflection`, `skip_followup`
- Domena: `domain = "styl_fm"` | `"the_economist"` | ...
- Parametry scrapingu: `num_queries`, `max_results`, `search_days`
- Filtry: `domains[]` (whitelist domen), `urls[]` (manualne URLe)

**AppSettings hierarchy:**
```python
AppSettings
  ├── search: SearchAgentConfig        (model, budget)
  ├── scraping: ScrapingConfig          (max_results, timeout, extraction_mode)
  ├── parsing: ParsingAgentConfig       (model, budget)
  ├── extraction: ExtractionAgentConfig (model, budget)
  ├── instructions: InstructionsAgentConfig (model, thinking)
  ├── writer: WriterAgentConfig          (model, thinking, rounds)
  ├── reflection: ReflectionAgentConfig  (model, budget, enabled)
  ├── followup: FollowUpAgentConfig      (model, budget, enabled)
  ├── pipeline: PipelineFlags            (llm_facts, adaptive_search, reflection, followup)
  └── domain: str                        (domain identifier)
```

---

## 5. Architektura techniczna

### Backend
- **FastAPI** — REST API + SSE streaming
- **pydantic-ai** — agenci z `agent.iter()`, message passing między agentami
- **pydantic** — typy, konfiguracja, validacja requestów
- **Logfire** — observability (spans, OTEL metrics per-agent)
- **httpx** — HTTP client (Kinde JWKS, webhooks, scraping tier-1)
- **trafilatura** — ekstrakcja treści artykułów z HTML (tier-1 scraping)
- **Jina Reader (r.jina.ai)** — managed headless scraping tier-2 (fallback gdy httpx/trafilatura nie wystarczy)
- **Serper.dev** — wyszukiwanie internetowe (Google SERP, URL + snippet)
- ~~Crawl4AI + Playwright~~ — zastąpione (aktywne bugi z browser lifecycle)
- ~~Tavily~~ — zastąpione Serperem (8–27x droższy przy tym samym use case)
- Firecrawl — placeholder na tier-3 (Cloudflare bypass), nie implementujemy na start

### Scraping — architektura warstwowa

```
1. httpx + trafilatura   ← szybki, niezawodny, zero zależności
        │ content pusty lub HTTP error
        ▼
2. Jina Reader           ← managed headless, brak browser management
        │ (paywall, login-protected)
        ▼
3. [Firecrawl — TODO gdy zajdzie potrzeba]
```

### Jina Reader — limity i semafor

- Free tier z API key: **500 RPM**, 10M tokenów gratis
- Paid: PAYG token-based (~$0.02/1M tokenów)
- **Globalny semafor** — wymagany, bo wielu użytkowników generuje artykuły równolegle

```python
# toolsets/scraping/rate_limiter.py
import asyncio

# Singleton na poziomie procesu — dzielony między wszystkich userów i workery
_JINA_SEMAPHORE = asyncio.Semaphore(8)  # max 8 concurrent = ~480 RPM z marginesem

async def fetch_with_jina(url: str) -> str:
    async with _JINA_SEMAPHORE:
        # httpx call do r.jina.ai/url
        ...
```

Wartość semafora (8) zakłada avg ~1s na request. Przy wzroście skali: podnieść do 15–20 lub dokupić Premium Key (5,000 RPM).

### Auth (Kinde)
- `NullAuthenticator` — lokalne dev, jeden tenant
- `KindeAuthenticator` — OIDC JWT, multi-tenant produkcja
- Aktywacja warunkowa: jeśli `KINDE_DOMAIN` ustawiony → Kinde, inaczej Null

### Observability (Logfire)
- `@logfire.instrument("agent_name")` na każdym agencie
- OTEL metrics: liczba wywołań LLM, tokeny, czas każdego etapu
- `send_to_logfire="if-token-present"` — lokalnie tylko logi konsolowe

### Prompty — format

Dwa zastosowania, dwa niezależne podejścia:

| Zastosowanie | Format | Dlaczego |
|---|---|---|
| Instrukcje (system prompt) | Jinja2 + adapter XML/Markdown | różne modele mają różne preferencje |
| Output agenta | pydantic `result_type=` | 100% reliability, zero "failed to parse" |

**Nie używamy JSON-stringów w treści promptów.**

#### Prompt adapter — jeden template, dwa formaty renderowania

Claude preferuje XML tagi; Gemini preferuje Markdown (34-38% mniej tokenów niż XML).  
Jeden plik `.j2` na agenta, zmienna `format_style` decyduje o renderowaniu:

```python
# agents/_base/prompt_renderer.py
def model_format_style(model: str) -> str:
    if model.startswith("anthropic:"):
        return "xml"
    return "markdown"  # google, openai, groq — wszystkie inne
```

```jinja2
{# fragment writer.j2 — jeden plik obsługuje oba formaty #}
{% macro section(name, content) %}
{% if format_style == "xml" %}<{{ name }}>{{ content }}</{{ name }}>
{% else %}## {{ name | upper }}
{{ content }}{% endif %}
{% endmacro %}

{{ section("task", "Napisz artykuł: " + topic) }}
{{ section("guidelines", guidelines) }}
{{ section("facts", facts | join("\n")) }}
```

### Testy
- Pytest + pytest-asyncio
- respx dla mockowania HTTP (Kinde JWKS, Serper, webhooks)
- `StaticAuthenticator` fixture dla auth bypass w testach
- Testy jednostkowe: konfiguracja agentów, prompt rendering, parsowanie output
- Testy integracyjne: full pipeline z zamockowanymi external calls

### Deployment
- Docker, Python 3.12, uv
- GitHub Actions CI/CD
- Webhook response → Make.com (non-breaking: stary endpoint działa równolegle)

---

## 6. Frontend (kolejny etap)

Po stabilizacji backendu:
- Kinde auth (SSO / email)
- Panel zarządzania: tworzenie requestów, historia artykułów, ustawienia domeny
- Live progress (SSE streaming): widać, który agent aktualnie pracuje
- Wzorzec z prawnik-ai-v2

---

## 7. Strategia wdrożenia (Non-Breaking Changes)

Obecna produkcja na `/write_article` działa bez zmian.

1. Nowy backend pod `/v2/write_article` (równolegle)
2. Testy na ruchu testowym
3. Cutover = zmiana webhooków w Make.com
4. Wyłączenie starego endpoint po stabilizacji

Każdy commit deployowalny osobno — żadnych "WIP commits".

---

## 8. Kolejne kroki (wysoki poziom)

1. **Spec + Plan: Konfiguracja i domeny** — `DomainConfig`, `AppSettings`, typy
2. **Spec + Plan: Agenci** — jeden po drugim, z testami
3. **Spec + Plan: FastAPI backend** — endpointy, auth, SSE, kolejka
4. **Spec + Plan: Integracja pipeline** — łączenie agentów, message passing
5. **Spec + Plan: Observability** — Logfire setup, metryki
6. **Spec + Plan: Frontend** — po stabilizacji backendu
