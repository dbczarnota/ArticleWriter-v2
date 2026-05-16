# Article Webhook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Push a finished article (HTML + metadata + image URLs) to a per-org webhook URL, triggered by a "Wyślij" button in the article view.

**Architecture:** Two new fields on `OrgConfig` (`webhook_url`, `webhook_secret`) and one on `Article` (`webhook_deliveries`). New endpoint `POST /v2/articles/{id}/send-webhook` does a synchronous `httpx` POST (30s timeout, no retry) and appends a delivery record. Frontend: a new "integracje" settings section for the two inputs; in the article toolbar a "Wyślij" button (visible only when `webhook_url` is set) + small status line for the last delivery.

**Tech Stack:** Python 3.12, SQLModel + Alembic, FastAPI, pydantic, httpx, respx (tests), React + TypeScript.

---

## File Structure

**Backend (create):**
- `migrations/versions/c1d2e3f4a5b6_add_webhook_fields.py` — Alembic migration

**Backend (modify):**
- `backend/db/models.py` — add `webhook_url`, `webhook_secret` to `OrgConfig`; add `webhook_deliveries` to `Article`
- `backend/api/schemas.py` — add fields to `DomainConfigUpdate`; add `WebhookPayload`, `WebhookDeliveryRecord` models
- `backend/api/v2.py` — extend `_org_config_to_dict`; new endpoint `send_article_webhook`
- `backend/repositories/protocols.py` — add `ArticleRepository.record_webhook_delivery` method
- `backend/repositories/postgres.py` — implement `record_webhook_delivery` (UPDATE + JSONB append)
- `backend/repositories/null.py` — no-op `record_webhook_delivery`

**Backend (create — tests):**
- `tests/api/test_send_webhook.py` — endpoint tests with `respx`

**Frontend (modify):**
- `frontend/src/types.ts` — add `webhook_url`, `webhook_secret` to `DomainConfigData`; add `WebhookDelivery` interface; add `webhook_deliveries` to `Article`
- `frontend/src/i18n/types.ts` — add `articleView.send*` keys + `settingsNav.integrations` + `domainConfig.webhook*` keys
- `frontend/src/i18n/pl.ts` + `en.ts` — add the strings
- `frontend/src/components/SettingsNav.tsx` — add `"integracje"` section ID + label
- `frontend/src/components/DomainConfigForm.tsx` — add `integracje` section with URL + secret inputs
- `frontend/src/components/ArticleView.tsx` — add "Wyślij" button + status line

---

## Task 1: DB migration

**Files:**
- Create: `migrations/versions/c1d2e3f4a5b6_add_webhook_fields.py`

- [ ] **Step 1: Write the migration file**

```python
"""add webhook fields

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-05-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

revision = "c1d2e3f4a5b6"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "org_configs",
        sa.Column("webhook_url", sa.String(2048), nullable=True),
    )
    op.add_column(
        "org_configs",
        sa.Column("webhook_secret", sa.String(256), nullable=True),
    )
    op.add_column(
        "articles",
        sa.Column(
            "webhook_deliveries",
            JSONB(),
            nullable=False,
            server_default=text("'[]'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("articles", "webhook_deliveries")
    op.drop_column("org_configs", "webhook_secret")
    op.drop_column("org_configs", "webhook_url")
```

- [ ] **Step 2: Verify alembic recognizes the file**

Run: `uv run alembic heads`
Expected: shows `c1d2e3f4a5b6 (head)` (and confirms `b0c1d2e3f4a5` is the parent — no branches).

- [ ] **Step 3: Commit**

```bash
git add migrations/versions/c1d2e3f4a5b6_add_webhook_fields.py
git commit -m "feat(db): add webhook fields migration"
```

---

## Task 2: Model fields

**Files:**
- Modify: `backend/db/models.py` (add fields to `OrgConfig` class, add field to `Article` class)

- [ ] **Step 1: Add the two `OrgConfig` fields**

In `backend/db/models.py`, inside the `OrgConfig` class, immediately before the `updated_at` field (around line 453), add:

```python
    webhook_url: str | None = Field(
        default=None, sa_column=Column(String(2048), nullable=True)
    )
    """Per-org outbound webhook for sending finished articles. None = button hidden."""

    webhook_secret: str | None = Field(
        default=None, sa_column=Column(String(256), nullable=True)
    )
    """Optional shared secret sent as X-Webhook-Secret header when set."""
```

