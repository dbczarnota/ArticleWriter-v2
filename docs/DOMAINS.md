# Konfiguracja domen — ArticleWriter-v2

Domena = zestaw ustawień redakcyjnych dla jednego portalu. Silnik (`agents/`, `toolsets/`) jest agnostyczny — domena definiuje **co** i **jak** pisać.

---

## Struktura plików domeny

```
domains/
  _base/
    config.py        — DomainConfig dataclass (nie edytować)
  moja_domena/
    __init__.py      — pusty
    config.py        — instancja DomainConfig eksportowana jako MOJA_DOMENA_DOMAIN
    guidelines.md    — instrukcje redakcyjne dla WriterAgent (styl, ton, zasady)
    examples.py      — lista przykładowych artykułów HTML jako EXAMPLE_ARTICLES
```

Przykład: `domains/styl_fm/` — gotowa referencyjna implementacja.

---

## DomainConfig — wszystkie pola

```python
@dataclass(frozen=True)
class DomainConfig:
    # === Wymagane ===
    name: str                          # unikalna nazwa domeny, snake_case
    description: str                   # jednozdaniowy opis dla agentów LLM

    # === Język i format ===
    language: str = "pl"               # BCP-47, używany w promptach i Serper
    html_format: str = ""              # instrukcja formatowania HTML dla WriterAgent

    # === Generowanie artykułu ===
    target_word_count: int = 600       # docelowa długość artykułu (słowa)
    max_facts_in_article: int = 8      # max liczba faktów przekazanych do writera
    max_quotes_in_article: int = 3     # max liczba cytatów przekazanych do writera

    # === Wyszukiwanie ===
    default_search_freshness: str = "qdr:w"   # świeżość wyników Google
                                               # qdr:d = 24h, qdr:w = tydzień, qdr:m = miesiąc
    default_num_queries: int = 3       # ile zapytań generuje SearchAgent
    default_max_results: int = 5       # max wyników per zapytanie (Serper)
    news_search: bool = False          # czy szukać też w Google News (/news endpoint)

    # === Scrapowanie ===
    max_pages_to_scrape: int = 10      # ile stron scrapers po filtrze LLM
                                       # filter rankuje best-first, bierzemy top N

    # === Media (embed candidates) ===
    youtube_search: bool = False       # szukaj filmów YouTube (Serper /videos)
    twitter_search: bool = False       # szukaj tweetów (Serper site:x.com)
    facebook_search: bool = False      # szukaj postów FB (Serper site:facebook.com)
    instagram_search: bool = False     # szukaj reels IG (Serper /images site:instagram.com/reel/)
    tiktok_search: bool = False        # szukaj TikTok (Serper /images site:tiktok.com/video/)
    reddit_search: bool = False        # szukaj wątków Reddit (public JSON API, bez auth)

    media_search_languages: tuple[str, ...] = ("en",)
    # BCP-47 kody języków dla zapytań social media. Dla każdego języka LLM
    # generuje oddzielne słowa kluczowe i szukamy na każdej platformie osobno.
    # Wyniki są deduplikowane po URL.
    # Wskazówka: zawsze zostaw "en" — większość social media jest po angielsku.
    # Przykład: ("en", "pl") dla polskiego portalu z polskimi celebrytami.

    media_search_num: int = 5          # max wyników per platforma per język

    # === Dane treningowe ===
    guidelines: str = ""               # zawartość guidelines.md
    example_articles: tuple[str, ...] = ()  # HTML przykładowych artykułów
```

---

## Freshness — wartości

| Wartość | Znaczenie | Kiedy używać |
|---|---|---|
| `qdr:h` | ostatnia godzina | breaking news |
| `qdr:d` | ostatnie 24h | newsy, celebryci |
| `qdr:w` | ostatni tydzień | domyślna |
| `qdr:m` | ostatni miesiąc | evergreen, analizy |

---

## Jak napisać guidelines.md

WriterAgent dostaje guidelines jako część system promptu. Pisz je jak brief dla dziennikarza:

- **Styl i ton** — krótkie zdania? clickbait? merytoryczny? sensacyjny?
- **Struktura artykułu** — nagłówki, śródtytuły, długość sekcji
- **Co unikać** — tematy tabu, wyrażenia, których nie używamy
- **Przykłady** — można cytować konkretne sformułowania

Długość: 200–500 słów. Wzorzec: `domains/styl_fm/guidelines.md`.

---

## Jak dodać example_articles

`examples.py` to plik z listą stringów HTML:

```python
# domains/moja_domena/examples.py
EXAMPLE_ARTICLES: list[str] = [
    """<h1>Tytuł artykułu</h1>
<p>Pierwszy akapit...</p>
""",
    # kolejny przykład...
]
```

Im więcej przykładów (3–5), tym lepiej WriterAgent rozumie oczekiwany styl. Minimalna długość przykładu: pełny artykuł (300+ słów).

---

## Tworzenie nowej domeny — krok po kroku

### 1. Skopiuj strukturę

```bash
cp -r domains/styl_fm domains/nowa_domena
```

### 2. Edytuj `config.py`

```python
from pathlib import Path
from domains._base.config import DomainConfig
from domains.nowa_domena.examples import EXAMPLE_ARTICLES

_GUIDELINES_PATH = Path(__file__).parent / "guidelines.md"

NOWA_DOMENA_DOMAIN = DomainConfig(
    name="nowa_domena",
    description="...",
    language="pl",
    target_word_count=800,
    default_search_freshness="qdr:w",
    max_pages_to_scrape=8,
    youtube_search=True,
    media_search_languages=("en", "pl"),
    guidelines=_GUIDELINES_PATH.read_text(encoding="utf-8"),
    html_format="...",
    example_articles=tuple(EXAMPLE_ARTICLES),
)
```

### 3. Napisz `guidelines.md`

Patrz sekcja wyżej.

### 4. Dodaj przykłady do `examples.py`

Minimum 1 artykuł. Docelowo 3–5.

### 5. Przetestuj przez `run.py`

```python
# run.py — podmień domenę:
from domains.nowa_domena.config import NOWA_DOMENA_DOMAIN
domain = NOWA_DOMENA_DOMAIN
```

---

## Dobieranie parametrów — wskazówki

### Ile stron scrapować? (`max_pages_to_scrape`)

| Typ domeny | Zalecane |
|---|---|
| Newsy/celebryci (krótki artykuł, dużo źródeł) | 6–10 |
| Analityczny/biznesowy (potrzeba faktów) | 10–15 |
| Evergreen/Wikipedia-style | 15–20 |

Filter LLM rankuje best-first — zwiększenie limitu podnosi jakość nieznacznie, ale wydłuża czas i koszt.

### Ile zapytań i wyników? (`default_num_queries`, `default_max_results`)

Łączna pula przed filtrem: `num_queries × max_results`. Np. 3 × 5 = 15 kandydatów → filter wybiera top 10.

Zwiększenie `max_results` ponad 10 rzadko pomaga (Serper zwraca i tak te same strony).

### Media search — co włączać?

- **YouTube** — zawsze, jeśli temat może mieć wideo. Działa bardzo dobrze.
- **Twitter** — warto dla newsów, celebrytów, sportu. Google częściowo indeksuje X.
- **Instagram** — reels dla lifestyle/beauty/fashion. Działa przez `/images`.
- **TikTok** — analogicznie do Instagram, ale słabsze wyniki.
- **Facebook** — działa, ale FB jest coraz mniej zaindeksowany.
- **Reddit** — darmowe, przydatne dla tematów gdzie jest anglojęzyczna dyskusja.

`media_search_languages=("en",)` — domyślne, wystarczy dla większości tematów.
`media_search_languages=("en", "pl")` — jeśli piszesz o polskich celebrytkach/wydarzeniach.

---

## Testowanie przez run.py

```bash
python run.py
```

Domyślnie uruchamia pipeline dla styl.fm. Logi debug pokazują:
- **SEARCH** — sformułowane zapytania, liczba wyników
- **MEDIA SEARCH** — sformułowane keyword queries (per język), znalezione embedy per platforma
- **SCRAPING** — ile stron scrapowano (tier-1/2), ile odrzucono przez filter
- **PARSING** → **EXTRACTION** → **INSTRUCTIONS** → **WRITING** → **REFLECTION**

Aby przetestować inną domenę — podmień `domain` w `run.py`.

---

## Referencyjna implementacja: styl.fm

```
domains/styl_fm/
├── config.py       — DomainConfig z pełnym zestawem flag
├── guidelines.md   — brief dla polskiego portalu lifestyle
└── examples.py     — 1+ przykładowych artykułów HTML
```

Konfiguracja styl.fm używa:
- `qdr:d` (24h freshness) — newsy
- `max_pages_to_scrape=10`
- wszystkie platformy social oprócz Facebook
- `media_search_languages=("en", "pl")` — tematy globalne + polskie
