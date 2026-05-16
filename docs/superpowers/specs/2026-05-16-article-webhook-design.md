# Article Webhook — Design Spec

**Date:** 2026-05-16
**Status:** Approved (brainstorming)

## Cel

Umożliwić wypchnięcie gotowego artykułu (HTML + metadane + URL-e do wygenerowanych obrazków) na zewnętrzny webhook skonfigurowany per organizacja. Typowy odbiorca: Make.com / n8n / własny endpoint CMS-a.

## UX

**Settings (per org):**
- Pole „Webhook URL" (text, walidacja `https://`).
- Pole „Webhook Secret" (password, opcjonalne).
- Oba puste domyślnie. Edytowane jak każda inna opcja w `OrgConfig`.

**Article view:**
- Guzik „Wyślij" pojawia się **tylko** gdy `orgConfig.webhook_url` jest niepuste. Umieszczony obok istniejącego „Kopiuj HTML".
- Pod guzikami linijka statusu z ostatniej wysyłki, czytana z `article.webhook_deliveries[-1]`:
  - `✓ Wysłano 2 min temu` (sukces)
  - `❌ Błąd 500 — 3 min temu` (porażka)
  - brak linijki gdy `webhook_deliveries` jest puste
- Klik → spinner na guziku → POST do backendu → toast sukces/błąd → re-fetch artykułu (status się odświeża).
- Bez modala potwierdzenia — guzik jest wyraźny, user wie co robi.

## Model danych

**`OrgConfig`** — dwa nowe pola:
- `webhook_url: str | None` (default `None`)
- `webhook_secret: str | None` (default `None`)

**`Article`** — jedno nowe pole:
- `webhook_deliveries: list[dict]` (JSONB column, default `[]`)

Każdy wpis w `webhook_deliveries`:
```json
{
  "sent_at": "2026-05-16T09:42:00Z",
  "status": "success" | "error",
  "http_status": 200,
  "error": null
}
```
`error` to krótki string (`"timeout"`, `"connection refused"`, `"http 500"`, itd.) gdy `status == "error"`, inaczej `null`.

Migracja Alembic dodająca te trzy pola (nullable / default `[]`). Wzór nazewnictwa jak istniejące migracje w `backend/alembic/versions/`.

## Backend

**Settings API** — bez nowych route'ów. `OrgConfig` ma generyczny update endpoint; dwa nowe pola dołączają do schemy `OrgConfigUpdate`.

**Nowy endpoint:** `POST /api/v2/articles/{article_id}/send-webhook`

Flow:
1. Pobierz artykuł + org config (zwykła autoryzacja przez `get_current_org`, filtr po `org_code`).
2. Jeśli `webhook_url` puste → `400 {"error": "webhook not configured"}`.
3. Zbuduj payload (sekcja „Payload").
4. POST przez `httpx.AsyncClient(timeout=30)`:
   - `Content-Type: application/json`
   - `User-Agent: ArticleWriter/2`
   - `X-Webhook-Secret: <secret>` (tylko gdy `webhook_secret` ustawiony)
5. Złap response (każdy wynik kończy się wpisem do `webhook_deliveries`):
   - 2xx → `status="success"`, `http_status=<code>`, `error=null`
   - inny kod → `status="error"`, `http_status=<code>`, `error="http <code>"`
   - `httpx.TimeoutException` → `status="error"`, `http_status=null`, `error="timeout"`
   - inny wyjątek httpx → `status="error"`, `http_status=null`, `error=<str(exc)[:200]>`
6. Append do `webhook_deliveries`, save, return `{status, http_status, error}` do frontu.

Bez background tasków, bez kolejki, bez retry — synchroniczne (max ~30s). User świadomie klika ponownie jeśli padło.

## Payload

Stabilny schemat — pydantic model `WebhookPayload` w `backend/api/schemas/`. Pola, których artykuł nie ma (np. brak wygenerowanych obrazków) → puste listy / null, **nie** pomijane.

```json
{
  "article_id": "uuid",
  "org_code": "styl_fm",
  "sent_at": "2026-05-16T09:42:00Z",
  "topic": "Oryginalny temat",
  "title": "Główny tytuł H1",
  "alternative_titles": ["alt 1", "alt 2"],
  "html": "<h1>...</h1><p>...</p>",
  "raw_facts": "tekst faktów / cytatów",
  "related_topics": [
    {"title": "...", "reason": "..."}
  ],
  "generated_images": [
    {
      "label": "hero",
      "url": "https://r2.../image.png",
      "template_id": "uuid",
      "created_at": "2026-05-16T09:30:00Z"
    }
  ],
  "metadata": {
    "created_at": "2026-05-16T09:25:00Z",
    "model_used": "gemini-3.1-pro",
    "domain": "styl.fm"
  }
}
```

`sent_at` generowane w momencie POST-u (nie w momencie zapisu do bazy). Same URL-e do zdjęć — bez base64.

## Bezpieczeństwo

- Webhook URL i secret per org, trzymane w `OrgConfig` (PostgreSQL).
- Jeśli `webhook_secret` ustawiony, dodajemy nagłówek `X-Webhook-Secret: <secret>`. Odbiorca weryfikuje porównaniem stringa.
- Walidacja URL po stronie backendu: musi zaczynać się od `https://` (odrzucamy `http://`, `file://`, itd.).
- Secret w UI jako `<input type="password">` (nie ekspozycji w plain textcie).
- W logach Logfire **nie** logujemy `webhook_secret` ani full payloadu (rozmiar) — tylko `article_id`, `webhook_url` (host), status, http_code.

## Frontend

**Nowe pliki / zmiany:**
- Settings UI — sekcja „integracje" (nowa, bo `webhook` to inny koncept niż dotychczasowe „szablony"). Alternatywnie: dorzucić do „ustawień ogólnych" jeśli już istnieją. Wybór miejsca podczas planowania.
- Article view — dodać guzik i status obok istniejącego „Kopiuj HTML". Jeden nowy hook / mała funkcja `sendArticleToWebhook(articleId)`.
- i18n PL: `webhook.url`, `webhook.secret`, `webhook.send`, `webhook.sent_ago`, `webhook.error`, `webhook.not_configured`.

## Testy

- Backend: unit test endpointu `POST /send-webhook` (respx do mockowania httpx) — happy path 2xx, błąd 500, timeout. Test że nagłówek `X-Webhook-Secret` jest / nie ma w zależności od konfiguracji. Test że pusty `webhook_url` → 400.
- Backend: test schemy `WebhookPayload` — wszystkie pola się serializują.
- Frontend: light test że guzik się nie pokazuje gdy `webhook_url` puste.

## Out of scope (świadomie)

- Retry / kolejka / background task.
- HMAC signature (jeśli kiedyś będzie potrzebne — drugi krok).
- Webhook delivery history UI poza „ostatni status" (jeśli ktoś chce historię, czyta przez API).
- Walidacja po stronie odbiorcy (że ma poprawny endpoint) — to ich problem.
- Bulk-send (wysłanie wielu artykułów naraz).