- [ ] **Step 2: Add the `Article.webhook_deliveries` field**

In the same file, inside the `Article` class, immediately after the `generated_images` field (around line 144), add:

```python
    webhook_deliveries: list[dict] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default=text("'[]'")),
    )
    """Append-only history of POSTs to OrgConfig.webhook_url. Each entry:
    {sent_at: iso, status: 'success'|'error', http_status: int|None, error: str|None}."""
```

- [ ] **Step 3: Run linter + type checker on the changed file**

Run: `uv run ruff check backend/db/models.py && uv run pyright backend/db/models.py`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add backend/db/models.py
git commit -m "feat(models): add webhook fields to OrgConfig and Article"
```

---

## Task 3: Apply migration and verify against DB

**Files:**
- None (verification only)

- [ ] **Step 1: Apply the migration locally**

Run: `uv run alembic upgrade head`
Expected: log line `Running upgrade b0c1d2e3f4a5 -> c1d2e3f4a5b6, add webhook fields`.

If you do not have a local DB, skip this step — the migration will run against prod via the deploy pipeline. Document the skip in the commit message of the next task instead.

- [ ] **Step 2: Confirm columns exist (only if local DB available)**

Run: `uv run python -c "import asyncio; from sqlalchemy import text; from backend.db.session import get_session_maker; sm = get_session_maker(); \nasync def chk():\n  async with sm() as s:\n    r = await s.execute(text(\"select column_name from information_schema.columns where table_name='org_configs' and column_name like 'webhook%'\"))\n    print(r.fetchall())\nasyncio.run(chk())"`
Expected: `[('webhook_url',), ('webhook_secret',)]`

---

## Task 4: Backend schemas

**Files:**
- Modify: `backend/api/schemas.py` (extend `DomainConfigUpdate`; add `WebhookPayload`, `WebhookDeliveryRecord`)

- [ ] **Step 1: Extend `DomainConfigUpdate`**

In `backend/api/schemas.py`, inside the `DomainConfigUpdate` class, immediately after the `image_creator_enabled: bool = False` line (around line 229), add:

```python
    webhook_url: str | None = None
    webhook_secret: str | None = None
```

- [ ] **Step 2: Add the payload + delivery-record models**

Append to `backend/api/schemas.py` (after `ContactRequest`):

```python
class GeneratedImagePayload(BaseModel):
    label: str = ""
    url: str
    template_id: str | None = None
    created_at: str | None = None


class RelatedTopicPayload(BaseModel):
    title: str
    reason: str = ""


class WebhookPayloadMetadata(BaseModel):
    created_at: str | None = None
    domain: str = ""


class WebhookPayload(BaseModel):
    """Stable contract sent to OrgConfig.webhook_url. Fields with no data
    are sent as empty lists / null — never omitted."""

    article_id: str
    org_code: str
    sent_at: str
    topic: str
    title: str = ""
    alternative_titles: list[str] = PydanticField(default_factory=list)
    html: str = ""
    raw_facts: str = ""
    related_topics: list[RelatedTopicPayload] = PydanticField(default_factory=list)
    generated_images: list[GeneratedImagePayload] = PydanticField(default_factory=list)
    metadata: WebhookPayloadMetadata = PydanticField(default_factory=WebhookPayloadMetadata)


class WebhookDeliveryRecord(BaseModel):
    """One entry in Article.webhook_deliveries — also the response shape
    of POST /v2/articles/{id}/send-webhook."""

    sent_at: str
    status: str  # "success" | "error"
    http_status: int | None = None
    error: str | None = None
```

`raw_facts` here is a single string built by joining `Fact.text` rows with newlines (see Task 6 — this is intentionally NOT the structured facts list, because the spec calls for a single human-readable text block).

- [ ] **Step 3: Lint + type-check**

Run: `uv run ruff check backend/api/schemas.py && uv run pyright backend/api/schemas.py`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add backend/api/schemas.py
git commit -m "feat(api): webhook schemas (DomainConfigUpdate fields + WebhookPayload)"
```

---

## Task 5: Extend `_org_config_to_dict`

**Files:**
- Modify: `backend/api/v2.py` (function `_org_config_to_dict`, around line 1938)

- [ ] **Step 1: Add the two new keys to the returned dict**

In `backend/api/v2.py`, inside `_org_config_to_dict`, immediately after the `"image_creator_enabled": config.image_creator_enabled,` line (around line 1974), add:

```python
        "webhook_url": config.webhook_url,
        "webhook_secret": config.webhook_secret,
```

- [ ] **Step 2: Lint + type-check**

Run: `uv run ruff check backend/api/v2.py && uv run pyright backend/api/v2.py`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add backend/api/v2.py
git commit -m "feat(api): expose webhook fields in /v2/domain-config response"
```

---

## Task 6: ArticleRepository.record_webhook_delivery

**Files:**
- Modify: `backend/repositories/protocols.py` — protocol method
- Modify: `backend/repositories/postgres.py` — implementation
- Modify: `backend/repositories/null.py` — no-op
- Create: `tests/repositories/test_record_webhook_delivery.py`

- [ ] **Step 1: Add the protocol method**

In `backend/repositories/protocols.py`, inside the `ArticleRepository` Protocol, immediately after the `set_marked_done` method (around line 145), add:

```python
    async def record_webhook_delivery(
        self,
        article_id: UUID,
        *,
        org_code: str,
        entry: dict,
    ) -> None:
        """Append `entry` to articles.webhook_deliveries for the given article.

        `entry` must already match WebhookDeliveryRecord shape (sent_at, status,
        http_status, error). No-op when the article does not exist or belongs
        to a different org (idempotent across tenants).
        """
        ...
```

- [ ] **Step 2: Implement in postgres.py**

Find the existing `set_marked_done` method in `backend/repositories/postgres.py` and add this method right after it:

```python
    async def record_webhook_delivery(
        self,
        article_id: UUID,
        *,
        org_code: str,
        entry: dict,
    ) -> None:
        from sqlalchemy import text as _sql_text

        async with self._sessionmaker() as session:
            await session.execute(
                _sql_text(
                    "UPDATE articles SET webhook_deliveries = "
                    "COALESCE(webhook_deliveries, '[]'::jsonb) || CAST(:entry AS jsonb) "
                    "WHERE id = :id AND org_code = :org"
                ),
                {"entry": __import__("json").dumps(entry), "id": str(article_id), "org": org_code},
            )
            await session.commit()
```

(Use the existing import style for `text` already present in `postgres.py` — replace the local re-import if the file already imports `text` at module scope. Check imports before writing.)

- [ ] **Step 3: Implement no-op in null.py**

Find the `NullArticleRepository` class in `backend/repositories/null.py` and add this method after `set_marked_done`:

```python
    async def record_webhook_delivery(
        self,
        article_id: UUID,
        *,
        org_code: str,
        entry: dict,
    ) -> None:
        return None
```

- [ ] **Step 4: Write the failing test**

Create `tests/repositories/test_record_webhook_delivery.py`:

```python
"""Tests for ArticleRepository.record_webhook_delivery — JSONB append + tenant filter."""

from __future__ import annotations

import pytest

from backend.repositories.postgres import PostgresArticleRepository


@pytest.mark.asyncio
async def test_record_webhook_delivery_appends(postgres_session_maker, seeded_article):
    """Two appends produce a list of length 2 with the right contents."""
    repo = PostgresArticleRepository(postgres_session_maker)
    await repo.record_webhook_delivery(
        seeded_article.id,
        org_code=seeded_article.org_code,
        entry={"sent_at": "2026-05-16T09:00:00Z", "status": "success", "http_status": 200, "error": None},
    )
    await repo.record_webhook_delivery(
        seeded_article.id,
        org_code=seeded_article.org_code,
        entry={"sent_at": "2026-05-16T09:05:00Z", "status": "error", "http_status": 500, "error": "http 500"},
    )
    article = await repo.get(seeded_article.id, org_code=seeded_article.org_code)
    assert article is not None
    assert len(article.webhook_deliveries) == 2
    assert article.webhook_deliveries[0]["status"] == "success"
    assert article.webhook_deliveries[1]["http_status"] == 500


@pytest.mark.asyncio
async def test_record_webhook_delivery_other_org_noop(postgres_session_maker, seeded_article):
    """Append targeted at the wrong org code is a no-op (tenant isolation)."""
    repo = PostgresArticleRepository(postgres_session_maker)
    await repo.record_webhook_delivery(
        seeded_article.id,
        org_code="some-other-org",
        entry={"sent_at": "2026-05-16T09:00:00Z", "status": "success", "http_status": 200, "error": None},
    )
    article = await repo.get(seeded_article.id, org_code=seeded_article.org_code)
    assert article is not None
    assert article.webhook_deliveries == []
```

The fixtures `postgres_session_maker` and `seeded_article` already exist in `tests/conftest.py` (testcontainers-based). If naming differs, grep `tests/conftest.py` for the existing article-seed fixture and adapt — do not introduce a new one.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/repositories/test_record_webhook_delivery.py -v`
Expected: both tests PASS. If FAIL on fixture import, adapt fixture names to whatever `tests/conftest.py` actually provides.

- [ ] **Step 6: Commit**

```bash
git add backend/repositories/protocols.py backend/repositories/postgres.py backend/repositories/null.py tests/repositories/test_record_webhook_delivery.py
git commit -m "feat(repo): record_webhook_delivery on ArticleRepository"
```

---

## Task 7: send-webhook endpoint

**Files:**
- Modify: `backend/api/v2.py` (new endpoint + payload-build helper)
- Create: `tests/api/test_send_webhook.py`

- [ ] **Step 1: Add the payload-build helper near the bottom of v2.py**

Insert above `_org_config_to_dict` in `backend/api/v2.py`:

```python
def _build_webhook_payload(
    article, org_config: OrgConfig, *, domain_name: str, sent_at_iso: str
) -> dict:
    """Materialize the JSON body sent to org_config.webhook_url."""
    title = ""
    if article.html:
        # First-H1 extraction lives in the frontend; backend just sends the
        # raw HTML and lets the receiver / our editor surface the H1.
        # Title sent as the first alternative_title fallback when present.
        if article.alternative_titles:
            title = article.alternative_titles[0]
    raw_facts = "\n".join(f.text for f in article.facts)
    related = [
        {"title": t, "reason": ""}
        for t in (article.followup_topics or [])
    ]
    images = [
        {
            "label": img.get("name", ""),
            "url": img.get("url", ""),
            "template_id": img.get("template_id"),
            "created_at": img.get("created_at"),
        }
        for img in (article.generated_images or [])
    ]
    return {
        "article_id": str(article.id),
        "org_code": article.org_code,
        "sent_at": sent_at_iso,
        "topic": article.topic,
        "title": title,
        "alternative_titles": list(article.alternative_titles or []),
        "html": article.html or "",
        "raw_facts": raw_facts,
        "related_topics": related,
        "generated_images": images,
        "metadata": {
            "created_at": article.created_at.isoformat() if article.created_at else None,
            "domain": domain_name,
        },
    }
```

- [ ] **Step 2: Add the endpoint**

Insert into `backend/api/v2.py` immediately after the `patch_article` function (around line 1139):

```python
@router.post(
    "/articles/{article_id}/send-webhook",
    summary="POST the article to the org's configured webhook URL",
    tags=["articles"],
)
async def send_article_webhook(
    article_id: UUID,
    org: Org = Depends(get_current_org),
    article_repo: ArticleRepository = Depends(get_article_repo),
    org_config_repo: OrgConfigRepository = Depends(get_org_config_repo),
) -> dict:
    """Sends the finished article to OrgConfig.webhook_url. Synchronous;
    30s timeout; no retry. Always appends a row to article.webhook_deliveries
    and returns the same record to the caller.
    """
    article = await article_repo.get(article_id, org_code=org.code)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    config = await org_config_repo.get(org.code)
    webhook_url = (config.webhook_url if config else None) or ""
    if not webhook_url:
        raise HTTPException(status_code=400, detail="Webhook not configured for this org")
    if not webhook_url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Webhook URL must use https://")

    sent_at = datetime.utcnow().isoformat() + "Z"
    payload = _build_webhook_payload(
        article, config, domain_name=org.domain_name, sent_at_iso=sent_at
    )
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "User-Agent": "ArticleWriter/2",
    }
    if config.webhook_secret:
        headers["X-Webhook-Secret"] = config.webhook_secret

    entry: dict[str, Any]
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(webhook_url, json=payload, headers=headers)
        if 200 <= resp.status_code < 300:
            entry = {"sent_at": sent_at, "status": "success", "http_status": resp.status_code, "error": None}
        else:
            entry = {
                "sent_at": sent_at,
                "status": "error",
                "http_status": resp.status_code,
                "error": f"http {resp.status_code}",
            }
    except httpx.TimeoutException:
        entry = {"sent_at": sent_at, "status": "error", "http_status": None, "error": "timeout"}
    except httpx.HTTPError as exc:
        entry = {"sent_at": sent_at, "status": "error", "http_status": None, "error": str(exc)[:200]}

    await article_repo.record_webhook_delivery(article_id, org_code=org.code, entry=entry)
    logfire.info(
        "article webhook delivery",
        article_id=str(article_id),
        org_code=org.code,
        webhook_host=httpx.URL(webhook_url).host,
        status=entry["status"],
        http_status=entry["http_status"],
    )
    return entry
```

(`datetime` is already imported at the top of `v2.py`; verify before adding.)

- [ ] **Step 3: Write the failing tests**

Create `tests/api/test_send_webhook.py`:

```python
"""POST /v2/articles/{id}/send-webhook — happy path, error response, timeout, no-config."""

from __future__ import annotations

import httpx
import pytest
import respx


@pytest.mark.asyncio
async def test_send_webhook_success(client, seeded_article_with_webhook):
    """2xx response → delivery recorded as success and returned."""
    article, _org_config = seeded_article_with_webhook
    with respx.mock(assert_all_called=True) as router:
        route = router.post("https://hook.example/in").mock(
            return_value=httpx.Response(202, json={"ok": True})
        )
        resp = await client.post(f"/v2/articles/{article.id}/send-webhook")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["http_status"] == 202
        # Header forwarded
        sent = route.calls.last.request
        assert sent.headers.get("X-Webhook-Secret") == "sekret"


@pytest.mark.asyncio
async def test_send_webhook_5xx_recorded_as_error(client, seeded_article_with_webhook):
    article, _ = seeded_article_with_webhook
    with respx.mock() as router:
        router.post("https://hook.example/in").mock(return_value=httpx.Response(500))
        resp = await client.post(f"/v2/articles/{article.id}/send-webhook")
        assert resp.status_code == 200
        assert resp.json() == {
            "sent_at": resp.json()["sent_at"],  # opaque
            "status": "error",
            "http_status": 500,
            "error": "http 500",
        }


@pytest.mark.asyncio
async def test_send_webhook_timeout_recorded_as_error(client, seeded_article_with_webhook):
    article, _ = seeded_article_with_webhook
    with respx.mock() as router:
        router.post("https://hook.example/in").mock(side_effect=httpx.TimeoutException("slow"))
        resp = await client.post(f"/v2/articles/{article.id}/send-webhook")
        body = resp.json()
        assert body["status"] == "error"
        assert body["http_status"] is None
        assert body["error"] == "timeout"


@pytest.mark.asyncio
async def test_send_webhook_400_when_url_not_configured(client, seeded_article):
    """No webhook_url on org → 400 with detail."""
    resp = await client.post(f"/v2/articles/{seeded_article.id}/send-webhook")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Webhook not configured for this org"


@pytest.mark.asyncio
async def test_send_webhook_secret_omitted_when_unset(client, seeded_article_with_webhook_nosecret):
    """webhook_secret blank → X-Webhook-Secret header not sent."""
    article, _ = seeded_article_with_webhook_nosecret
    with respx.mock() as router:
        route = router.post("https://hook.example/in").mock(return_value=httpx.Response(200))
        await client.post(f"/v2/articles/{article.id}/send-webhook")
        sent = route.calls.last.request
        assert "X-Webhook-Secret" not in sent.headers
```

Fixtures needed (add to `tests/conftest.py` if missing — or to a closer `conftest.py` if one exists in `tests/api/`):

```python
@pytest.fixture
async def seeded_article_with_webhook(seeded_article, org_config_repo):
    config = await org_config_repo.get(seeded_article.org_code)
    config.webhook_url = "https://hook.example/in"
    config.webhook_secret = "sekret"
    await org_config_repo.upsert(config)
    return seeded_article, config


@pytest.fixture
async def seeded_article_with_webhook_nosecret(seeded_article, org_config_repo):
    config = await org_config_repo.get(seeded_article.org_code)
    config.webhook_url = "https://hook.example/in"
    config.webhook_secret = None
    await org_config_repo.upsert(config)
    return seeded_article, config
```

If `seeded_article` / `org_config_repo` / `client` fixtures have different names in this repo, grep `tests/conftest.py` for the existing equivalents and adapt — do not invent new ones.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/api/test_send_webhook.py -v`
Expected: all five tests PASS.

- [ ] **Step 5: Lint + type-check**

Run: `uv run ruff check backend/api/v2.py tests/api/test_send_webhook.py && uv run pyright backend/api/v2.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add backend/api/v2.py tests/api/test_send_webhook.py tests/conftest.py
git commit -m "feat(api): POST /v2/articles/{id}/send-webhook"
```

---

## Task 8: Frontend types

**Files:**
- Modify: `frontend/src/types.ts`

- [ ] **Step 1: Extend `DomainConfigData`**

In `frontend/src/types.ts`, inside the `DomainConfigData` interface, immediately after `image_creator_enabled: boolean;` (around line 176), add:

```typescript
  webhook_url: string | null;
  webhook_secret: string | null;
```

- [ ] **Step 2: Add the `WebhookDelivery` interface**

Append before or after `DomainConfigData` in `frontend/src/types.ts`:

```typescript
export interface WebhookDelivery {
  sent_at: string;
  status: "success" | "error";
  http_status: number | null;
  error: string | null;
}
```

- [ ] **Step 3: Extend the `Article` interface with `webhook_deliveries`**

Find the `Article` interface in `frontend/src/types.ts` (`grep -n "interface Article" frontend/src/types.ts`). Inside it, alongside `generated_images`, add:

```typescript
  webhook_deliveries: WebhookDelivery[];
```

- [ ] **Step 4: Type-check**

Run: `cd frontend && npm run typecheck`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types.ts
git commit -m "feat(types): webhook fields on DomainConfigData and Article"
```

---

## Task 9: i18n strings

**Files:**
- Modify: `frontend/src/i18n/types.ts`
- Modify: `frontend/src/i18n/pl.ts`
- Modify: `frontend/src/i18n/en.ts`

- [ ] **Step 1: Extend the i18n shape in types.ts**

In `frontend/src/i18n/types.ts`:

- Inside the `settingsNav` block (`grep -n "settingsNav" frontend/src/i18n/types.ts`), add: `integrations: string;`
- Inside the `articleView` block (line ~351 by the existing layout), add: `send: string; sending: string; sendOk: string; sendError: string; sentAgo: (mins: number) => string;`
- Add a new top-level section: `webhook: { url: string; urlPlaceholder: string; secret: string; secretPlaceholder: string; sectionTitle: string; sectionHint: string; }`

(Use existing type-definition style — match the surrounding `(args) => string` pattern used elsewhere in the file. If `(mins: number) => string` does not match the file's style, just use `sentAgoMinutes: string` with the format `"Wysłano {n} min temu"` and do the substitution in the component.)

- [ ] **Step 2: Polish strings in pl.ts**

In `frontend/src/i18n/pl.ts`:

Inside `settingsNav` add: `integrations: "Integracje",`

Inside `articleView` add (after `exportHtml`):

```typescript
    send: "Wyślij",
    sending: "Wysyłanie…",
    sendOk: "Wysłano",
    sendError: "Błąd wysyłki",
    sentAgo: (mins: number) => mins < 1 ? "przed chwilą" : `${mins} min temu`,
```

Add a new top-level block:

```typescript
  webhook: {
    sectionTitle: "Webhook (callback)",
    sectionHint: "Adres, na który zostanie wysłany artykuł po kliknięciu „Wyślij" w widoku artykułu. Puste pole = guzik ukryty.",
    url: "Webhook URL",
    urlPlaceholder: "https://hook.twojadomena.pl/articles",
    secret: "Webhook Secret (opcjonalnie)",
    secretPlaceholder: "wysyłany jako nagłówek X-Webhook-Secret",
  },
```

- [ ] **Step 3: English strings in en.ts**

In `frontend/src/i18n/en.ts` mirror the same additions:

```typescript
// settingsNav
    integrations: "Integrations",
// articleView (after exportHtml)
    send: "Send",
    sending: "Sending…",
    sendOk: "Sent",
    sendError: "Send failed",
    sentAgo: (mins: number) => mins < 1 ? "just now" : `${mins} min ago`,
// new top-level block
  webhook: {
    sectionTitle: "Webhook (callback)",
    sectionHint: "URL the article will be POSTed to when you press \"Send\" in the article view. Empty = button hidden.",
    url: "Webhook URL",
    urlPlaceholder: "https://hook.your-domain.com/articles",
    secret: "Webhook Secret (optional)",
    secretPlaceholder: "sent as X-Webhook-Secret header",
  },
```

- [ ] **Step 4: Type-check**

Run: `cd frontend && npm run typecheck`
Expected: no errors (en.ts and pl.ts must structurally match types.ts).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/i18n/types.ts frontend/src/i18n/pl.ts frontend/src/i18n/en.ts
git commit -m "feat(i18n): webhook + integrations strings"
```

---

## Task 10: SettingsNav adds "integracje"

**Files:**
- Modify: `frontend/src/components/SettingsNav.tsx`

- [ ] **Step 1: Extend `SECTION_IDS` and `labels`**

In `frontend/src/components/SettingsNav.tsx`:

Change line 3 from:

```typescript
const SECTION_IDS = ["podstawowe", "modele", "wyszukiwanie", "media", "wytyczne", "html", "stance", "tytuly", "przyklady", "szablony", "szablony-obrazkow", "discovery", "streamy"] as const;
```

to (added `"integracje"` at the end, before `streamy` for grouping):

```typescript
const SECTION_IDS = ["podstawowe", "modele", "wyszukiwanie", "media", "wytyczne", "html", "stance", "tytuly", "przyklady", "szablony", "szablony-obrazkow", "discovery", "streamy", "integracje"] as const;
```

Then inside the `labels` object, add:

```typescript
    integracje: t.settingsNav.integrations,
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run typecheck`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SettingsNav.tsx
git commit -m "feat(settings): add integracje nav entry"
```

---

## Task 11: DomainConfigForm — integracje section

**Files:**
- Modify: `frontend/src/components/DomainConfigForm.tsx`

- [ ] **Step 1: Find an existing section block to mimic**

The form uses `sectionVisible(id)` to switch displays. Locate one of the smaller sections (e.g. `<section id="html"`) and use its structure as a template — same outer `<section>` style, same `inputStyle`, same `set(...)` helper.

- [ ] **Step 2: Add the section markup**

Inside `DomainConfigForm.tsx`, **after** the closing `</section>` of `szablony-obrazkow` (around the end of the templates block, ~line 740), insert:

```tsx
        <section id="integracje" style={{ display: sectionVisible("integracje") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>
            {t.webhook.sectionTitle}
          </h3>
          <p style={{ fontSize: 12, color: "var(--muted)", marginBottom: 12 }}>
            {t.webhook.sectionHint}
          </p>

          <label style={labelStyle}>
            {t.webhook.url}
            <input
              type="url"
              value={form.webhook_url ?? ""}
              onChange={(e) => set("webhook_url", e.target.value || null)}
              placeholder={t.webhook.urlPlaceholder}
              style={inputStyle}
            />
          </label>

          <label style={labelStyle}>
            {t.webhook.secret}
            <input
              type="password"
              value={form.webhook_secret ?? ""}
              onChange={(e) => set("webhook_secret", e.target.value || null)}
              placeholder={t.webhook.secretPlaceholder}
              autoComplete="off"
              style={inputStyle}
            />
          </label>
        </section>
```

`labelStyle` and `inputStyle` are already defined locally in the file — reuse them exactly. If `labelStyle` isn't defined, look in the same file for how other labels are styled and copy that.

- [ ] **Step 3: Type-check + lint**

Run: `cd frontend && npm run typecheck && npm run lint`
Expected: no errors.

- [ ] **Step 4: Manual smoke (UI)**

Start the frontend (`cd frontend && npm run dev`), open Settings → Integracje, type a URL + secret, hit Save, refresh, confirm values persist. Document the result in the commit message.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/DomainConfigForm.tsx
git commit -m "feat(settings): integracje section with webhook URL + secret"
```

---

## Task 12: ArticleView — Send button + status line

**Files:**
- Modify: `frontend/src/components/ArticleView.tsx`

- [ ] **Step 1: Load org config and add send state**

At the top of the `ArticleView` component (after the existing `useState` hooks, around line 28), add:

```typescript
const [domainConfig, setDomainConfig] = useState<DomainConfigData | null>(null);
const [sending, setSending] = useState(false);
const [sendBanner, setSendBanner] = useState<{ ok: boolean; text: string } | null>(null);
```

Add at the top of the file the type import:

```typescript
import type { Article, DomainConfigData, EmbedCandidate, Fact, Quote, SocialMediaAttachment, WebhookDelivery } from "../types";
```

(Append `DomainConfigData` and `WebhookDelivery` to the existing import line — do not add a second import.)

Add a one-shot effect to fetch the domain config (it's a tiny call, fine to do per article load):

```typescript
useEffect(() => {
  let cancelled = false;
  request<DomainConfigData>("/v2/domain-config")
    .then((cfg) => { if (!cancelled) setDomainConfig(cfg); })
    .catch(() => { /* settings unconfigured — button stays hidden */ });
  return () => { cancelled = true; };
}, [request]);
```

- [ ] **Step 2: Implement the send handler**

Inside the component (near `handleDeleteGeneratedImage`):

```typescript
async function handleSendWebhook() {
  if (!article) return;
  setSending(true);
  setSendBanner(null);
  try {
    const delivery = await request<WebhookDelivery>(
      `/v2/articles/${article.id}/send-webhook`,
      { method: "POST" },
    );
    setArticle((a) => a ? { ...a, webhook_deliveries: [...(a.webhook_deliveries ?? []), delivery] } : a);
    setSendBanner({
      ok: delivery.status === "success",
      text: delivery.status === "success" ? av.sendOk : (delivery.error ?? av.sendError),
    });
  } catch (e: unknown) {
    setSendBanner({ ok: false, text: e instanceof Error ? e.message : String(e) });
  } finally {
    setSending(false);
  }
}
```

- [ ] **Step 3: Add the button + status line in the toolbar**

In `frontend/src/components/ArticleView.tsx` find the existing `<Button … onClick={handleExport} …>` (around line 321). Immediately **before** that line, add:

```tsx
{domainConfig?.webhook_url ? (
  <Button
    variant="outline"
    size="sm"
    onClick={handleSendWebhook}
    disabled={sending}
  >
    {sending ? av.sending : av.send}
  </Button>
) : null}
```

Then immediately **after** the closing `</div>` of the action-buttons row (around line 324, the `<div style={{ display: "flex", gap: 8, …}}>`), add a status line element:

```tsx
{domainConfig?.webhook_url && (article.webhook_deliveries?.length ?? 0) > 0 && (() => {
  const last: WebhookDelivery = article.webhook_deliveries[article.webhook_deliveries.length - 1];
  const minsAgo = Math.max(0, Math.round((Date.now() - new Date(last.sent_at).getTime()) / 60000));
  const icon = last.status === "success" ? "✓" : "✕";
  const colorVar = last.status === "success" ? "var(--success-fg)" : "var(--error-fg)";
  const label = last.status === "success"
    ? `${icon} ${av.sendOk} ${av.sentAgo(minsAgo)}`
    : `${icon} ${last.error ?? av.sendError} (${av.sentAgo(minsAgo)})`;
  return (
    <div style={{ width: "100%", fontSize: 11, color: colorVar, marginTop: 6, textAlign: "right" }}>
      {label}
    </div>
  );
})()}

{sendBanner && (
  <div style={{ width: "100%", fontSize: 11, color: sendBanner.ok ? "var(--success-fg)" : "var(--error-fg)", marginTop: 4, textAlign: "right" }}>
    {sendBanner.text}
  </div>
)}
```

- [ ] **Step 4: Type-check + lint**

Run: `cd frontend && npm run typecheck && npm run lint`
Expected: no errors.

- [ ] **Step 5: Manual smoke (UI)**

Start the frontend, open an article. With webhook unconfigured: button is hidden. Configure a webhook URL pointing at https://webhook.site/<id> + a secret, refresh: button appears. Click it: status line shows `✓ Wysłano …`. Verify webhook.site received the POST with the right payload and `X-Webhook-Secret` header. Document in the commit message.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ArticleView.tsx
git commit -m "feat(article-view): Wyślij button + delivery status line"
```

---

## Task 13: End-to-end verification

**Files:**
- None (verification only)

- [ ] **Step 1: Full backend test suite**

Run: `uv run pytest -x`
Expected: green.

- [ ] **Step 2: Full frontend type + lint**

Run: `cd frontend && npm run typecheck && npm run lint`
Expected: green.

- [ ] **Step 3: Final manual run-through**

1. Settings → Integracje: leave URL empty → article view button hidden.
2. Set URL + secret → save.
3. Article view: button appears.
4. Click → status line shows success.
5. Inspect webhook.site receipt: payload contains `article_id`, `html`, `generated_images` URLs (no base64), `X-Webhook-Secret` header set.
6. Set URL to a 500-returning endpoint (e.g. `https://httpstat.us/500`): status line shows `✕ http 500 (just now)`.
7. Confirm `articles.webhook_deliveries` in DB has both entries.

- [ ] **Step 4: Final commit (no-op if nothing changed)**

If steps 1-3 required tweaks, commit them. Otherwise skip.
